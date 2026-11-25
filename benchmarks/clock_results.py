#!/usr/bin/env python3
"""Publish a clock reanalysis separately from the 100 MHz implementation table."""
import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--build-dir", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
fields = dict(line.split("\t", 1) for line in (args.build_dir / "summary.tsv").read_text().splitlines())
engine = fields["engine"]
base = root / "results/engines" / engine
period = float(fields["period_ns"])
setup, hold = float(fields["setup_wns_ns"]), float(fields["hold_whs_ns"])
coverage_text = (args.build_dir / "clock_coverage.rpt").read_text()
coverage = {name: int(count) for name, count in re.findall(r"checking (\w+) \((\d+)\)", coverage_text)}
if coverage.get("no_clock") or coverage.get("unconstrained_internal_endpoints"):
    raise SystemExit("Unconstrained sequential logic; do not publish a throughput prediction")
simulation_text = (base / "simulation.log").read_text()
messages = []
for size in (65536, 1048576):
    match = re.search(rf"random_{size} length={size} continuous_cycles=(\d+)", simulation_text)
    cycles = int(match[1])
    messages.append({"message_bytes": size, "continuous_cycles": cycles,
                     "predicted_core_MB_per_s": size / cycles * 1000 / period if setup >= 0 and hold >= 0 else None})
args.output_dir.mkdir(parents=True, exist_ok=True)
for name in ("summary.tsv", "clocks.rpt", "clock_coverage.rpt", "routed_timing.rpt",
             "routed_register_timing.rpt", "routed_utilization.rpt", "route_status.rpt"):
    shutil.copyfile(args.build_dir / name, args.output_dir / name)
document = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "engine": engine, "part": fields["part"], "vivado": fields["vivado"],
    "analysis_type": fields["analysis_type"],
    "analysis_clock_mhz": 1000 / period, "physical_route_clock_mhz": 100.0,
    "physical_route_changed": False, "rtl_changed": False,
    "input_delay_ns": float(fields["input_delay_ns"]),
    "output_delay_ns": float(fields["output_delay_ns"]),
    "hd_clk_src": "BUFGCTRL_X0Y0",
    "timing": {"setup_wns_ns": setup, "hold_whs_ns": hold,
               "register_setup_wns_ns": float(fields["register_setup_wns_ns"]),
               "register_data_path_delay_ns": float(fields["register_data_path_delay_ns"]),
               "timing_met": setup >= 0 and hold >= 0},
    "clock_coverage": coverage,
    "intentional_timing_exception": "aresetn is false-pathed and has no input-delay constraint; all sequential data endpoints are clocked and constrained",
    "simulation": messages,
    "sources_sha256": json.loads((base / "sources_sha256.json").read_text()),
    "checkpoint": str((args.build_dir / "clock_reanalysis.dcp").resolve().relative_to(root)),
    "hardware_tested": False,
    "caveats": ["This reanalyzes an unchanged route at a slower clock; it is not a separately implemented 80 MHz design or a DFX configuration.",
                "Core rates are predictions from simulated cycles and timing analysis, not hardware, DMA or Ethernet measurements.",
                "OOC input/output paths lack physical partition-pin locations; deployed system timing requires its own route."],
}
destination = args.output_dir / "analysis.json"
destination.write_text(json.dumps(document, indent=2) + "\n")
print(destination)
