"""Offline protocol and mocked-device tests; no board performance is measured."""
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hash_service import (Hardware, handle_connection, receive_json, send_json,
                          INFO, START, TRANSFER, RESULT, SWITCH, ABORT, control_lock)


class ReferenceBackend:
    def __init__(self, buffer_size=257):
        self.buffer_size = buffer_size
        self.buffer = bytearray(buffer_size)
        self.transfers = []
        self.aborted = False
        self.fail_switch = False

    def select(self, algorithm):
        if self.fail_switch:
            raise RuntimeError("injected PCAP failure")
        self.hasher = {"sha3": hashlib.sha3_256, "sha256": hashlib.sha256,
                       "blake2s": hashlib.blake2s}[algorithm]()

    def start(self, length):
        self.remaining = length

    def transfer(self, length):
        assert 0 < length <= self.buffer_size and length <= self.remaining
        self.transfers.append(length)
        self.hasher.update(self.buffer[:length])
        self.remaining -= length

    def result(self):
        assert self.remaining == 0
        return {"digest": self.hasher.hexdigest(), "core_cycles": 0}

    def abort(self):
        self.aborted = True


class StaticIdentityTests(unittest.TestCase):
    def test_control_handoff_is_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch('hash_service.CONTROL_LOCK',str(Path(directory)/'owner.lock')):
            with control_lock():
                with self.assertRaisesRegex(RuntimeError,'Another FPGA input operation'):
                    with control_lock():self.fail('overlapping ownership accepted')
            with control_lock():pass

    def test_raw_input_owner_rejected_before_device_access(self):
        for owner in (str(os.getpid()+1), 'incomplete'):
            with mock.patch('hash_service.os.path.isdir',return_value=True), \
                 mock.patch('builtins.open',mock.mock_open(read_data=owner)), \
                 mock.patch('hash_service.os.open') as opened:
                with self.assertRaisesRegex(RuntimeError,'Ethernet/replay job'):
                    Hardware('/dev/hash-accel',Path('/unused/manifest.json'))
                opened.assert_not_called()

    def test_missing_owner_during_atomic_handoff_is_busy(self):
        with mock.patch('hash_service.os.path.isdir',return_value=True), \
             mock.patch('builtins.open',side_effect=FileNotFoundError), \
             mock.patch('hash_service.os.open') as opened:
            with self.assertRaisesRegex(RuntimeError,'Ethernet/replay job'):
                Hardware('/dev/hash-accel',Path('/unused/manifest.json'))
            opened.assert_not_called()

    def test_raw_owner_can_restore_the_normal_driver(self):
        manifest=mock.Mock()
        manifest.read_text.return_value=json.dumps(dict(abi=65536,part='xc7z020clg400-1'))
        with mock.patch('hash_service.os.path.isdir',return_value=True), \
             mock.patch('builtins.open',mock.mock_open(read_data=str(os.getpid()))), \
             mock.patch('hash_service.os.open',side_effect=OSError('device reached')) as opened:
            with self.assertRaisesRegex(OSError,'device reached'):
                Hardware('/dev/hash-accel',manifest)
            opened.assert_called_once()

    def test_wrong_partial_set_is_rejected_before_device_access(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory)/'manifest.json'
            manifest.write_text(json.dumps(dict(abi=65536, part='xc7z020clg400-1', static_sha256='a'*64)))
            identity = mock.Mock()
            identity.exists.return_value = True
            identity.read_bytes.return_value = b'b'*64+b'\0'
            with mock.patch('hash_service.Path', return_value=identity), mock.patch('hash_service.os.open') as opened:
                with self.assertRaisesRegex(ValueError, 'running static image'):
                    Hardware('/dev/hash-accel', manifest)
                opened.assert_not_called()

    def test_matching_and_legacy_device_trees_reach_device_open(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory)/'manifest.json'
            manifest.write_text(json.dumps(dict(abi=65536, part='xc7z020clg400-1', static_sha256='a'*64)))
            for present in (False, True):
                identity = mock.Mock()
                identity.exists.return_value = present
                identity.read_bytes.return_value = b'a'*64+b'\0'
                with self.subTest(identity_present=present), mock.patch('hash_service.Path', return_value=identity), mock.patch('hash_service.os.open', side_effect=OSError('mock device open')) as opened:
                    with self.assertRaisesRegex(OSError, 'mock device open'):
                        Hardware('/dev/hash-accel', manifest)
                    opened.assert_called_once()


