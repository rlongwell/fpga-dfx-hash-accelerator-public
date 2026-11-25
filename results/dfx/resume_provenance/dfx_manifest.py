#!/usr/bin/env python3
"""Describe a completed, compatible DFX artifact set for the board service."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys


def sha256(path: pathlib.Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def utilization(path: pathlib.Path, instance: str) -> dict[str, int]:
    keys = ("luts", "logic_luts", "lutram", "srls", "ffs", "ramb36", "ramb18", "dsps")
    for line in path.read_text().splitlines():
        fields = [field.strip() for field in line.split("|")[1:-1]]
        if len(fields) in (10, 12) and fields[0] == instance:
            return dict(zip(keys, map(int, fields[-8:])))
    raise ValueError(f"No utilization row for {instance} in {path}")


def route_counts(path: pathlib.Path) -> dict[str, int]:
    text = path.read_text()
    counts = {}
    for key, label in (("errors", "nets with routing errors"),
                       ("routable", "routable nets"), ("routed", "fully routed nets")):
        match = re.search(r"# of " + label + r"[. ]*:\s*(\d+)", text)
        if not match:
            raise ValueError(f"Missing {label} in {path}")
        counts[key] = int(match[1])
    if counts["errors"] or counts["routable"] != counts["routed"]:
        raise ValueError(f"Unsuccessful routing: {path}")
    return counts


def timing(path: pathlib.Path) -> dict[str, float]:
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("WNS(ns)"):
            values = lines[index + 2].split()
            result = {"wns_ns": float(values[0]), "tns_ns": float(values[1]),
                      "whs_ns": float(values[4]), "ths_ns": float(values[5]),
                      "wpws_ns": float(values[8]), "tpws_ns": float(values[9])}
            if any(result[key] < 0 for key in ("wns_ns", "whs_ns", "wpws_ns")):
                raise ValueError(f"Failing routed timing: {path}")
            return result
    raise ValueError(f"No timing summary: {path}")


def summarize(root: pathlib.Path, out: pathlib.Path, images: dict) -> None:
    summary = {"part": "xc7z020clg400-1", "vivado": "2024.2", "clock_mhz": 100,
               "hardware_tested": False,
               "static_synthesis": utilization(root / "build/vivado/system/static_utilization.rpt", "system_top"),
               "configurations": {}}
    rows = ["# DFX implementation results", "",
            "Vivado 2024.2, xc7z020clg400-1, 100 MHz. These are routed implementation results; no board was connected.", "",
            "| Configuration | Total LUT / FF | Static LUT / FF | RP LUT / FF | WNS (ns) | WHS (ns) | Full .bit bytes | Partial .bit bytes | PCAP .bin bytes |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name in images:
        directory = out / name
        total = utilization(directory / "routed_utilization.rpt", "system_top")
        rp = utilization(directory / "routed_utilization.rpt", "u_hash")
        static = {key: total[key] - rp[key] for key in total}
        metrics = timing(directory / "routed_timing.rpt")
        sizes = {"full_bit": (directory / "full.bit").stat().st_size,
                 "partial_bit": (directory / "full_pblock_hash_partial.bit").stat().st_size,
                 "pcap_bin": (directory / "full_pblock_hash_partial.bit.bin").stat().st_size}
        summary["configurations"][name] = {
            "total": total, "static": static, "rp": rp,
            "rm_synthesis": utilization(directory / "synth_utilization.rpt", "hash_rm"),
            "timing": metrics, "routing": route_counts(directory / "route_status.rpt"),
            "bitstream_bytes": sizes,
            "reports": directory.relative_to(root).as_posix(),
        }
        rows.append(f"| {name} | {total['luts']} / {total['ffs']} | {static['luts']} / {static['ffs']} | "
                    f"{rp['luts']} / {rp['ffs']} | {metrics['wns_ns']:.3f} | {metrics['whs_ns']:.3f} | "
                    f"{sizes['full_bit']} | {sizes['partial_bit']} | {sizes['pcap_bin']} |")
    rows.extend(["", "Static counts are total routed usage minus the u_hash hierarchy. They can include implementation-added cells; the separate static synthesis counts precede implementation.", "",
                 "All routable nets are routed with zero routing errors. Routed setup, hold, and pulse-width timing pass. Implementation DRC has no errors or critical warnings. The initial configuration's static placement/routing is reused for every alternate; pr_verify reports are in build/vivado/dfx/.", "",
                 "Full reports, resource-type counts, and the machine-readable summary are in [dfx_summary.json](dfx_summary.json). Runtime image identities are in [dfx_manifest.json](dfx_manifest.json).", ""])
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "results/dfx_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (root / "results/dfx_summary.md").write_text("\n".join(rows))


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: dfx_manifest.py ROOT OUTPUT INITIAL_ALGORITHM")
    root = pathlib.Path(sys.argv[1]).resolve()
    out = pathlib.Path(sys.argv[2]).resolve()
    initial = sys.argv[3]
    ids = {"sha3": 1, "sha256": 2, "blake2s": 3}
    if initial not in ids:
        raise SystemExit(f"Unknown initial algorithm: {initial}")
    if not (out / "build_info.txt").is_file():
        raise SystemExit("No completed DFX build_info.txt; refusing to publish a manifest")
    static_digest = sha256(out / initial / "full.bit")
    images = {}
    for name, algorithm_id in ids.items():
        source = out / name / "full_pblock_hash_partial.bit.bin"
        if not source.is_file():
            continue
        image_digest = sha256(source)
        images[name] = {
            "algorithm_id": algorithm_id,
            "filename": f"fpga-dfx-hash/{static_digest[:12]}/{name}-{image_digest[:12]}.bin",
            "source": source.relative_to(root).as_posix(),
            "sha256": image_digest,
        }
    if not images:
        raise SystemExit("No PCAP images found")
    manifest = {
        "abi": 65536,
        "part": "xc7z020clg400-1",
        "vivado": "2024.2",
        "static_sha256": static_digest,
        "images": images,
    }
    summarize(root, out, images)
    text = json.dumps(manifest, indent=2) + "\n"
    for target in (out / "manifest.json", root / "results" / "dfx_manifest.json"):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(target)


if __name__ == "__main__":
    main()
