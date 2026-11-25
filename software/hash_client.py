#!/usr/bin/env python3
"""Stream a file to the PS service; optionally verify its result locally."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time
from hash_service import receive_json, send_json


def hash_file(host, path, algorithm="sha3", port=9237, verify=False):
    """Time client-observed completion; optional reference hashing is untimed.

    File reads during transmission are included. A verification prepass may warm
    the filesystem cache, so its use is recorded in the returned measurement.
    """
    with Path(path).open("rb") as source:
        length = os.fstat(source.fileno()).st_size
        reference = None
        if verify:
            function = {"sha3": hashlib.sha3_256, "sha256": hashlib.sha256,
                        "blake2s": hashlib.blake2s}[algorithm]
            reference = hashlib.file_digest(source, function).hexdigest()
            source.seek(0)
        request_started = time.perf_counter_ns()
        with socket.create_connection((host, port), timeout=30) as connection:
            send_json(connection, {"algorithm": algorithm, "length": length})
            ready = receive_json(connection)
            if ready.get("status") != "ready":
                raise RuntimeError(ready)
            transfer_started = time.perf_counter_ns()
            remaining = length
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise RuntimeError("input file became shorter during transfer")
                connection.sendall(chunk)
                remaining -= len(chunk)
            result = receive_json(connection)
            completed = time.perf_counter_ns()
        if result.get("status") != "ok":
            raise RuntimeError(result)
        if result.get("algorithm") != algorithm or result.get("length") != length:
            raise RuntimeError("server response does not match request")
        result["manager_load_ns"] = ready.get("manager_load_ns", 0)
        result.update(client_transfer_and_result_ns=completed-transfer_started,
                      client_request_ns=completed-request_started,
                      client_transfer_and_result_MB_s=length*1000/(completed-transfer_started),
                      reference_prepass=verify, reference_hashing_in_timed_region=False)
        if reference is not None:
            if result["digest"] != reference:
                raise RuntimeError("hardware digest disagrees with local hashlib")
            result["verified"] = True
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("file", type=Path)
    parser.add_argument("--algorithm", choices=("sha3", "sha256", "blake2s"), default="sha3")
    parser.add_argument("--port", type=int, default=9237)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    print(json.dumps(hash_file(args.host, args.file, args.algorithm, args.port, args.verify), indent=2))


if __name__ == "__main__":
    main()
