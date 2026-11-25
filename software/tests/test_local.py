"""Offline tests of the local API; the explicit fake is not FPGA evidence."""
import errno
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hash_local


class FakeHardware:
    def __init__(self, *_):
        self.buffer_size = 257
        self.buffer = bytearray(self.buffer_size)
        self.transfers = []
        self.aborted = self.closed = False
        self.algorithm = "sha3"

    def info(self):
        return 65536, hash_local.ALGORITHMS[self.algorithm], self.buffer_size, 0

    def select(self, algorithm):
        self.algorithm = algorithm
        return 123

    def start(self, length):
        self.remaining = length
        self.reference = {"sha3": hashlib.sha3_256, "sha256": hashlib.sha256,
                          "blake2s": hashlib.blake2s}[self.algorithm]()

    def transfer(self, count):
        assert 0 < count <= min(self.remaining, self.buffer_size)
        self.reference.update(self.buffer[:count])
        self.remaining -= count
        self.transfers.append(count)

    def result(self):
        assert self.remaining == 0
        return {"digest": self.reference.hexdigest(), "core_cycles": 0}

    def abort(self):
        self.aborted = True

    def close(self):
        self.closed = True


class ShortReader(io.BytesIO):
    def readinto(self, target):
        return super().readinto(target[:7])


class LocalTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(hash_local, "Hardware", FakeHardware)
        patch.start()
        self.addCleanup(patch.stop)

    def test_all_algorithms_empty_boundaries_and_multiple_buffers(self):
        with hash_local.LocalHasher() as hasher:
            for algorithm, reference in [("sha3", hashlib.sha3_256),
                                         ("sha256", hashlib.sha256), ("blake2s", hashlib.blake2s)]:
                for length in [0, 1, 55, 56, 63, 64, 65, 135, 136, 137, 256, 257, 258, 4099]:
                    with self.subTest(algorithm=algorithm, length=length):
                        data = bytes((index * 37 + 11) & 255 for index in range(length))
                        result = hasher.hash_bytes(memoryview(data), algorithm, verify=True)
                        self.assertEqual(result["digest"], reference(data).hexdigest())
                        self.assertEqual(result["dma_transfers"], (length + 256) // 257)
                        self.assertEqual(result["algorithm_id"], hash_local.ALGORITHMS[algorithm])
                        self.assertTrue(result["verified"])

    def test_short_reads_and_trailing_data(self):
        source = ShortReader(bytes(range(256)) * 3 + b"tail")
        with hash_local.LocalHasher() as hasher:
            result = hasher.hash_stream(source, 768, "sha256")
            self.assertEqual(result["digest"], hashlib.sha256(bytes(range(256)) * 3).hexdigest())
            self.assertNotIn("verified", result)
            self.assertEqual(source.read(), b"tail")
            self.assertEqual(hasher._hardware.transfers, [257, 257, 254])

    def test_truncation_aborts_after_dma_then_recovers(self):
        with hash_local.LocalHasher() as hasher:
            with self.assertRaises(EOFError):
                hasher.hash_stream(io.BytesIO(b"x" * 258), 300)
            self.assertTrue(hasher._hardware.aborted)
            self.assertEqual(hasher._hardware.transfers, [257])
            self.assertEqual(hasher.hash_bytes(b"abc")["digest"], hashlib.sha3_256(b"abc").hexdigest())

    def test_reader_failure_and_invalid_read_counts_abort(self):
        for value in [None, -1, 100, True, "1", OSError("reader failed")]:
            with self.subTest(value=value), hash_local.LocalHasher() as hasher:
                reader = mock.Mock()
                if isinstance(value, Exception):
                    reader.readinto.side_effect = value
                else:
                    reader.readinto.return_value = value
                with self.assertRaises((OSError, ValueError)):
                    hasher.hash_stream(reader, 3)
                self.assertTrue(hasher._hardware.aborted)

    def test_hardware_errors_are_propagated_without_fallback(self):
        with hash_local.LocalHasher() as hasher:
            hasher._hardware.transfer = mock.Mock(side_effect=OSError("DMA failed"))
            with self.assertRaisesRegex(OSError, "DMA failed"):
                hasher.hash_bytes(b"abc", verify=True)
            self.assertTrue(hasher._hardware.aborted)

    def test_verify_rejects_wrong_hardware_digest(self):
        with hash_local.LocalHasher() as hasher:
            hasher._hardware.result = lambda: {"digest": "00" * 32, "core_cycles": 1}
            with self.assertRaisesRegex(RuntimeError, "disagrees"):
                hasher.hash_bytes(b"abc", verify=True)

    def test_file_input_and_bytearray(self):
        with tempfile.TemporaryDirectory() as directory, hash_local.LocalHasher() as hasher:
            path = Path(directory) / "input.bin"
            data = bytearray(range(256)) * 4
            path.write_bytes(data)
            expected = hashlib.blake2s(data).hexdigest()
            self.assertEqual(hasher.hash_file(path, "blake2s")["digest"], expected)
            self.assertEqual(hasher.hash_bytes(data, "blake2s")["digest"], expected)

    def test_rejected_inputs_do_not_start_job(self):
        with hash_local.LocalHasher() as hasher:
            with mock.patch.object(hasher._hardware, "start") as start:
                for length in [-1, 1 << 61, True, "3"]:
                    with self.assertRaises(ValueError):
                        hasher.hash_stream(io.BytesIO(), length)
                with self.assertRaises(ValueError):
                    hasher.hash_bytes(b"abc", "bad")
                with self.assertRaises(TypeError):
                    hasher.hash_stream(object(), 3)
                start.assert_not_called()

    def test_close_is_idempotent_and_prevents_reuse(self):
        hasher = hash_local.LocalHasher()
        hasher.close()
        hasher.close()
        self.assertTrue(hasher._hardware.closed)
        with self.assertRaisesRegex(ValueError, "closed"):
            hasher.hash_bytes(b"abc")

    def test_busy_and_missing_device_do_not_fall_back(self):
        with mock.patch.object(hash_local, "Hardware", side_effect=OSError(errno.EBUSY, "busy")):
            with self.assertRaisesRegex(RuntimeError, "modprobe hash_accel"):
                hash_local.LocalHasher()
        with mock.patch.object(hash_local, "Hardware", side_effect=FileNotFoundError("device")):
            with self.assertRaises(FileNotFoundError):
                hash_local.LocalHasher()


if __name__ == "__main__":
    unittest.main()
