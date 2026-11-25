#!/usr/bin/env python3
"""Export only timing-closed, statically compatible SHA3 comparison images."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/vivado"))
from dfx_manifest import utilization, timing, route_counts


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_sources(ledger, seen=None):
    seen = set() if seen is None else seen
    ledger = ledger.resolve()
    if ledger in seen:
        return
    seen.add(ledger)
    for line in ledger.read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = Path(name)
        if digest(path) != expected:
            raise ValueError("Build input changed: " + name)
        if path.name.endswith("sources.sha256"):
            check_sources(path, seen)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=["fast", "oxide", "oxide_elastic", "compact"])
    parser.add_argument("--build", type=Path, help="alternate implementation directory")
    args = parser.parse_args()
    build = args.build.resolve() if args.build else ROOT / "build/sha3-profile" / args.variant
    output = ROOT / "results/sha3-performance-20261115" / args.variant
    output.mkdir(parents=True, exist_ok=True)
    # These sources and checkpoints are checked before Vivado writes images.
    check_sources(build / "sources.sha256")
    for name in ["sha3", "sha256", "blake2s"]:
        report = (build / f"pr_verify_{name}.rpt").read_text()
        if "are compatible" not in report or "ERROR:" in report:
            raise ValueError("Static compatibility not established")
    metrics = timing(build / "routed_timing.rpt")
    routes = route_counts(build / "route_status.rpt")
    full = build / "full.bit"
    partial = build / "full_pblock_hash_partial.bit.bin"
    raw = partial.read_bytes()
    if len(raw) % 4 or b"\x66\x55\x99\xaa" not in raw[:128]:
        raise ValueError("Invalid PCAP image encoding")
    # Base manifest remains the known-good, original three-image deployment.
    base = ROOT / "build/vivado/dfx/manifest.json"
    manifest = json.loads(base.read_text())
    manifest["images"]["sha3"] = {
        "algorithm_id": 1,
        "filename": f"fpga-dfx-hash/{manifest['static_sha256'][:12]}/sha3-{args.variant}-{digest(partial)[:12]}.bin",
        "source": str(partial.relative_to(ROOT)), "sha256": digest(partial)}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    placement = re.search(r"^# place_design -directive (\S+)", (build / "console.log").read_text(), re.M)
    flow_path = next(Path(line.split("  ", 1)[1]) for line in (build / "sources.sha256").read_text().splitlines()
                     if line.endswith(".tcl"))
    inherited_placement = re.search(r"^# SOURCE_PLACEMENT (\S+)", flow_path.read_text(), re.M)
    retained = re.search(r"^RETAINED_OXIDE_CORE_PLACEMENT (\d+)", (build / "console.log").read_text(), re.M)
    record = {"variant": args.variant, "clock_mhz": 100, "part": "xc7z020clg400-1",
              "build_directory": str(build.relative_to(ROOT)),
              "placement_directive": placement[1] if placement else inherited_placement[1] if inherited_placement else "Default",
              "post_route_physical_optimization": "AggressiveExplore" if "Command: phys_opt_design -directive AggressiveExplore" in (build / "console.log").read_text() else None,
              "native_core_placements_retained": int(retained[1]) if retained else 0,
              "timing": metrics, "routing": routes,
              "total": utilization(build / "routed_utilization.rpt", "system_top"),
              "rp": utilization(build / "routed_utilization.rpt", "u_hash"),
              "full_bit": {"source": str(full.relative_to(ROOT)), "sha256": digest(full)},
              "partial": manifest["images"]["sha3"], "base_static_sha256": manifest["static_sha256"],
              "scope": "Routed variant against original locked static; full pr_verify against all three accepted configurations",
              "physical_tested": False}
    (output / "implementation.json").write_text(json.dumps(record, indent=2) + "\n")
    for path in build.glob("*.rpt"):
        shutil.copy2(path, output / path.name)
    shutil.copy2(build / "sources.sha256", output / "sources.sha256")
    (build / "partial.bin.gz").write_bytes(gzip.compress(raw, mtime=0))
    print(output / "manifest.json")
    print("PCAP SHA-256", digest(partial), "gzip bytes", (build / "partial.bin.gz").stat().st_size)


if __name__ == "__main__":
    main()
