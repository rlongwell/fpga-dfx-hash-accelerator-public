#!/usr/bin/env python3
"""Run only on the configured Zybo: DMA/core, FPGA-manager and ARM measurements."""
import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software"))
from hash_service import Hardware

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--manifest", type=Path, required=True)
parser.add_argument("--device", type=Path, default=Path("/dev/hash-accel"))
parser.add_argument("--bytes", type=int, default=64 * 1024 * 1024)
parser.add_argument("--repeats", type=int, default=5)
parser.add_argument("--output", type=Path, default=Path("board_measurements.json"))
args = parser.parse_args()
if not 0 <= args.bytes < 1 << 61 or args.repeats < 1:
    parser.error("invalid byte/repetition count")
if not platform.machine().startswith("arm"):
    parser.error("this benchmark must run on the Zynq ARM board")
hardware = Hardware(args.device, args.manifest)
try:
    # Prepare a repeated pattern outside timed regions. Working memory is bounded.
    pattern = bytes(range(256)) * ((hardware.buffer_size + 255) // 256)
    pattern = pattern[:hardware.buffer_size]
    hardware.buffer[:] = pattern
    # Make the first SHA3 measurement an actual switch, not an already-loaded ID.
    hardware.select("blake2s")
    report = {"platform": platform.platform(), "machine": platform.machine(),
              "python": platform.python_version(), "bytes": args.bytes,
              "buffer_size": hardware.buffer_size, "repeats": args.repeats,
              "manifest_static_sha256": hardware.manifest["static_sha256"],
              "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "scope": "Real board DMA+core (no Ethernet), FPGA Manager loads and ARM in-memory software hashing",
              "algorithms": {}}
    for name, function in [("sha3", hashlib.sha3_256), ("sha256", hashlib.sha256),
                           ("blake2s", hashlib.blake2s)]:
        load_samples = [hardware.select(name)]
        reference = function()
        for offset in range(0, args.bytes, hardware.buffer_size):
            reference.update(pattern[:min(hardware.buffer_size, args.bytes-offset)])
        expected = reference.hexdigest()
        dma_samples, software_samples, core_cycles = [], [], []
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            hardware.start(args.bytes)
            for offset in range(0, args.bytes, hardware.buffer_size):
                hardware.transfer(min(hardware.buffer_size, args.bytes-offset))
            result = hardware.result()
            elapsed = time.perf_counter_ns() - started
            if result["digest"] != expected:
                raise RuntimeError(f"{name} PL hash mismatch")
            dma_samples.append(elapsed); core_cycles.append(result["core_cycles"])
            software = function(); started = time.perf_counter_ns()
            for offset in range(0, args.bytes, hardware.buffer_size):
                software.update(pattern[:min(hardware.buffer_size, args.bytes-offset)])
            digest = software.hexdigest()
            software_samples.append(time.perf_counter_ns()-started)
            if digest != expected:
                raise RuntimeError("ARM reference mismatch")
        for _ in range(args.repeats-1):
            hardware.select("sha256" if name != "sha256" else "sha3")
            load_samples.append(hardware.select(name))
        report["algorithms"][name] = {
            "manager_load_samples_ns": load_samples,
            "manager_load_median_ns": statistics.median(load_samples),
            "manager_load_scope": "FPGA Manager call including firmware retrieval, PCAP transfer and driver completion; zero means image already selected",
            "dma_and_core_samples_ns": dma_samples, "core_cycles": core_cycles,
            "dma_and_core_median_MB_s": args.bytes * 1000 / statistics.median(dma_samples),
            "arm_software_samples_ns": software_samples,
            "arm_software_median_MB_s": args.bytes * 1000 / statistics.median(software_samples),
            "digest": expected,
        }
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(args.output)
finally:
    hardware.close()
