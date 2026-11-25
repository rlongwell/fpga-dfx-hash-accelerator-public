#!/usr/bin/env python3
"""Physical profiling with untimed references, warmup and individual samples."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0, "/opt/zybo/hash/software")
from hash_local import LocalHasher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--algorithms", nargs="+", default=["sha3"])
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oxide", action="store_true", help="upstream cannot encode empty input")
    args = parser.parse_args()
    assert platform.machine().startswith("arm")
    assert args.repeats >= 3
    references = {"sha3": hashlib.sha3_256, "sha256": hashlib.sha256, "blake2s": hashlib.blake2s}
    manifest = json.loads(args.manifest.read_text())
    report = {"label": args.label, "kind": "physical-zybo-performance", "manifest": manifest,
              "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "kernel": platform.release(), "python": platform.python_version(),
              "cpuinfo": Path("/proc/cpuinfo").read_text(), "repeats": args.repeats,
              "bench_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "warmup_per_method": 1, "algorithms": {}, "correctness": [],
              "timing_scope": "Wall time includes Python/ioctl costs. DMA reuses prefilled coherent DDR; local API includes PS copies. Reference hashing outside hardware timing. ARM uses preallocated RAM. No Ethernet or disk I/O in timed regions.",
              "core_counter_scope": "100 MHz static shell START-to-result cycles, including starvation and DMA/software gaps; not compute-only cycles.",
              "environment": "Normal board scheduling; no CPU affinity, governor change or thermal stabilization."}
    for relative in ["/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq",
                     "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"]:
        path = Path(relative)
        if path.is_file(): report[relative] = path.read_text().strip()
    pattern = bytes(range(256))
    def payload(n): return (pattern * ((n + 255) // 256))[:n]

    class ShortReader(io.BytesIO):
        def readinto(self, target): return super().readinto(target[:13])

    try:
        with LocalHasher(manifest=args.manifest) as hasher:
            hardware = hasher._hardware
            report["buffer_size"] = hardware.buffer_size
            # Identical algorithm IDs cannot distinguish implementations; force
            # a different algorithm first, then verify/load this manifest's file.
            hardware.select("sha256")
            report["initial_manager_load_ns"] = hardware.select("sha3")
            assert report["initial_manager_load_ns"] > 0
            for algorithm in args.algorithms:
                reference = references[algorithm]
                hardware.select(algorithm)
                for n in [0, 1, 7, 8, 9, 55, 56, 63, 64, 65, 127, 128, 129, 135, 136,
                          137, 271, 272, 273, 4095, 4096, 4097, 1048575, 1048576, 1048577, 2097169]:
                    if args.oxide and not n: continue
                    data = payload(n)
                    result = hasher.hash_bytes(data, algorithm)
                    assert result["digest"] == reference(data).hexdigest(), (algorithm, n, result)
                    report["correctness"].append(dict(bytes=n, **result))
                data = payload(4099)
                source = ShortReader(data + b"tail")
                result = hasher.hash_stream(source, len(data), algorithm)
                assert result["digest"] == reference(data).hexdigest() and source.read() == b"tail"
                report["correctness"].append(dict(case="short-reads", bytes=len(data), **result))
                rows = []
                for n in [64, 136, 1024, 65536, 1048576, 16777216]:
                    data = payload(n)
                    expected = reference(data).hexdigest()
                    hardware.buffer[:] = payload(hardware.buffer_size)
                    samples = {"dma": [], "local_api": [], "arm": []}
                    for method in samples:
                        for repetition in range(args.repeats + 1):
                            started = time.perf_counter_ns()
                            if method == "dma":
                                hardware.start(n)
                                for offset in range(0, n, hardware.buffer_size):
                                    hardware.transfer(min(n-offset, hardware.buffer_size))
                                result = hardware.result()
                            elif method == "local_api":
                                result = hasher.hash_bytes(data, algorithm)
                            else:
                                result = {"digest": reference(data).hexdigest()}
                            elapsed = time.perf_counter_ns() - started
                            assert result["digest"] == expected, (algorithm, method, n, result)
                            if repetition:
                                samples[method].append({"ns": elapsed, "core_cycles": result.get("core_cycles")})
                    row = {"bytes": n, "digest": expected, "samples": samples, "summary": {}}
                    for method, values in samples.items():
                        times = [sample["ns"] for sample in values]
                        median = statistics.median(times)
                        row["summary"][method] = {"median_ns": median, "min_ns": min(times),
                                                   "max_ns": max(times), "MB_s": n * 1000 / median}
                    rows.append(row)
                    print(args.label, algorithm, n, json.dumps(row["summary"]), flush=True)
                report["algorithms"][algorithm] = rows
            # Non-destructive midstream abort followed by recovery and DFX back.
            try:
                hasher.hash_stream(io.BytesIO(payload(1048577)), 1048578, "sha3")
            except EOFError:
                report["abort_rejected"] = True
            else:
                raise AssertionError("truncated message accepted")
            assert hasher.hash_bytes(b"recovery", "sha3")["digest"] == hashlib.sha3_256(b"recovery").hexdigest()
            hardware.select("sha256")
            report["return_manager_load_ns"] = hardware.select("sha3")
            assert report["return_manager_load_ns"] > 0
            assert hasher.hash_bytes(b"return", "sha3")["digest"] == hashlib.sha3_256(b"return").hexdigest()
            report["passed"] = True
    except BaseException as error:
        report["passed"] = False
        report["error"] = repr(error)
        raise
    finally:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print("REPORT", args.output, "passed", report.get("passed"), flush=True)


if __name__ == "__main__":
    main()
