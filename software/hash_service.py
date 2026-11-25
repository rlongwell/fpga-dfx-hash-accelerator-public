#!/usr/bin/env python3
"""Bounded-memory TCP file hashing through the Linux PL accelerator driver.

The production backend never hashes file payloads in software. The test backend
is separate and explicitly selected by the offline tests.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path
import socket
import struct
import time

ALGORITHMS = {"sha3": 1, "sha256": 2, "blake2s": 3}
MAX_LENGTH = (1 << 61) - 1
MAX_HEADER = 4096
CONTROL_LOCK = '/run/zybo-hash-control.lock'


@contextmanager
def control_lock():
    """Serialize GUI/raw-input driver transitions across complete operations."""
    with open(CONTROL_LOCK, 'a') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Another FPGA input operation owns the accelerator.') from error
        yield


def ioctl_number(direction: int, number: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord("H") << 8) | number


INFO = ioctl_number(2, 0, 16)
START = ioctl_number(1, 1, 8)
TRANSFER = ioctl_number(1, 2, 4)
RESULT = ioctl_number(2, 3, 48)
SWITCH = ioctl_number(3, 4, 144)
ABORT = ioctl_number(0, 5, 0)


def receive_json(connection: socket.socket) -> dict:
    # Read exactly through newline; do not consume subsequent binary payload.
    header = bytearray()
    while len(header) < MAX_HEADER:
        byte = connection.recv(1)
        if not byte:
            raise EOFError("connection ended before header")
        if byte == b"\n":
            value = json.loads(header)
            if not isinstance(value, dict):
                raise ValueError("header must be a JSON object")
            return value
        header.extend(byte)
    raise ValueError("header exceeds 4096 bytes")


def send_json(connection: socket.socket, value: dict) -> None:
    connection.sendall(json.dumps(value, separators=(",", ":")).encode() + b"\n")


def firmware_path(name: str) -> Path:
    """Use the kernel firmware loader's filesystem search order."""
    if Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("invalid firmware name")
    roots = []
    custom = Path("/sys/module/firmware_class/parameters/path")
    if custom.exists() and custom.read_text().strip():
        roots.append(Path(custom.read_text().strip()))
    release = os.uname().release
    roots.extend([Path("/lib/firmware/updates") / release, Path("/lib/firmware/updates"),
                  Path("/lib/firmware") / release, Path("/lib/firmware")])
    for root in roots:
        candidate = root / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"firmware is not installed in the kernel search path: {name}")


class Hardware:
    def __init__(self, device: Path, manifest: Path):
        # Raw GEM/replay runs temporarily unload this driver. Keep a second
        # API/GUI process from reopening it during that exclusive handoff.
        if os.path.isdir('/run/zybo-hash-net.lock'):
            try:
                with open('/run/zybo-hash-net.lock/owner') as source:
                    owner = int(source.read().strip())
            except (OSError, ValueError):
                owner = None
            if owner != os.getpid():
                raise RuntimeError('An exclusive FPGA Ethernet/replay job owns the accelerator.')
        self.manifest = json.loads(manifest.read_text())
        if self.manifest.get("abi") != 65536 or self.manifest.get("part") != "xc7z020clg400-1":
            raise ValueError("manifest hardware ABI/part mismatch")
        identity = Path("/proc/device-tree/core-forge,static-sha256")
        if identity.exists():
            running = identity.read_bytes().rstrip(b"\0").decode("ascii")
            if running != self.manifest.get("static_sha256"):
                raise ValueError("running static image and partial-image manifest mismatch")
        self.fd = os.open(device, os.O_RDWR | os.O_CLOEXEC)
        try:
            abi, _, self.buffer_size, _ = self.info()
            if abi != 65536 or self.buffer_size <= 0:
                raise ValueError("driver ABI/buffer mismatch")
            self.buffer = mmap.mmap(self.fd, self.buffer_size, flags=mmap.MAP_SHARED,
                                    prot=mmap.PROT_READ | mmap.PROT_WRITE)
        except BaseException:
            os.close(self.fd)
            raise

    def info(self) -> tuple[int, int, int, int]:
        result = bytearray(16)
        fcntl.ioctl(self.fd, INFO, result, True)
        return struct.unpack("<IIII", result)

    def select(self, algorithm: str) -> int:
        expected_id = ALGORITHMS[algorithm]
        if self.info()[1] == expected_id:
            return 0
        image = self.manifest["images"][algorithm]
        if image["algorithm_id"] != expected_id:
            raise ValueError("image algorithm ID mismatch")
        name = image["filename"]
        encoded = name.encode("ascii")
        if len(encoded) >= 128:
            raise ValueError("firmware name too long")
        path = firmware_path(name)
        # Checks the configuration artifact, never the file payload.
        with path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != image["sha256"]:
            raise ValueError("partial bitstream checksum mismatch")
        request = bytearray(struct.pack("<I128sIQ", expected_id, encoded, 0, 0))
        fcntl.ioctl(self.fd, SWITCH, request, True)
        if self.info()[1] != expected_id:
            raise RuntimeError("configured algorithm ID mismatch")
        return struct.unpack("<I128sIQ", request)[3]

    def start(self, length: int) -> None:
        fcntl.ioctl(self.fd, START, struct.pack("<Q", length))

    def transfer(self, length: int) -> None:
        # Blocking ioctl keeps the receive buffer owned by DMA until completion.
        fcntl.ioctl(self.fd, TRANSFER, struct.pack("<I", length))

    def result(self) -> dict:
        result = bytearray(48)
        fcntl.ioctl(self.fd, RESULT, result, True)
        digest, cycles, status, error = struct.unpack("<32sQII", result)
        if error or not status & 2 or status & 4:
            raise RuntimeError(f"hardware hash error {error}, status {status:#x}")
        return {"digest": digest.hex(), "core_cycles": cycles}

    def abort(self) -> None:
        fcntl.ioctl(self.fd, ABORT)

    def close(self) -> None:
        self.buffer.close()
        os.close(self.fd)