class ProtocolTests(unittest.TestCase):
    def connect(self, backend):
        client, server = socket.socketpair()
        errors = []

        def run():
            try:
                with server:
                    handle_connection(server, backend, timeout=2)
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(client.close)

        def cleanup():
            client.close()
            thread.join(3)
            self.assertFalse(thread.is_alive(), "server hung")
            self.assertFalse(errors, errors)
        self.addCleanup(cleanup)
        return client

    def test_files_split_across_many_dma_buffers(self):
        for algorithm, reference in [("sha3", hashlib.sha3_256),
                                     ("sha256", hashlib.sha256), ("blake2s", hashlib.blake2s)]:
            for length in [0, 1, 55, 56, 63, 64, 65, 135, 136, 137, 4096, 1048579]:
                with self.subTest(algorithm=algorithm, length=length):
                    payload = bytes((i * 37 + 11) & 255 for i in range(length))
                    backend = ReferenceBackend()
                    connection = self.connect(backend)
                    send_json(connection, {"algorithm": algorithm, "length": length})
                    self.assertEqual(receive_json(connection)["status"], "ready")
                    for offset in range(0, length, 113):
                        connection.sendall(payload[offset:offset+113])
                    result = receive_json(connection)
                    self.assertEqual(result["status"], "ok")
                    self.assertEqual(result["digest"], reference(payload).hexdigest())
                    self.assertEqual(sum(backend.transfers), length)
                    self.assertEqual(len(backend.buffer), 257)

    def test_short_file_aborts_and_next_request_can_run(self):
        backend = ReferenceBackend()
        connection = self.connect(backend)
        send_json(connection, {"algorithm": "sha3", "length": 1000})
        self.assertEqual(receive_json(connection)["status"], "ready")
        connection.sendall(b"short")
        connection.shutdown(socket.SHUT_WR)
        self.assertEqual(receive_json(connection)["status"], "error")
        self.assertTrue(backend.aborted)
        recovery = self.connect(backend)
        send_json(recovery, {"algorithm": "blake2s", "length": 0})
        self.assertEqual(receive_json(recovery)["status"], "ready")
        self.assertEqual(receive_json(recovery)["digest"], hashlib.blake2s(b"").hexdigest())

    def test_invalid_requests(self):
        for request in [{"algorithm": "bad", "length": 1},
                        {"algorithm": [], "length": 1},
                        {"algorithm": "sha3", "length": -1},
                        {"algorithm": "sha256", "length": 1 << 61},
                        {"algorithm": "sha3", "length": True}, {}, []]:
            with self.subTest(request=request):
                connection = self.connect(ReferenceBackend())
                connection.sendall(json.dumps(request).encode()+b"\n")
                self.assertEqual(receive_json(connection)["status"], "error")

    def test_configuration_failure_prevents_ready(self):
        backend = ReferenceBackend(); backend.fail_switch = True
        connection = self.connect(backend)
        send_json(connection, {"algorithm": "sha256", "length": 2})
        self.assertEqual(receive_json(connection)["status"], "error")
        self.assertEqual(backend.transfers, [])

    def test_uapi_struct_sizes_and_commands(self):
        root = Path(__file__).resolve().parents[2]
        build = root / "build/software-tests"
        build.mkdir(parents=True, exist_ok=True)
        source = build / "uapi_check.c"
        source.write_text('''#include <stdio.h>
#include "hash_accel.h"
int main(void) {
printf("%zu %zu %zu %lu %lu %lu %lu %lu %lu\\n",
sizeof(struct hash_info),sizeof(struct hash_result),sizeof(struct hash_switch),
(unsigned long)HASH_INFO,(unsigned long)HASH_START,(unsigned long)HASH_TRANSFER,
(unsigned long)HASH_RESULT,(unsigned long)HASH_SWITCH,(unsigned long)HASH_ABORT);
}
''')
        subprocess.run(["cc", "-Wall", "-Werror", "-I", str(root/"software/linux"),
                        str(source), "-o", str(build/"uapi_check")], check=True)
        actual = list(map(int, subprocess.check_output([build/"uapi_check"]).split()))
        self.assertEqual(actual, [16, 48, 144, INFO, START, TRANSFER, RESULT, SWITCH, ABORT])
        self.assertEqual(struct.calcsize("<32sQII"), 48)
        self.assertEqual(struct.calcsize("<I128sIQ"), 144)

    def test_command_line_client_over_tcp(self):
        root = Path(__file__).resolve().parents[2]
        backend = ReferenceBackend(buffer_size=4096)
        failures = []
        with socket.create_server(("127.0.0.1", 0)) as listener, tempfile.TemporaryDirectory() as directory:
            port = listener.getsockname()[1]
            payload = bytes(range(256)) * 1000 + b"final partial buffer"
            path = Path(directory) / "message.bin"
            path.write_bytes(payload)

            def serve():
                try:
                    listener.settimeout(5)
                    connection, _ = listener.accept()
                    with connection:
                        handle_connection(connection, backend)
                except BaseException as error:
                    failures.append(error)

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            result = subprocess.run([sys.executable, str(root/"software/hash_client.py"),
                                     "127.0.0.1", str(path), "--port", str(port),
                                     "--algorithm", "sha256", "--verify"],
                                    text=True, capture_output=True, timeout=10, check=True)
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertFalse(failures)
            answer = json.loads(result.stdout)
            self.assertTrue(answer["verified"])
            self.assertGreater(answer["client_transfer_and_result_ns"], 0)
            self.assertGreaterEqual(answer["client_request_ns"], answer["client_transfer_and_result_ns"])
            self.assertTrue(answer["reference_prepass"])
            self.assertFalse(answer["reference_hashing_in_timed_region"])
            self.assertEqual(answer["digest"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(sum(backend.transfers), len(payload))

    def test_ethernet_benchmark_harness_over_localhost(self):
        root = Path(__file__).resolve().parents[2]
        backend = ReferenceBackend(buffer_size=4096)
        failures = []
        with socket.create_server(("127.0.0.1", 0)) as listener, tempfile.TemporaryDirectory() as directory:
            port = listener.getsockname()[1]
            payload = bytes(range(256)) * 17 + b"benchmark harness only"
            path = Path(directory) / "message.bin"
            output = Path(directory) / "measurements.json"
            path.write_bytes(payload)

            def serve():
                try:
                    listener.settimeout(5)
                    for _ in range(6):
                        connection, _ = listener.accept()
                        with connection:
                            handle_connection(connection, backend)
                except BaseException as error:
                    failures.append(error)

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            subprocess.run([sys.executable, str(root/"benchmarks/ethernet.py"),
                            "127.0.0.1", str(path), "--port", str(port),
                            "--repeats", "2", "--output", str(output)],
                           text=True, capture_output=True, timeout=15, check=True)
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertFalse(failures)
            report = json.loads(output.read_text())
            self.assertEqual(report["bytes"], len(payload))
            self.assertEqual(report["repeats"], 2)
            self.assertEqual(set(report["algorithms"]), {"sha3", "sha256", "blake2s"})
            for name, reference in [("sha3", hashlib.sha3_256),
                                    ("sha256", hashlib.sha256), ("blake2s", hashlib.blake2s)]:
                result = report["algorithms"][name]
                self.assertEqual(result["digest"], reference(payload).hexdigest())
                self.assertEqual(len(result["samples"]), 2)
                self.assertGreater(result["client_transfer_and_result_median_ns"], 0)
                for sample in result["samples"]:
                    self.assertEqual(sample["algorithm"], name)
                    self.assertEqual(sample["digest"], result["digest"])
                    self.assertGreater(sample["client_transfer_and_result_ns"], 0)
                    self.assertGreaterEqual(sample["client_request_ns"], sample["client_transfer_and_result_ns"])
                    self.assertFalse(sample["reference_hashing_in_timed_region"])
            self.assertEqual(sum(backend.transfers), len(payload)*6)


class HardwareBackendTests(unittest.TestCase):
    """Exercise production Hardware validation against a fake ioctl boundary."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.partial = self.directory / "partial.bin"
        self.partial.write_bytes(b"offline configuration artifact fixture")
        self.manifest_path = self.directory / "manifest.json"
        self.manifest = {
            "abi": 65536, "part": "xc7z020clg400-1",
            "images": {name: {"algorithm_id": algorithm_id,
                              "filename": f"fpga-dfx-hash/test/{name}.bin",
                              "sha256": hashlib.sha256(self.partial.read_bytes()).hexdigest()}
                       for name, algorithm_id in [("sha3", 1), ("sha256", 2), ("blake2s", 3)]}}
        self.write_manifest()
        self.algorithm_id, self.abi, self.buffer_size = 1, 65536, 4096
        self.switch_error = None
        self.configured_id = None
        self.calls, self.switch_requests = [], []
        self.open_device = self.patch("hash_service.os.open", return_value=41)
        self.close_device = self.patch("hash_service.os.close")
        self.mapping = mock.Mock()
        self.map_device = self.patch("hash_service.mmap.mmap", return_value=self.mapping)
        self.find_firmware = self.patch("hash_service.firmware_path", return_value=self.partial)
        self.patch("hash_service.fcntl.ioctl", side_effect=self.ioctl)

    def patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def hardware(self):
        hardware = Hardware(Path("/dev/offline-test-only"), self.manifest_path)
        self.addCleanup(hardware.close)
        return hardware

    def ioctl(self, fd, command, argument=None, mutate=False):
        self.assertEqual(fd, 41)
        self.calls.append(command)
        if command == INFO:
            self.assertTrue(mutate)
            argument[:] = struct.pack("<IIII", self.abi, self.algorithm_id, self.buffer_size, 0)
        elif command == SWITCH:
            self.assertTrue(mutate)
            expected, filename, flags, reserved_duration = struct.unpack("<I128sIQ", argument)
            self.switch_requests.append((expected, filename.rstrip(b"\0"), flags, reserved_duration))
            if self.switch_error:
                raise self.switch_error
            self.algorithm_id = expected if self.configured_id is None else self.configured_id
            argument[:] = struct.pack("<I128sIQ", expected, filename, flags, 123456)
        else:
            self.fail(f"unexpected ioctl {command:#x}")
        return 0

    def test_manifest_abi_and_part_rejected_before_device_open(self):
        for field, value in [("abi", 0), ("part", "wrong-part")]:
            with self.subTest(field=field):
                saved = self.manifest[field]
                self.manifest[field] = value
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, "manifest hardware ABI/part"):
                    self.hardware()
                self.manifest[field] = saved
        self.open_device.assert_not_called()

    def test_driver_abi_and_buffer_rejected_and_device_closed(self):
        for abi, buffer_size in [(0, 4096), (65536, 0)]:
            with self.subTest(abi=abi, buffer_size=buffer_size):
                self.abi, self.buffer_size = abi, buffer_size
                with self.assertRaisesRegex(ValueError, "driver ABI/buffer"):
                    self.hardware()
        self.assertEqual(self.close_device.call_count, 2)
        self.map_device.assert_not_called()

    def test_current_algorithm_avoids_reconfiguration(self):
        hardware = self.hardware()
        self.assertEqual(hardware.select("sha3"), 0)
        self.find_firmware.assert_not_called()
        self.assertNotIn(SWITCH, self.calls)

    def test_switch_validates_image_and_returns_driver_duration(self):
        hardware = self.hardware()
        for name, algorithm_id in [("sha256", 2), ("blake2s", 3), ("sha3", 1)]:
            with self.subTest(algorithm=name):
                self.assertEqual(hardware.select(name), 123456)
                self.assertEqual(self.switch_requests[-1],
                                 (algorithm_id, f"fpga-dfx-hash/test/{name}.bin".encode(), 0, 0))
                self.assertEqual(hardware.select(name), 0)
        self.assertEqual(self.calls.count(SWITCH), 3)

    def test_manifest_algorithm_id_mismatch_blocks_switch(self):
        self.manifest["images"]["sha256"]["algorithm_id"] = 3
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "image algorithm ID mismatch"):
            self.hardware().select("sha256")
        self.find_firmware.assert_not_called()
        self.assertNotIn(SWITCH, self.calls)

    def test_changed_partial_checksum_blocks_switch(self):
        self.partial.write_bytes(b"changed artifact after manifest creation")
        with self.assertRaisesRegex(ValueError, "partial bitstream checksum mismatch"):
            self.hardware().select("sha256")
        self.assertNotIn(SWITCH, self.calls)

    def test_configured_algorithm_id_mismatch_is_rejected(self):
        self.configured_id = 3
        with self.assertRaisesRegex(RuntimeError, "configured algorithm ID mismatch"):
            self.hardware().select("sha256")
        self.assertEqual(self.calls.count(SWITCH), 1)

    def test_driver_switch_failure_never_announces_ready(self):
        self.switch_error = OSError("injected FPGA manager failure")
        connection = ProtocolTests.connect(self, self.hardware())
        send_json(connection, {"algorithm": "sha256", "length": 1})
        answer = receive_json(connection)
        self.assertEqual(answer["status"], "error")
        self.assertIn("injected FPGA manager failure", answer["message"])
        self.assertEqual(self.calls.count(SWITCH), 1)
        self.assertNotIn(START, self.calls)
        self.assertNotIn(TRANSFER, self.calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
