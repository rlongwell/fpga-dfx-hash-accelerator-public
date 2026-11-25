#!/usr/bin/env python3
"""Local, dependency-free desktop dashboard for a physical Zybo hash demo."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import re
from pathlib import Path
import secrets
import shlex
import signal
import tempfile
import threading
import time
from urllib.parse import unquote, urlparse
import webbrowser

from uart import Console, Cancelled
from ssh import SSHConsole
from replay import run_replay

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'demo/web'
SETTINGS = ROOT / '.settings/gui.json'
OUTPUT = ROOT / 'build/demo'
MAX_FILE = 16 * 1024 * 1024
VARIANTS = ROOT / 'demo/core_variants.json'
BOARD_MANIFEST = ROOT / 'demo/board_manifest.json'
ALGORITHMS = {'sha3': hashlib.sha3_256, 'sha256': hashlib.sha256, 'blake2s': hashlib.blake2s}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_board(board):
    manifest = json.loads(BOARD_MANIFEST.read_text())
    expected = {
        'static_sha256': manifest['static_sha256'],
        'manifest_sha256': digest(BOARD_MANIFEST),
        'service_sha256': digest(ROOT / 'software/hash_service.py'),
        'client_sha256': digest(ROOT / 'software/hash_client.py'),
        'local_api_sha256': digest(ROOT / 'software/hash_local.py'),
    }
    for key, value in expected.items():
        if board.get(key) != value:
            raise RuntimeError(f'Installed {key} differs from this demo’s validated configuration.')
    if board.get('profile') != 'hash' or board.get('kernel') not in ('6.6.40-dfx-hash', '6.6.40-dfx-hash-wifi'):
        raise RuntimeError('Unexpected board profile or kernel.')


def validate_result(result, algorithm, size, reference):
    if result.get('status') != 'ok' or result.get('algorithm') != algorithm or result.get('length') != size:
        raise RuntimeError('Board result does not match the requested file and algorithm.')
    if result.get('digest') != reference:
        raise RuntimeError('FPGA digest disagrees with the independent PC reference.')
    if type(result.get('core_cycles')) is not int or result['core_cycles'] <= 0:
        raise RuntimeError('Hardware did not report a positive cycle count.')
    if result.get('backend') != 'fpga-dma' or type(result.get('local_hash_ns')) is not int or result['local_hash_ns'] <= 0:
        raise RuntimeError('The result lacks direct hardware API timing.')
    return dict(result, reference_digest=reference, verified=True, backend='physical-fpga-dma',
                timing_scope='On-board local API: RAM file read + driver + DMA + core; excludes USB upload and reconfiguration')


def validate_comparison(result, size, reference):
    core = result.get('core')
    config = json.loads(VARIANTS.read_text())
    if core not in config['variants'] or result.get('image') != config['variants'][core]['image']:
        raise RuntimeError('The result lacks the expected comparison bitstream identity.')
    if result.get('intermediate_algorithm_id') != 2 or result.get('manager_load_ns', 0) <= 0:
        raise RuntimeError('The comparison did not force and observe reconfiguration.')
    samples = result.get('samples', [])
    if result.get('repeats') != 7 or len(samples) != 7:
        raise RuntimeError('Expected seven measured samples after a warmup.')
    for sample in [result.get('warmup', {})] + samples:
        validate_result(sample, 'sha3', size, reference)
    times = sorted(s['local_hash_ns'] for s in samples)
    if (result['local_hash_ns'], result.get('minimum_hash_ns'), result.get('maximum_hash_ns')) != (times[3],times[0],times[-1]):
        raise RuntimeError('Comparison summary differs from its actual samples.')
    return validate_result(result, 'sha3', size, reference)


def read_settings():
    try:
        value = json.loads(SETTINGS.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_theme(theme):
    if theme not in ('dark', 'light'):
        raise ValueError('Unknown theme.')
    value = read_settings()
    value['theme'] = theme
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.gui-', dir=SETTINGS.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        os.replace(name, SETTINGS)
    finally:
        Path(name).unlink(missing_ok=True)


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.active = None
        self.jobs = {}
        self.files = {}
        self.board = None
        self.token = secrets.token_urlsafe(32)
        self.loaded_code_hashes = {str(p.relative_to(ROOT)): digest(p)
                                   for p in (ROOT/'demo/server.py', ROOT/'demo/uart.py',
                                             ROOT/'demo/ssh.py', ROOT/'demo/replay.py')}
        OUTPUT.mkdir(parents=True, exist_ok=True)

    def register_file(self, path, name):
        with self.lock:
            if len(self.files) >= 8:
                old = next(iter(self.files))
                self.files.pop(old)['path'].unlink(missing_ok=True)
            ident = secrets.token_hex(12)
            self.files[ident] = dict(path=path, name=Path(name).name[:160], size=path.stat().st_size)
            return dict(id=ident, name=self.files[ident]['name'], size=path.stat().st_size)

    def start(self, request):
        kind = request.get('kind', 'hash')
        if kind not in ('probe', 'hash', 'replay'):
            raise ValueError('Unknown job type.')
        transport = request.get('transport', 'ssh-wired')
        if transport not in ('usb-uart', 'ssh-wired', 'ssh-wifi'):
            raise ValueError('Unknown board connection.')
        if kind == 'replay' and transport == 'usb-uart':
            raise ValueError('The live replay sweep needs an SSH connection.')
        algorithms = request.get('algorithms', ['sha3'])
        compare = request.get('compare_cores', False)
        if type(compare) is not bool or (compare and algorithms != ['sha3']):
            raise ValueError('Core comparison requires SHA3-256 only.')
        if not isinstance(algorithms, list) or not 1 <= len(algorithms) <= 3 or any(a not in ALGORITHMS for a in algorithms):
            raise ValueError('Choose one or all three supported algorithms.')
        with self.lock:
            if self.active:
                raise RuntimeError('A board operation is already running.')
            file = None
            if kind == 'hash':
                file = self.files.get(request.get('file_id'))
                if file is None:
                    raise ValueError('Select or upload a file again.')
                if compare and not file['size']:
                    raise ValueError('The pinned Quartz core cannot encode an empty input.')
                self.files.pop(request['file_id'])
            ident = secrets.token_hex(12)
            job = dict(id=ident, kind=kind, state='running', stage='connecting', progress=0,
                       created_utc=datetime.now(timezone.utc).isoformat(), results=[], events=[],
                       algorithms=algorithms, compare_cores=compare, transport=transport,
                       file={k: v for k, v in file.items() if k != 'path'} if file else None)
            cancel = threading.Event()
            self.jobs[ident] = (job, cancel)
            self.active = ident
            while len(self.jobs) > 16:
                self.jobs.pop(next(iter(self.jobs)))
            threading.Thread(target=self.work, args=(job, cancel, file), daemon=True).start()
            return {'id': ident}

    def update(self, job, **values):
        with self.lock:
            job.update(values)

    def event(self, job, message, references, size):
        event = message['event']
        with self.lock:
            job['events'].append(dict(message, received_utc=datetime.now(timezone.utc).isoformat()))
        if event == 'board':
            validate_board(message['board'])
            self.update(job, board=message['board'])
            with self.lock:
                self.board = dict(message['board'], checked_utc=datetime.now(timezone.utc).isoformat())
        elif event in ('loading', 'hashing'):
            self.update(job, stage=event, current_algorithm=message['algorithm'],
                        current_core=message.get('core'), current_core_label=message.get('core_label'))
        elif event == 'result':
            result = message['result']
            algorithm = result.get('algorithm')
            if algorithm not in references:
                raise RuntimeError('Unexpected algorithm returned by the board.')
            row = (validate_comparison(result, size, references[algorithm]) if job['compare_cores']
                   else validate_result(result, algorithm, size, references[algorithm]))
            with self.lock:
                if job['compare_cores'] and result['core'] in [r.get('core') for r in job['results']]:
                    raise RuntimeError('The board returned a duplicate comparison core.')
                job['results'].append(row)
        elif event == 'payload_verified':
            if message['size'] != size or message['sha256'] != job['input_sha256']:
                raise RuntimeError('Board payload differs from the selected PC file.')
            self.update(job, decoded_payload_verified=True)
        elif event == 'restoring':
            self.update(job, stage='restoring')
        elif event == 'restored':
            validate_result(message['result'], 'sha3', 0, hashlib.sha3_256(b'').hexdigest())
            self.update(job, restored_sha3=True)

    def work(self, job, cancel, file):
        payload = '/tmp/zybo-demo-' + job['id'] + '.payload'
        agent = ROOT / 'demo/board_agent.py'
        remote_agent = '/tmp/zybo-demo-agent-' + digest(agent)[:16] + '.py'
        remote_config = '/tmp/zybo-demo-' + job['id'] + '-variants.json'
        packed = None
        self.update(job, demo_source_sha256=dict(self.loaded_code_hashes,
                                                **{'demo/board_agent.py':digest(agent)}))
        references = {}
        started = time.monotonic()
        try:
            if file:
                for name in job['algorithms']:
                    with file['path'].open('rb') as stream:
                        references[name] = hashlib.file_digest(stream, ALGORITHMS[name]).hexdigest()
                self.update(job, input_sha256=digest(file['path']))
                data = gzip.compress(file['path'].read_bytes(), compresslevel=6, mtime=0)
                compressed = len(data) < file['size'] * .9
                if compressed:
                    fd, name = tempfile.mkstemp(prefix='compressed-', dir=OUTPUT)
                    packed = Path(name)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(data)
                transfer_file = packed or file['path']
                self.update(job, compressed_transfer=compressed, transfer_bytes=transfer_file.stat().st_size)
            suffix = '.uart.log' if job['transport'] == 'usb-uart' else '.ssh.log'
            with (OUTPUT / (job['id'] + suffix)).open('wb') as log:
                connection = Console(log) if job['transport'] == 'usb-uart' else SSHConsole(log, job['transport'])
                self.connected_work(connection, job, cancel, file, remote_agent, agent, payload,
                                    remote_config, references, packed)
            self.update(job, state='passed', stage='complete')
        except Cancelled as error:
            self.update(job, state='cancelled', stage='cancelled', error=str(error))
        except Exception as error:
            self.update(job, state='failed', stage='failed', error=str(error))
            with self.lock:
                self.board = None
        finally:
            if file:
                file['path'].unlink(missing_ok=True)
            if packed:
                packed.unlink(missing_ok=True)
            self.update(job, elapsed_seconds=time.monotonic() - started,
                        completed_utc=datetime.now(timezone.utc).isoformat())
            with self.lock:
                snapshot = deepcopy(job)
                self.active = None
            (OUTPUT / (job['id'] + '.json')).write_text(json.dumps(snapshot, indent=2) + '\n')

    def connected_work(self, connection, job, cancel, file, remote_agent, agent, payload,
                       remote_config, references, packed):
        with connection as console:
            check = console.command('if [ -f ' + shlex.quote(remote_agent) + ' ]; then sha256sum ' + shlex.quote(remote_agent) + '; fi')
            if not any(line.startswith(digest(agent) + ' ') for line in check.splitlines()):
                # Use a unique destination even if an unexpected stale helper exists.
                remote_agent = '/tmp/zybo-demo-agent-' + secrets.token_hex(12) + '.py'
                console.upload(agent, remote_agent)
            try:
                handler = lambda msg: self.event(job, msg, references, file['size'] if file else 0)
                console.agent(remote_agent, '--probe', handler)
                if cancel.is_set():
                    raise Cancelled('Cancelled before file transfer.')
                if job['kind'] == 'replay':
                    def update(**values): self.update(job, **values)
                    def event(value):
                        with self.lock:
                            job['events'].append(dict(value, received_utc=datetime.now(timezone.utc).isoformat()))
                    run_replay(console, job, cancel, update, event, OUTPUT/'replay-runs'/job['id'])
                    console.agent(remote_agent, '--probe', handler)
                if file:
                    self.update(job, stage='uploading')
                    transfer_start = time.monotonic()
                    console.upload(packed or file['path'], payload,
                                   progress=lambda n, total: self.update(job, bytes_sent=n, progress=n / max(total, 1)),
                                   cancelled=cancel.is_set)
                    self.update(job, upload_seconds=time.monotonic() - transfer_start, progress=1, upload_verified=True)
                    if cancel.is_set():
                        raise Cancelled('Cancelled after file transfer.')
                    arguments = '--file ' + shlex.quote(payload) + ' --algorithms ' + ' '.join(job['algorithms'])
                    arguments += f" --expected-size {file['size']} --input-sha256 {job['input_sha256']}"
                    if job['compressed_transfer']:
                        arguments += ' --compressed'
                    if job['compare_cores']:
                        console.upload(VARIANTS, remote_config)
                        self.update(job, comparison_config_sha256=digest(VARIANTS))
                        arguments += ' --compare ' + shlex.quote(remote_config)
                    console.agent(remote_agent, arguments, handler)
                    expected = 2 if job['compare_cores'] else len(job['algorithms'])
                    if len(job['results']) != expected or not job.get('restored_sha3') or not job.get('decoded_payload_verified'):
                        raise RuntimeError('The hardware run or SHA3 restoration was incomplete.')
            finally:
                console.command('rm -f ' + ' '.join(shlex.quote(p) for p in
                                [payload, str(Path(payload).with_suffix('.decoded')), remote_agent, remote_config]))

    def get_job(self, ident):
        with self.lock:
            if ident in self.jobs:
                return deepcopy(self.jobs[ident][0])
        if not re.fullmatch(r'[0-9a-f]{24}', ident):
            raise KeyError('Unknown completed job.')
        saved = json.loads((OUTPUT / (ident + '.json')).read_text())
        if saved.get('id') != ident or saved.get('state') not in ('passed','failed','cancelled'):
            raise ValueError('Saved job is incomplete or has a different identity.')
        return saved


class Handler(BaseHTTPRequestHandler):
    server_version = 'ZyboDemo/1.0'

    @property
    def state(self):
        return self.server.state

    def log_message(self, *_):
        pass

    def json(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        expected = {'127.0.0.1:' + str(self.server.server_port), 'localhost:' + str(self.server.server_port)}
        if self.headers.get('Host') not in expected:
            raise ValueError('Use this dashboard through its local address.')
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://' + h for h in expected}:
            raise ValueError('Cross-origin requests are not supported.')

    def do_GET(self):
        try:
            self.allowed()
            path = urlparse(self.path).path
            if path == '/api/bootstrap':
                summary = json.loads((ROOT / 'results/sha3-performance-20261115/summary.json').read_text())
                with self.state.lock:
                    self.json(dict(token=self.state.token, settings=read_settings(), board=self.state.board,
                                   active=self.state.active, benchmark=summary, max_file=MAX_FILE))
            elif path.startswith('/api/replay-evidence/'):
                ident = path.rsplit('/', 1)[1]
                job = self.state.get_job(ident)
                if job['kind'] != 'replay' or job['state'] == 'running':
                    raise ValueError('Finish the sweep before exporting evidence.')
                folder = OUTPUT/'replay-runs'/ident
                self.json(dict(job=job, plan=json.loads((folder/'plan.json').read_text()),
                               results=json.loads((folder/'results.json').read_text())))
            elif path.startswith('/api/jobs/'):
                self.json(self.state.get_job(path.rsplit('/', 1)[1]))
            else:
                relative = 'index.html' if path == '/' else unquote(path).lstrip('/')
                target = (WEB / relative).resolve()
                target.relative_to(WEB)
                data = target.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(data)
        except (OSError, ValueError, KeyError) as error:
            self.json({'error': str(error)}, 404)

    def do_POST(self):
        temporary = None
        try:
            self.allowed()
            if self.headers.get('X-Demo-Token') != self.state.token:
                raise ValueError('Refresh the dashboard before starting a request.')
            length = int(self.headers.get('Content-Length', '-1'))
            path = urlparse(self.path).path
            if length < 0 or length > (MAX_FILE if path == '/api/files' else 8192):
                raise ValueError('Request exceeds the demo limit of 16.78 MB per file.')
            self.connection.settimeout(30)
            if path == '/api/files':
                fd, name = tempfile.mkstemp(prefix='payload-', dir=OUTPUT)
                temporary = Path(name)
                with os.fdopen(fd, 'wb') as stream:
                    left = length
                    while left:
                        block = self.rfile.read(min(left, 65536))
                        if not block:
                            raise ValueError('File upload was incomplete.')
                        stream.write(block)
                        left -= len(block)
                result = self.state.register_file(temporary, unquote(self.headers.get('X-File-Name', 'untitled')))
                temporary = None
                self.json(result)
                return
            request = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(request, dict):
                raise ValueError('Request must be a JSON object.')
            if path == '/api/jobs':
                self.json(self.state.start(request), 202)
            elif path == '/api/cancel':
                with self.state.lock:
                    if self.state.active:
                        self.state.jobs[self.state.active][1].set()
                self.json({'ok': True})
            elif path == '/api/settings':
                save_theme(request.get('theme'))
                self.json({'ok': True})
            else:
                self.json({'error': 'Unknown endpoint.'}, 404)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            self.json({'error': str(error)}, 400)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


def main():
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.state = State()
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Zybo Hash Lab → {url}\nPress Ctrl+C to stop. Keep this terminal open.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        with server.state.lock:
            if server.state.active:
                server.state.jobs[server.state.active][1].set()
        print('Finishing the current board operation safely…', flush=True)
        while server.state.active:
            time.sleep(.2)
    finally:
        server.server_close()
        for file in server.state.files.values():
            file['path'].unlink(missing_ok=True)


if __name__ == '__main__':
    main()