def handle_connection(connection: socket.socket, hardware, timeout: float = 30.0,
                      receive_mode: str = "direct") -> None:
    """One file per connection. Errors abort the file before another is accepted."""
    connection.settimeout(timeout)
    active = False
    try:
        if receive_mode not in ("direct", "prefetch"):
            raise ValueError("receive_mode must be direct or prefetch")
        request = receive_json(connection)
        algorithm, length = request.get("algorithm"), request.get("length")
        if not isinstance(algorithm, str) or algorithm not in ALGORITHMS:
            raise ValueError("algorithm must be sha3, sha256 or blake2s")
        if type(length) is not int or not 0 <= length <= MAX_LENGTH:
            raise ValueError("length must be a byte count between 0 and 2^61-1")
        manager_load_ns = hardware.select(algorithm) or 0
        hardware.start(length)
        active = True
        send_json(connection, {"status": "ready", "algorithm": algorithm, "length": length,
                               "manager_load_ns": manager_load_ns})
        started = time.perf_counter_ns()
        if receive_mode == "prefetch":
            from hash_receive import receive_prefetched
            receive_prefetched(connection, hardware, length)
        remaining = length if receive_mode == "direct" else 0
        while remaining:
            count = min(remaining, hardware.buffer_size)
            view = memoryview(hardware.buffer)[:count]
            try:
                offset = 0
                while offset < count:
                    received = connection.recv_into(view[offset:])
                    if not received:
                        raise EOFError("file ended before the declared length")
                    offset += received
                hardware.transfer(count)
            finally:
                view.release()
            remaining -= count
        result = hardware.result()
        active = False
        result.update(status="ok", algorithm=algorithm, length=length,
                      transfer_and_hash_ns=time.perf_counter_ns() - started,
                      receive_mode=receive_mode)
        send_json(connection, result)
    except (OSError, ValueError, RuntimeError, EOFError, KeyError) as error:
        if active:
            hardware.abort()
        try:
            send_json(connection, {"status": "error", "message": str(error)})
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", type=Path, default=Path("/dev/hash-accel"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9237)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--receive-mode", choices=("direct", "prefetch"), default="direct")
    args = parser.parse_args()
    hardware = Hardware(args.device, args.manifest)
    try:
        with socket.create_server((args.listen, args.port), backlog=4) as listener:
            print(f"Hash accelerator listening on {args.listen}:{args.port}", flush=True)
            while True:
                connection, _ = listener.accept()
                with connection:
                    handle_connection(connection, hardware, args.timeout, args.receive_mode)
    finally:
        hardware.close()


if __name__ == "__main__":
    main()
