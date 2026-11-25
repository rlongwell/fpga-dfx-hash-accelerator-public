#!/usr/bin/env python3
"""Hash PS memory, files or binary streams directly through the FPGA DMA driver.

No sockets or software fallback. The shared TCP service must release the device
before this process opens it. Use one LocalHasher context for repeated jobs.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import os
from pathlib import Path
import stat
import sys
import threading
import time
import json

from hash_service import ALGORITHMS, MAX_LENGTH, Hardware


def default_manifest() -> Path:
    root = Path(__file__).resolve().parent.parent
    installed = root / "dfx_manifest.json"
    return installed if installed.is_file() else root / "results/dfx_manifest.json"


class _BufferReader:
    def __init__(self, view):
        self.view, self.offset = view, 0

    def readinto(self, target):
        count = min(len(target), len(self.view) - self.offset)
        target[:count] = self.view[self.offset:self.offset + count]
        self.offset += count
        return count


class LocalHasher:
    """Exclusive FPGA owner; jobs on this instance are serialized.

    Input memory/files must remain unchanged until the synchronous call returns.
    A stream must implement blocking readinto(). Exactly length bytes are read;
    trailing bytes belong to the next job. Optional verification uses hashlib
    only as an independent reference, never as the returned hash backend.
    """

    def __init__(self, device=Path("/dev/hash-accel"), manifest=None):
        self.device = Path(device)
        self._lock = threading.Lock()
        self._closed = False
        try:
            self._hardware = Hardware(self.device, Path(manifest) if manifest else default_manifest())
        except OSError as error:
            if error.errno == errno.EBUSY:
                raise RuntimeError(
                    "FPGA is busy. On the shared SD image run "
                    "'/opt/zybo/hash/start.sh stop; modprobe hash_accel' first. "
                    "Restart the service with '/opt/zybo/hash/start.sh start' when done."
                ) from error
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        with self._lock:
            if not self._closed:
                self._hardware.close()
                self._closed = True

    def hash_bytes(self, data, algorithm="sha3", *, verify=False):
        """Hash a contiguous bytes/bytearray/memoryview without copying it whole."""
        with memoryview(data) as original, original.cast("B") as view:
            return self.hash_stream(_BufferReader(view), len(view), algorithm, verify=verify)

    def hash_file(self, path, algorithm="sha3", *, verify=False):
        with Path(path).open("rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("hash_file needs a regular file; use hash_stream with an exact length")
            return self.hash_stream(source, info.st_size, algorithm, verify=verify)

    def hash_stream(self, source, length, algorithm="sha3", *, verify=False):
        if not isinstance(algorithm, str) or algorithm not in ALGORITHMS:
            raise ValueError("algorithm must be sha3, sha256 or blake2s")
        if type(length) is not int or not 0 <= length <= MAX_LENGTH:
            raise ValueError("length must be a byte count between 0 and 2^61-1")
        if not callable(getattr(source, "readinto", None)):
            raise TypeError("source must implement blocking binary readinto()")
        with self._lock:
            if self._closed:
                raise ValueError("LocalHasher is closed")
            hardware = self._hardware
            load_ns = hardware.select(algorithm)
            reference = ({"sha3": hashlib.sha3_256, "sha256": hashlib.sha256,
                          "blake2s": hashlib.blake2s}[algorithm]() if verify else None)
            active = False
            started = time.perf_counter_ns()
            transfers = 0
            try:
                hardware.start(length)
                active = True
                remaining = length
                while remaining:
                    count = min(remaining, hardware.buffer_size)
                    with memoryview(hardware.buffer)[:count] as target:
                        filled = 0
                        while filled < count:
                            with target[filled:] as tail:
                                received = source.readinto(tail)
                            if received is None:
                                raise BlockingIOError("nonblocking streams are unsupported")
                            if type(received) is not int or not 0 <= received <= count - filled:
                                raise ValueError("readinto returned an invalid byte count")
                            if received == 0:
                                raise EOFError("input ended before its declared length")
                            filled += received
                        if reference is not None:
                            reference.update(target)
                        hardware.transfer(count)
                    remaining -= count
                    transfers += 1
                result = hardware.result()
                active = False
            except BaseException:
                if active:
                    hardware.abort()
                raise
            elapsed = time.perf_counter_ns() - started
            if reference is not None and result["digest"] != reference.hexdigest():
                raise RuntimeError("FPGA digest disagrees with hashlib")
            result.update(status="ok", backend="fpga-dma", transport="local-device",
                          algorithm=algorithm, algorithm_id=hardware.info()[1], length=length,
                          dma_transfers=transfers, buffer_size=hardware.buffer_size,
                          manager_load_ns=load_ns, local_hash_ns=elapsed,
                          reference_hashing_in_timed_region=verify)
            if reference is not None:
                result["verified"] = True
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", help="regular file, or - for binary stdin")
    parser.add_argument("--text", help="hash this UTF-8 text, including empty text")
    parser.add_argument("--length", type=int, help="required byte count for stdin")
    parser.add_argument("--algorithm", choices=tuple(ALGORITHMS), default="sha3")
    parser.add_argument("--manifest", type=Path, default=default_manifest())
    parser.add_argument("--device", type=Path, default=Path("/dev/hash-accel"))
    parser.add_argument("--verify", action="store_true", help="compare FPGA output with hashlib")
    args = parser.parse_args()
    if (args.file is None) == (args.text is None):
        parser.error("supply a file (or -) or --text")
    if args.file == "-":
        if args.length is None or not 0 <= args.length <= MAX_LENGTH:
            parser.error("stdin requires --length with an exact nonnegative byte count")
    elif args.length is not None:
        parser.error("--length applies only to stdin; files/text have automatic lengths")
    try:
        with LocalHasher(args.device, args.manifest) as hasher:
            if args.text is not None:
                result = hasher.hash_bytes(args.text.encode("utf-8"), args.algorithm, verify=args.verify)
            elif args.file == "-":
                result = hasher.hash_stream(sys.stdin.buffer, args.length, args.algorithm, verify=args.verify)
            else:
                result = hasher.hash_file(args.file, args.algorithm, verify=args.verify)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, EOFError, RuntimeError) as error:
        print(f"hash_local: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
