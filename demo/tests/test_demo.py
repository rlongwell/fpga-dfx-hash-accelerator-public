"""Offline boundary/recovery tests. These do not emulate physical evidence."""
import hashlib
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import board_agent


class EvidenceValidation(unittest.TestCase):
    def setUp(self):
        self.digest = hashlib.sha3_256(b'abc').hexdigest()
        self.result = dict(status='ok', algorithm='sha3', length=3, digest=self.digest,
                           core_cycles=100, local_hash_ns=4000, backend='fpga-dma')

    def test_valid_result_keeps_timing_scope(self):
        row = server.validate_result(self.result, 'sha3', 3, self.digest)
        self.assertTrue(row['verified'])
        self.assertIn('excludes USB', row['timing_scope'])

    def test_reject_digest_or_request_mismatch(self):
        for change in [dict(digest='0'*64), dict(length=4), dict(algorithm='sha256')]:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                server.validate_result(dict(self.result, **change), 'sha3', 3, self.digest)

    def test_reject_missing_hardware_or_timing(self):
        for change in [dict(core_cycles=0), dict(core_cycles=True), dict(backend='reference'), dict(local_hash_ns=0)]:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                server.validate_result(dict(self.result, **change), 'sha3', 3, self.digest)

    def test_wrong_installed_sources_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'static_sha256'):
            server.validate_board({'static_sha256':'0'*64})

    def test_kernel_admission_still_requires_pinned_sources(self):
        root=server.ROOT
        manifest=json.loads(server.BOARD_MANIFEST.read_text())
        board=dict(profile='hash',static_sha256=manifest['static_sha256'],
                   manifest_sha256=server.digest(server.BOARD_MANIFEST),
                   service_sha256=server.digest(root/'software/hash_service.py'),
                   client_sha256=server.digest(root/'software/hash_client.py'),
                   local_api_sha256=server.digest(root/'software/hash_local.py'))
        for release in ('6.6.40-dfx-hash','6.6.40-dfx-hash-wifi'):
            server.validate_board(dict(board,kernel=release))
        with self.assertRaisesRegex(RuntimeError,'profile or kernel'):
            server.validate_board(dict(board,kernel='6.6.40-unverified'))
        with self.assertRaisesRegex(RuntimeError,'service_sha256'):
            server.validate_board(dict(board,kernel='6.6.40-dfx-hash-wifi',service_sha256='0'*64))


class Settings(unittest.TestCase):
    def test_theme_atomic_preserves_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(server, 'SETTINGS', Path(temp)/'gui.json'):
            server.SETTINGS.write_text('{"window": {"width": 1200}}')
            server.save_theme('light')
            self.assertEqual(server.read_settings(), {'theme':'light', 'window':{'width':1200}})
            self.assertEqual(len(list(Path(temp).iterdir())), 1)

    def test_malformed_settings_and_invalid_theme(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(server, 'SETTINGS', Path(temp)/'gui.json'):
            server.SETTINGS.write_text('not json')
            self.assertEqual(server.read_settings(), {})
            with self.assertRaises(ValueError): server.save_theme('invalid')


class BoardRecovery(unittest.TestCase):
    def test_busy_raw_input_does_not_stop_service_or_load_driver(self):
        service=SimpleNamespace(control_lock=mock.Mock(side_effect=RuntimeError('input busy')))
        with mock.patch.dict(sys.modules,{'hash_service':service}), \
             mock.patch.object(board_agent.subprocess,'run') as commands:
            for operation,args in [(board_agent.run,(Path('/tmp/zybo-demo-test'),['sha3'])),
                                   (board_agent.run_comparison,(Path('/tmp/zybo-demo-test'),Path('/tmp/config')))]:
                with self.assertRaisesRegex(RuntimeError,'input busy'):operation(*args)
            commands.assert_not_called()

    def test_hash_failure_restores_sha3_and_restarts_service(self):
        hardware = mock.MagicMock()
        hardware.__enter__.return_value = hardware
        hardware.hash_file.side_effect = RuntimeError('injected DMA failure')
        module = SimpleNamespace(LocalHasher=mock.Mock(return_value=hardware))
        with mock.patch.dict(sys.modules, {'hash_local':module,'hash_service':SimpleNamespace(control_lock=nullcontext)}), mock.patch.object(board_agent.subprocess, 'run') as run, mock.patch.object(board_agent, 'emit'):
            with self.assertRaisesRegex(RuntimeError, 'injected DMA failure'):
                board_agent.run(Path('/tmp/zybo-demo-test'), ['sha3'])
            hardware.hash_bytes.assert_called_once_with(b'', algorithm='sha3', verify=True)
            self.assertEqual(run.call_args.args[0], ['/opt/zybo/hash/start.sh', 'start'])
            hardware.__exit__.assert_called_once()

    def test_failure_to_open_device_still_restarts_service(self):
        module = SimpleNamespace(LocalHasher=mock.Mock(side_effect=OSError('device unavailable')))
        with mock.patch.dict(sys.modules, {'hash_local':module,'hash_service':SimpleNamespace(control_lock=nullcontext)}), mock.patch.object(board_agent.subprocess, 'run') as run:
            with self.assertRaises(OSError): board_agent.run(Path('/tmp/zybo-demo-test'), ['sha3'])
            self.assertEqual(run.call_args.args[0][-1], 'start')


class LocalHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = mock.patch.object(server, 'OUTPUT', Path(cls.temp.name))
        cls.output.start()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.http.state = server.State()
        cls.url = 'http://127.0.0.1:' + str(cls.http.server_port)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join()
        cls.output.stop(); cls.temp.cleanup()

    def post(self, path, body=b'{}', **headers):
        return urllib.request.urlopen(urllib.request.Request(self.url+path, data=body, headers=headers))

    def test_cross_origin_or_missing_token_rejected(self):
        for headers in [{}, {'X-Demo-Token':self.http.state.token, 'Origin':'https://example.com'}]:
            with self.subTest(headers=headers), self.assertRaises(urllib.error.HTTPError) as caught:
                self.post('/api/jobs', **headers)
            self.assertEqual(caught.exception.code, 400)

    def test_binary_and_empty_uploads_keep_bytes(self):
        for payload in [b'', bytes(range(256))]:
            with self.post('/api/files', payload, **{'X-Demo-Token':self.http.state.token, 'X-File-Name':'demo%20%27%3B%24.dat'}) as response:
                value = json.load(response)
            file = self.http.state.files[value['id']]
            self.assertEqual(file['path'].read_bytes(), payload)
            self.assertEqual(value['name'], "demo ';$.dat")

    def test_path_traversal_does_not_expose_repository(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.url+'/%2e%2e/server.py')
        self.assertEqual(caught.exception.code, 404)

    def test_oversized_upload_rejected_before_body(self):
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', self.http.server_port)
        connection.putrequest('POST','/api/files')
        connection.putheader('X-Demo-Token',self.http.state.token)
        connection.putheader('Content-Length',str(server.MAX_FILE+1))
        connection.endheaders()
        self.assertEqual(connection.getresponse().status,400)
        connection.close()


if __name__ == '__main__': unittest.main()
