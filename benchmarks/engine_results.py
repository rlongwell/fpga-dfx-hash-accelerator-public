#!/usr/bin/env python3
"""Summarize recorded reports without replacing failed timing with a prediction."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
def engine_sources(engine):
    sources = [root / "rtl/common/axis_bytes.sv", root / f"rtl/rm/{engine}.sv"]
    sources.append(root / (f"rtl/sha3/experiments/hash_{engine}.sv" if engine.startswith("sha3_")
                           else f"rtl/{engine}/hash_{engine}.sv"))
    return sources

if len(sys.argv) == 3 and sys.argv[1] == "--capture":
    engine = sys.argv[2]
    if engine not in {"sha3", "sha256", "blake2s", "sha3_wide", "sha3_serial", "sha3_fast", "sha3_compact"}:
        raise SystemExit("Unknown engine")
    destination = root / f"build/engines/{engine}/sources_sha256.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in engine_sources(engine)}, indent=2) + "\n")
    raise SystemExit(0)

rows = []
for result in sorted((root / "results/engines").glob("*/summary.tsv")):
    engine = result.parent.name
    fields = dict(line.split("\t", 1) for line in result.read_text().splitlines())
    utilization = (result.parent / "routed_utilization.rpt").read_text()
    def resource(label):
        match = re.search(r"\|\s*" + re.escape(label) + r"\*?\s*\|\s*([\d.]+)", utilization)
        if not match:
            raise ValueError(f"Missing {label} in {result.parent}")
        return float(match[1]) if "." in match[1] else int(match[1])
    simulation = (result.parent / "simulation.log").read_text()
    if "ALL PASS vectors=79 modes=2 framing_errors=5 abort_cases=2" not in simulation:
        raise ValueError(f"Missing passing test completion for {engine}")
    match = re.search(r"random_1048576 length=1048576 continuous_cycles=(\d+) stressed_cycles=(\d+)", simulation)
    cycles = int(match[1])
    period = float(fields["period_ns"])
    setup = float(fields["setup_wns_ns"])
    hold = float(fields["hold_whs_ns"])
    register_slack = float(fields["register_setup_wns_ns"])
    lut = resource("Slice LUTs")
    timing_met = setup >= 0 and hold >= 0
    row = {
        "engine": engine, "historical": engine.endswith(("_pre_commit", "_pre_prefetch")),
        "analysis_type": fields.get("analysis_type", "synthesized, placed and routed at constrained clock"),
        "part": fields["part"], "vivado": fields["vivado"],
        "clock_period_ns": period, "input_delay_ns": float(fields["input_delay_ns"]),
        "output_delay_ns": float(fields["output_delay_ns"]),
        "routed": {"lut": lut, "ff": resource("Slice Registers"),
                   "bram_tiles": resource("Block RAM Tile"), "dsp": resource("DSPs"),
                   "setup_wns_ns": setup, "hold_whs_ns": hold,
                   "register_setup_wns_ns": register_slack,
                   "register_data_path_delay_ns": float(fields["register_data_path_delay_ns"]),
                   "timing_met": timing_met,
                   "register_slack_clock_estimate_mhz": 1000 / (period-register_slack)},
        "simulation": {"vector_count": 79, "modes": 2, "message_bytes": 1048576,
                       "continuous_cycles": cycles, "stressed_cycles": int(match[2])},
        "predicted_core_MB_per_s_at_constrained_clock": 1048576 / cycles * 1000 / period if timing_met else None,
        "predicted_core_MB_per_s_per_LUT": 1048576 / cycles * 1000 / period / lut if timing_met else None,
        "sources_sha256": json.loads((result.parent / "sources_sha256.json").read_text()),
        "hardware_tested": False,
    }
    rows.append(row)
document = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "Out-of-context routed common-interface engines, including stream adapter; no PS, DMA, DFX pblock or Ethernet",
    "methodology": "Vivado 2024.2, xc7z020clg400-1, 2 ns IO, BUFGCTRL_X0Y0; synth rebuilt, opt/place/phys_opt/route defaults at 100 MHz. Rows explicitly marked clock reanalysis preserve the physical route and only change clock constraints.",
    "caveats": ["Core rates combine measured simulation cycles with a timing-closed constrained clock; they are predictions, not hardware measurements.",
                "Register-slack clock estimates are not frequency-sweep or hardware measurements.",
                "OOC ports have no physical partition-pin locations; register-to-register timing is the relevant internal metric, while real system timing requires the DFX top-level route.",
                "Oxide baseline has a byte input interface and no common-interface adapter; compare those boundary differences explicitly.",
                "Partial-reconfiguration timing, memory bandwidth and Ethernet throughput remain unmeasured."],
    "engines": rows,
}
destination = root / "results/engine_measurements.json"
destination.write_text(json.dumps(document, indent=2) + "\n")
print(f"Recorded {len(rows)} engines in {destination}")
