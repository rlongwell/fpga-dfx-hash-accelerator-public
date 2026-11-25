#!/usr/bin/env python3
"""Core software hashes in RAM, excluding allocation, file I/O, and networking."""
import argparse
import hashlib
import json
import os
import platform
import ssl
import statistics
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--bytes", type=int, default=16 * 1024 * 1024)
parser.add_argument("--repeats", type=int, default=9)
parser.add_argument("--output", type=Path, default=Path("results/x86_software.json"))
parser.add_argument("--context", default="No workload isolation or CPU affinity requested")
args = parser.parse_args()
if args.bytes <= 0 or args.repeats < 3:
    parser.error("bytes must be positive and repeats at least 3")
payload = bytes(range(256)) * ((args.bytes + 255) // 256)
payload = payload[:args.bytes]
cpuinfo = Path("/proc/cpuinfo").read_text()
cpu = next((line.split(":", 1)[1].strip() for line in cpuinfo.splitlines()
            if line.startswith("model name")), platform.processor())
results = {"scope": "x86 software hashes in RAM; no DMA/Ethernet/ARM comparison",
           "cpu": cpu, "platform": platform.platform(), "python": platform.python_version(),
           "openssl": ssl.OPENSSL_VERSION, "load_average_at_start": os.getloadavg(),
           "measurement_context": args.context,
           "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "bytes": args.bytes, "repeats": args.repeats, "algorithms": {}}
for name, function in [("sha3", hashlib.sha3_256), ("sha256", hashlib.sha256),
                       ("blake2s", hashlib.blake2s)]:
    expected = function(payload).digest()
    samples = []
    for _ in range(args.repeats):
        start = time.perf_counter_ns()
        digest = function(payload).digest()
        elapsed = time.perf_counter_ns() - start
        assert digest == expected
        samples.append(elapsed)
    median = statistics.median(samples)
    results["algorithms"][name] = {"samples_ns": samples, "median_ns": median,
        "median_MB_s": args.bytes * 1000 / median,
        "min_ns": min(samples), "max_ns": max(samples)}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, indent=2))
