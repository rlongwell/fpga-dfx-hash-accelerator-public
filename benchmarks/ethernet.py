#!/usr/bin/env python3
"""Measure repeated client-observed file hashing against the configured board."""
import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software"))
from hash_client import hash_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("file", type=Path)
    parser.add_argument("--port", type=int, default=9237)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("ethernet_measurements.json"))
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    report = {"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "client_platform": platform.platform(), "python": platform.python_version(),
              "host": args.host, "port": args.port, "file": str(args.file),
              "bytes": args.file.stat().st_size, "repeats": args.repeats,
              "scope": "Client-observed network file hashing; only a configured board run establishes Ethernet/PL performance",
              "timing": "transfer_and_result begins after ready and ends after parsing the digest response; request also includes TCP connect, header and algorithm selection. Both include file reads, exclude local reference hashing, and use decimal MB/s.",
              "cache": "Reference prepasses and repeated file reads can warm client filesystem cache; no cold-cache claim.",
              "algorithms": {}}
    for name, function in [("sha3", hashlib.sha3_256), ("sha256", hashlib.sha256),
                           ("blake2s", hashlib.blake2s)]:
        with args.file.open("rb") as source:
            expected = hashlib.file_digest(source, function).hexdigest()
        samples = []
        for _ in range(args.repeats):
            result = hash_file(args.host, args.file, name, args.port)
            if result["digest"] != expected or result["length"] != report["bytes"]:
                raise RuntimeError(f"{name}: incorrect digest or file changed during benchmark")
            samples.append(result)
        median = statistics.median(s["client_transfer_and_result_ns"] for s in samples)
        report["algorithms"][name] = {"samples": samples, "digest": expected,
            "client_transfer_and_result_median_ns": median,
            "client_transfer_and_result_median_MB_s": report["bytes"]*1000/median,
            "client_request_median_ns": statistics.median(s["client_request_ns"] for s in samples)}
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(args.output)


if __name__ == "__main__":
    main()
