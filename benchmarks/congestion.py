#!/usr/bin/env python3
"""Retain Vivado congestion estimates separately from final routing correctness."""
import json
import hashlib
import re
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
entries = []
paths = [(f"{variant}, double_buffer={mode}", root / "build/vivado" / f"{variant}_db_{mode}" / "vivado.log")
         for variant in ("baseline", "oxide_no_digest") for mode in ("false", "true")]
paths += [(engine, root / "build/engines" / engine / "vivado.log")
          for engine in ("sha3", "sha256", "blake2s", "sha3_wide", "sha3_serial")]
for name, default_path in paths:
    # A resumed implementation has its own log. Never use an interrupted run's
    # initial zero-utilization values merely because a later checkpoint exists.
    candidates = [p for p in default_path.parent.glob("*vivado.log") if p.is_file()]
    complete = []
    for candidate in candidates:
        content = candidate.read_text()
        success = content.rfind("route_design completed successfully")
        failed = re.findall(r"Number of Failed Nets\s*=\s*(\d+)", content[:success])
        overlap = re.findall(r"Number of Node Overlaps\s*=\s*(\d+)", content[:success])
        if success >= 0 and failed and overlap and failed[-1] == overlap[-1] == "0":
            complete.append(candidate)
    if not complete:
        continue
    path = max(complete, key=lambda p: p.stat().st_mtime_ns)
    text = path.read_text()
    text = text[:text.rfind("route_design completed successfully")]
    match = re.search(r"Post-Placement Estimated Congestion(.*?)Phase 4\.3\.1 Print Estimated Congestion", text, re.S)
    if not match:
        continue
    directions = re.findall(r"\|\s*(North|South|East|West)\|\s*(\d+x\d+)\|\s*(\d+x\d+)\|", match[1])
    vertical = re.findall(r"Global Vertical Routing Utilization\s*=\s*([\d.]+)\s*%", text)
    horizontal = re.findall(r"Global Horizontal Routing Utilization\s*=\s*([\d.]+)\s*%", text)
    if len(directions) != 4 or not vertical or not horizontal or not (path.parent / "routed.dcp").exists():
        continue
    evidence = root / "results/congestion_logs" / f"{path.parent.name}.log"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, evidence)
    entries.append({"implementation": name,
                    "post_placement_region_sizes": {d: {"global": g, "short": s} for d, g, s in directions},
                    "final_global_vertical_routing_utilization_percent": float(vertical[-1]),
                    "final_global_horizontal_routing_utilization_percent": float(horizontal[-1]),
                    "log": str(path.relative_to(root)),
                    "retained_log": str(evidence.relative_to(root)),
                    "log_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "route_completed_successfully": True,
                    "failed_nets": 0, "node_overlaps": 0})
document = {"scope": "Standalone OOC comparisons; not whole-system DFX routing",
            "interpretation": "Post-placement region dimensions are Vivado estimates, not congested-device percentages. Global routing utilization is separate from local congestion and final route correctness.",
            "implementations": entries}
(root / "results/congestion.json").write_text(json.dumps(document, indent=2) + "\n")
lines = ["# Routing congestion evidence", "",
         document["scope"] + ". " + document["interpretation"], "",
         "Each direction reports global/short region size exactly as printed by Vivado's post-placement estimator. "
         "Routing utilization uses the final reported global resource percentages. A completed route with zero overlaps is a correctness check, not a claim of zero congestion.", "",
         "| Implementation | North | South | East | West | Vertical use, % | Horizontal use, % |",
         "| --- | --- | --- | --- | --- | ---: | ---: |"]
for entry in entries:
    sizes = entry["post_placement_region_sizes"]
    directions = " | ".join(sizes[d]["global"] + "/" + sizes[d]["short"] for d in ("North", "South", "East", "West"))
    lines.append(f"| {entry['implementation']} | {directions} | "
                 f"{entry['final_global_vertical_routing_utilization_percent']:.3f} | "
                 f"{entry['final_global_horizontal_routing_utilization_percent']:.3f} |")
lines += ["", "The JSON record identifies the completed route log, its retained copy and SHA-256. "
          "Interrupted logs cannot supply a final utilization result. "
          "Regenerate with `python3 benchmarks/congestion.py` after routing finishes.", ""]
(root / "results/congestion.md").write_text("\n".join(lines))
print(f"Recorded {len(entries)} routed implementation congestion estimates")
