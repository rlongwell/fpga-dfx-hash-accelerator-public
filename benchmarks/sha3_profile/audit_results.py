#!/usr/bin/env python3
"""Audit retained measurements from a source checkout; never access the board.

The default checks published evidence and source files. --build-artifacts also
requires the original ignored checkpoints/bitstreams. Neither mode repeats a
physical experiment or provides independent attestation of its capture.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "results/sha3-performance-20261115"
sys.path.insert(0, str(ROOT))
from scripts.vivado.dfx_manifest import route_counts, timing, utilization


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def relative_source(name):
    """Map a captured workstation path to this checkout without changing it."""
    path = Path(name)
    if path.is_absolute():
        marker = "fpga-dfx-hash-accelerator"
        require(marker in path.parts, "Unrecognized captured source path: " + name)
        path = Path(*path.parts[path.parts.index(marker) + 1:])
    require(bool(path.parts) and ".." not in path.parts, "Invalid source path: " + name)
    return path


def verify_ledger(ledger, base, allow_build=False):
    verified, omitted = set(), set()
    for line in ledger.read_text().splitlines():
        expected, name = line.split("  ", 1)
        relative = relative_source(name)
        if relative.parts[0] == "build" and not allow_build:
            omitted.add(str(relative))
            continue
        path = base / relative
        require(digest(path) == expected, "Checksum mismatch: " + str(path))
        verified.add(str(relative))
    return verified, omitted


def audit_row(row, algorithm, repeats=7):
    length = row["bytes"]
    require(isinstance(length, int) and 0 < length <= 16777216, "Invalid measured length")
    pattern = bytes(range(256))
    data = (pattern * ((length + 255) // 256))[:length]
    reference = {"sha3": hashlib.sha3_256, "sha256": hashlib.sha256,
                 "blake2s": hashlib.blake2s}[algorithm]
    require(row["digest"] == reference(data).hexdigest(), "Measured digest mismatch")
    require(set(row["samples"]) == {"dma", "local_api", "arm"}, "Missing timing method")
    for method, samples in row["samples"].items():
        require(len(samples) == repeats, "Wrong number of measured repetitions")
        times = [sample["ns"] for sample in samples]
        require(all(isinstance(n, int) and n > 0 for n in times), "Invalid duration")
        if method != "arm":
            require(all(isinstance(s["core_cycles"], int) and s["core_cycles"] > 0
                        for s in samples), "Missing physical cycle counter")
        expected = {"median_ns": statistics.median(times), "min_ns": min(times),
                    "max_ns": max(times), "MB_s": length * 1000 / statistics.median(times)}
        for key, value in expected.items():
            require(math.isclose(row["summary"][method][key], value, rel_tol=1e-12),
                    f"Stored {method} {key} disagrees with raw samples")


def audit(build_artifacts=False):
    # The capture bundle remains unchanged when review documentation evolves.
    sealed, _ = verify_ledger(EVIDENCE / "SHA256SUMS", EVIDENCE, True)
    source = read(ROOT / "reference/oxide/SOURCE.json")
    for entry in source["files"]:
        path = ROOT / "reference/oxide" / entry["path"]
        require(digest(path) == entry["sha256"], "Changed upstream file: " + entry["path"])
        if path.suffix == ".vhd":
            require("Mozilla Public" in path.read_text(), "Missing upstream license notice")
    require(digest(ROOT / "reference/oxide/MPL-2.0.txt") == source["license_sha256"],
            "Changed MPL license text")
    derivative = read(ROOT / "rtl/sha3/oxide_no_digest/SOURCE.json")
    require(digest(ROOT / "rtl/sha3/oxide_no_digest/sha3_256.vhd") == derivative["modified_sha256"],
            "Changed separately licensed derivative")

    manifest_paths = {
        "current": "original_manifest.json", "fast": "fast/manifest.json",
        "compact": "compact/manifest.json", "compact-postboot": "promoted_manifest.json",
        "oxide": "oxide/manifest.json", "oxide_elastic": "oxide_elastic/runtime_manifest.json",
    }
    reports, measured_rows = {}, 0
    benchmark_sha = digest(ROOT / "benchmarks/sha3_profile/run_board.py")
    for label, manifest_name in manifest_paths.items():
        report = read(EVIDENCE / f"{label}-physical.json")
        require(report["passed"] is True and report["kind"] == "physical-zybo-performance",
                "Unaccepted physical report: " + label)
        require(report["bench_source_sha256"] == benchmark_sha, "Benchmark source changed")
        require(report["manifest_sha256"] == digest(EVIDENCE / manifest_name), "Manifest identity mismatch")
        require(report["manifest"] == read(EVIDENCE / manifest_name), "Manifest content mismatch")
        require(report["kernel"] == "6.6.40-dfx-hash" and report["buffer_size"] == 1048576,
                "Different kernel or buffer size")
        require(report["repeats"] == 7 and report["warmup_per_method"] == 1, "Different sampling policy")
        require(report["abort_rejected"] and report["initial_manager_load_ns"] > 0
                and report["return_manager_load_ns"] > 0, "Missing abort or DFX evidence")
        for algorithm, rows in report["algorithms"].items():
            require([r["bytes"] for r in rows] == [64, 136, 1024, 65536, 1048576, 16777216],
                    "Unexpected measurement sizes")
            for row in rows:
                audit_row(row, algorithm)
                measured_rows += 1
        reports[label] = report

    verified, omitted = set(), set()
    for variant in ["fast", "compact", "oxide", "oxide_elastic"]:
        directory = EVIDENCE / variant
        record = read(directory / "implementation.json")
        require(record["clock_mhz"] == 100, "Different implementation clock")
        for key, instance in [("rp", "u_hash"), ("total", "system_top")]:
            require(record[key] == utilization(directory / "routed_utilization.rpt", instance),
                    "Resource summary disagrees with routed report")
        require(record["timing"] == timing(directory / "routed_timing.rpt"), "Timing summary mismatch")
        require(record["routing"] == route_counts(directory / "route_status.rpt"), "Routing summary mismatch")
        for algorithm in ["sha3", "sha256", "blake2s"]:
            text = (directory / f"pr_verify_{algorithm}.rpt").read_text()
            require("are compatible" in text and "ERROR:" not in text, "Missing static compatibility")
        got, skipped = verify_ledger(directory / "sources.sha256", ROOT, build_artifacts)
        verified.update(got)
        omitted.update(skipped)
        require(reports[variant]["manifest"]["images"]["sha3"] == record["partial"],
                "Measured partial differs from implemented partial")
    # Verify the retained parent ledger for post-route optimization as well.
    got, skipped = verify_ledger(EVIDENCE / "oxide_elastic/parent-sources.sha256", ROOT, build_artifacts)
    verified.update(got)
    omitted.update(skipped)
    got, skipped = verify_ledger(EVIDENCE / "artifacts.sha256", ROOT, build_artifacts)
    verified.update(got)
    omitted.update(skipped)

    summary = read(EVIDENCE / "summary.json")
    for name, report_name in [("current", "current"), ("oxide_elastic", "oxide_elastic"),
                              ("compact", "compact-postboot")]:
        row = reports[report_name]["algorithms"]["sha3"][-1]
        for key, method in [("dma_MB_s", "dma"), ("local_api_MB_s", "local_api")]:
            require(summary[name][key] == row["summary"][method]["MB_s"], "Headline rate mismatch")
        area = (read(ROOT / "results/dfx_summary.json")["configurations"]["sha3"] if name == "current"
                else read(EVIDENCE / name / "implementation.json"))
        require(summary[name]["rp_luts"] == area["rp"]["luts"]
                and summary[name]["rp_ffs"] == area["rp"]["ffs"], "Headline area mismatch")
    postboot = read(EVIDENCE / "promoted-local-physical.json")
    manifest = read(EVIDENCE / "promoted_manifest.json")
    require(postboot["passed"] is True and len(postboot["jobs"]) == 81, "Post-boot acceptance failed")
    require(postboot["files_sha256"]["/boot/profiles/hash/system.bit"] == manifest["static_sha256"],
            "Booted full image identity mismatch")
    require(postboot["files_sha256"]["/opt/zybo/hash/dfx_manifest.json"] == digest(EVIDENCE / "promoted_manifest.json"),
            "Booted manifest identity mismatch")
    return {"passed": True, "kind": "offline-audit-of-retained-evidence", "hardware_rerun": False,
            "sealed_files": len(sealed), "physical_reports_checked": len(reports),
            "measurement_rows_recomputed": measured_rows, "source_files_checked": len(verified),
            "build_artifacts_checked": build_artifacts,
            "build_paths_not_checked": sorted(omitted),
            "dma_speedup_vs_oxide": summary["compact"]["dma_MB_s"] / summary["oxide_elastic"]["dma_MB_s"],
            "LUT_reduction_percent": 100 * (1 - summary["compact"]["rp_luts"] / summary["oxide_elastic"]["rp_luts"]),
            "FF_reduction_percent": 100 * (1 - summary["compact"]["rp_ffs"] / summary["oxide_elastic"]["rp_ffs"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-artifacts", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.build_artifacts)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")
