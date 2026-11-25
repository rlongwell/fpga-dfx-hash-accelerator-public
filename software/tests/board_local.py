#!/usr/bin/env python3
"""Physical PS-to-PL acceptance test. No mock device or software hash fallback.

Stop the shared hash service, modprobe hash_accel, then run on the Zybo.
This writes only its output report and a temporary input file.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import socket
import stat
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--software", type=Path, default=Path("/opt/zybo/hash/software"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.software))
    from hash_local import LocalHasher

    assert platform.machine().startswith("arm"), "run on the physical ARM board"
    assert stat.S_ISCHR(Path("/dev/hash-accel").stat().st_mode)
    report = {"kind": "physical-zybo-ps-dma", "started_unix": time.time(),
              "kernel_release": platform.release(), "machine": platform.machine(),
              "model": Path("/proc/device-tree/model").read_text().rstrip("\0"),
              "profile_env": Path("/boot/profile.env").read_text(),
              "proc_net_tcp": Path("/proc/net/tcp").read_text(), "jobs": [], "checks": {}}
    paths = [args.software / "hash_local.py", args.software / "hash_service.py",
             args.software.parent / "dfx_manifest.json", Path(__file__),
             Path("/boot/profiles/hash/system.bit"), Path("/boot/profiles/hash/system.dtb")]
    report["files_sha256"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    references = {"sha3": hashlib.sha3_256, "sha256": hashlib.sha256, "blake2s": hashlib.blake2s}
    ids = {"sha3": 1, "sha256": 2, "blake2s": 3}
    pattern = bytes((index * 37 + 11) & 255 for index in range(256))

    def data_for(length):
        return (pattern * ((length + 255) // 256))[:length]

    def check(label, result, data, algorithm):
        assert result["digest"] == references[algorithm](data).hexdigest(), (label, result)
        assert result["algorithm_id"] == ids[algorithm], result
        assert result["core_cycles"] > 0, result
        assert result["length"] == len(data)
        assert result["dma_transfers"] == (len(data) + result["buffer_size"] - 1) // result["buffer_size"]
        assert result["backend"] == "fpga-dma" and result["transport"] == "local-device"
        report["jobs"].append(dict(case=label, **result))
        print("PASS", label, algorithm, len(data), result["digest"], flush=True)

    class ShortReader(io.BytesIO):
        def readinto(self, target):
            return super().readinto(target[:13])

    # Prove the direct API cannot make any socket connection in this process.
    def no_network(*_, **__):
        raise AssertionError("local hashing must not open a socket")

    socket.socket = socket.create_connection = no_network
    try:
        assert not any(":2415 " in line and line.split()[3] == "0A"
                       for line in report["proc_net_tcp"].splitlines()[1:]), "TCP service still running"
        report["checks"]["tcp_service_absent"] = True
        with tempfile.TemporaryDirectory(prefix="hash-local-test-") as directory:
            path = Path(directory) / "input.bin"
            with LocalHasher() as hasher:
                try:
                    other = LocalHasher()
                except RuntimeError as error:
                    assert "busy" in str(error)
                    report["checks"]["exclusive_owner_rejected"] = str(error)
                else:
                    other.close()
                    raise AssertionError("second device owner was accepted")
                lengths = [0, 1, 55, 56, 63, 64, 65, 127, 128, 129, 135, 136, 137,
                           4095, 4096, 4097, 1048575, 1048576, 1048577, 2097169]
                for algorithm in references:
                    for index, length in enumerate(lengths):
                        data = data_for(length)
                        value = [lambda: data, lambda: bytearray(data), lambda: memoryview(data)][index % 3]()
                        result = hasher.hash_bytes(value, algorithm, verify=index % 2 == 0)
                        check("memory", result, data, algorithm)
                    data = data_for(2097169)
                    path.write_bytes(data)
                    check("file", hasher.hash_file(path, algorithm, verify=True), data, algorithm)
                    data = data_for(4097)
                    source = ShortReader(data + b"unconsumed tail")
                    check("short-reads", hasher.hash_stream(source, len(data), algorithm), data, algorithm)
                    assert source.read() == b"unconsumed tail"
                # Abort after one real 1 MiB DMA transfer, then reuse the owner.
                try:
                    hasher.hash_stream(io.BytesIO(data_for(1048577)), 1048578, "sha3")
                except EOFError:
                    report["checks"]["truncated_stream_aborted"] = True
                else:
                    raise AssertionError("truncated stream accepted")
                check("abort-recovery", hasher.hash_bytes(b"recovered", "sha3"), b"recovered", "sha3")
                for algorithm in ["sha3", "sha256", "blake2s", "sha256", "sha3"]:
                    result = hasher.hash_bytes(b"PS to PL switch proof", algorithm)
                    if algorithm != "sha3" or report["jobs"][-1]["algorithm"] != "sha3":
                        assert result["manager_load_ns"] > 0, result
                    check("switch-away-and-back", result, b"PS to PL switch proof", algorithm)
            report["checks"]["api_sockets_forbidden"] = True
            for algorithm in references:
                for kind in ["text", "file", "stdin"]:
                    command = [sys.executable, str(args.software / "hash_local.py"),
                               "--algorithm", algorithm, "--verify"]
                    input_data = None
                    if kind == "text":
                        data = "PS → PL\n".encode()
                        command += ["--text", data.decode()]
                    elif kind == "file":
                        data = data_for(1048577)
                        path.write_bytes(data)
                        command += [str(path)]
                    else:
                        data = data_for(1048577)
                        input_data = data
                        command += ["-", "--length", str(len(data))]
                    completed = subprocess.run(command, input=input_data, capture_output=True, timeout=30)
                    assert completed.returncode == 0, completed.stderr.decode()
                    check("cli-" + kind, json.loads(completed.stdout), data, algorithm)
            # Restore initial SHA3 personality before returning device to service.
            with LocalHasher() as hasher:
                report["restored_algorithm"] = hasher.hash_bytes(b"", "sha3", verify=True)
            report["passed"] = True
    except BaseException as error:
        report["passed"] = False
        report["error"] = repr(error)
        raise
    finally:
        report["finished_unix"] = time.time()
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print("REPORT", args.output, "jobs", len(report["jobs"]), "passed", report.get("passed"), flush=True)


if __name__ == "__main__":
    main()
