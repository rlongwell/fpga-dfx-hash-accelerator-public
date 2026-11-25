"""Network read-ahead correctness and cancellation, using a software test device."""
import hashlib
import socket
import threading
import time
import unittest

from test_service import ReferenceBackend
from hash_service import handle_connection, receive_json, send_json


class PrefetchTests(unittest.TestCase):
    def connect(self, backend, timeout=1):
        client, server = socket.socketpair()
        client.settimeout(3)
        failures = []

        def serve():
            try:
                with server:
                    handle_connection(server, backend, timeout, receive_mode='prefetch')
            except BaseException as error:
                failures.append(error)

        thread = threading.Thread(target=serve)
        thread.start()

        def cleanup():
            client.close(); thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertFalse(failures)
            self.assertFalse(any(t.name == 'hash-tcp-prefetch' and t.is_alive()
                                 for t in threading.enumerate()))
        self.addCleanup(cleanup)
        return client

    def test_all_digests_and_boundaries_with_slow_dma(self):
        class SlowDevice(ReferenceBackend):
            def transfer(self, length):
                before = bytes(self.buffer[:length])
                time.sleep(.0002)
                assert before == self.buffer[:length], 'DMA input overwritten while active'
                super().transfer(length)

        for algorithm, digest in [('sha3',hashlib.sha3_256),('sha256',hashlib.sha256),('blake2s',hashlib.blake2s)]:
            for length in (0,1,135,136,137,65539):
                with self.subTest(algorithm=algorithm,length=length):
                    data = (bytes(range(256))*257)[:length]
                    device = SlowDevice(1024);client = self.connect(device)
                    send_json(client,dict(algorithm=algorithm,length=length))
                    self.assertEqual(receive_json(client)['status'],'ready')
                    if data:
                        client.sendall(data)
                    answer = receive_json(client)
                    self.assertEqual(answer['digest'],digest(data).hexdigest())
                    self.assertEqual(answer['receive_mode'],'prefetch')
                    self.assertEqual(sum(device.transfers),length)
                    client.close()

    def test_disconnect_aborts_and_recovery_succeeds(self):
        device = ReferenceBackend(1024);client = self.connect(device)
        send_json(client,dict(algorithm='sha3',length=8192));receive_json(client)
        client.sendall(b'short');client.shutdown(socket.SHUT_WR)
        self.assertEqual(receive_json(client)['status'],'error');self.assertTrue(device.aborted)
        recovery = self.connect(device)
        send_json(recovery,dict(algorithm='sha3',length=3));receive_json(recovery)
        recovery.sendall(b'abc')
        self.assertEqual(receive_json(recovery)['digest'],hashlib.sha3_256(b'abc').hexdigest())

    def test_dma_failure_cancels_a_receiver_waiting_for_data(self):
        class FailedDevice(ReferenceBackend):
            def transfer(self, length):
                raise RuntimeError('injected DMA failure')
        device = FailedDevice(1024);client = self.connect(device)
        send_json(client,dict(algorithm='sha3',length=1<<20));receive_json(client)
        client.sendall(b'x'*2048)
        self.assertEqual(receive_json(client)['status'],'error')
        self.assertTrue(device.aborted)

    def test_stalled_sender_times_out_and_releases_worker(self):
        device = ReferenceBackend(1024);client = self.connect(device,timeout=.1)
        send_json(client,dict(algorithm='sha3',length=4096));receive_json(client)
        self.assertEqual(receive_json(client)['status'],'error')
        self.assertTrue(device.aborted)


if __name__ == '__main__':
    unittest.main()
