#!/usr/bin/env python3
"""Assemble measured implementation evidence; never fill absent hardware results."""
import csv
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
results = root / "results"
rows = []
for variant, label in [("baseline", "Oxide original"), ("oxide_no_digest", "Oxide without digest register")]:
    document = json.loads((results / f"{variant}_implementation.json").read_text())
    for config in document["configurations"]:
        db = str(config["double_buffer"]).lower()
        with (results / f"{variant}_db_{db}_gaps_false_cycles.csv").open() as source:
            cycles = next(int(row["total_cycles"]) for row in csv.DictReader(source)
                          if int(row["bytes"]) == 65536)
        frequency = 1000 / config["period_ns"]
        rate = 65536 * frequency / cycles if config["timing_met"] else None
        rows.append({"name": f"{label}, {'double' if config['double_buffer'] else 'single'} buffer",
                     "lut": config["routed"]["lut"], "ff": config["routed"]["ff"],
                     "bram": config["routed"]["bram_tile"], "dsp": config["routed"]["dsp"],
                     "slack": config["setup_wns_ns"], "cycles": cycles, "rate": rate})

engines = json.loads((results / "engine_measurements.json").read_text())
names = {"sha3": "SHA3 direct byte absorption", "sha256": "SHA-256",
         "blake2s": "BLAKE2s-256", "sha3_wide": "SHA3 wide absorption",
         "sha3_serial": "SHA3 shared lane/row rounds", "sha3_fast": "SHA3 wide, registered framing", "sha3_compact": "SHA3 wide, compact padding"}
for engine in engines["engines"]:
    if engine.get("historical"):
        continue
    name = engine["engine"]
    text = (results / "engines" / name / "simulation.log").read_text()
    cycles = int(re.search(r"random_65536 length=65536 continuous_cycles=(\d+)", text)[1])
    physical = engine["routed"]
    rate = 65536 * 1000 / engine["clock_period_ns"] / cycles if physical["timing_met"] else None
    rows.append({"name": names[name], "lut": physical["lut"], "ff": physical["ff"],
                 "bram": physical["bram_tiles"], "dsp": physical["dsp"],
                 "slack": physical["setup_wns_ns"], "cycles": cycles, "rate": rate})

lines = ["# Measured comparison", "",
         "Vivado 2024.2, xc7z020clg400-1, 100 MHz target, standalone out-of-context implementations. "
         "LUT/FF/BRAM/DSP and slack come from routed reports. File rates are **predictions from simulation cycles at the constrained clock**, not board measurements. "
         "Decimal MB/s is used throughout.", "",
         "All table rates use a 65,536-byte message with continuous source traffic. "
         "At 100 MHz, the corresponding predicted latency in microseconds is the listed cycle count divided by 100. "
         "Oxide latency starts at its first accepted byte; common-interface engines include their explicit start. "
         "The Oxide rows expose the original byte interface, whereas SystemVerilog rows include their 64-bit stream adapter and length checking. "
         "Compare the isolated digest-storage change within the Oxide pair, and the original RTL experiments within the common-interface group. "
         "There is no claim that a wide AXI port alone improves a byte core.", "",
         "| Implementation | LUT | FF | BRAM | DSP | Setup slack, ns | Cycles / 64 KiB | Predicted MB/s | MB/s per LUT |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
for row in rows:
    rate = f"{row['rate']:.3f}" if row["rate"] is not None else "timing failed"
    efficiency = f"{row['rate']/row['lut']:.5f}" if row["rate"] is not None else "—"
    lines.append(f"| {row['name']} | {row['lut']:,} | {row['ff']:,} | {row['bram']} | {row['dsp']} | "
                 f"{row['slack']:+.3f} | {row['cycles']:,} | {rate} | {efficiency} |")
lines += ["", "## What the measurements establish", "",
          "The minimal Oxide modification removes redundant digest storage while preserving valid digest behavior and measured cycle counts. "
          "Single-buffer routing saves 135 LUTs and 265 FFs; double buffering saves 183 LUTs and 255 FFs. "
          "The different FF deltas reflect synthesis transformations, rather than an assumption that every removed bit maps one-for-one to a flip-flop.", "",
          "Direct state absorption removes the large input buffer and lowers storage, but the measured common-interface byte design uses more LUTs than the original byte-input baseline. "
          "The wide and shared-datapath rows retain their measured tradeoffs, including any negative result; fewer arithmetic units are not automatically fewer FPGA resources.", "",
          "At 100 MHz, a 24-cycle Keccak permutation has a theoretical capacity of 4.167 million permutations/s (566.667 MB/s of SHA3 rate blocks if absorption were free). "
          "The 744-cycle serialized permutation has 0.1344 million permutations/s (18.280 MB/s of rate blocks). "
          "These datapath capacities exclude absorption, padding, stream buffering, DMA, and networking, and must not be substituted for file throughput.", "",
          "All compared flows use the same part, tool version, 10 ns clock, 2 ns input/output budgets, BUFGCTRL_X0Y0 OOC clock source, "
          "rebuilt synthesis hierarchy, and default opt/place/phys_opt/route stages. The Oxide pair used four tool threads; the common-interface group used two. "
          "OOC external pins have no physical partition-pin placement, so internal register timing is also recorded separately. "
          "Frequencies inferred from one routed slack value are estimates, not measured maximum clocks; no frequency sweep was performed.", "",
          "[Routing congestion evidence](congestion.md) preserves the actual post-placement regional estimates and final global routing-resource percentages. "
          "These are separate from the zero-routing-error acceptance checks.", "",
          "The original SHA-256 final-round accumulation missed 100 MHz. The retained negative result is in `engines/sha256_pre_commit/`; "
          "the current core adds one chaining-state commit clock per block and is independently reverified. "
          "The initial full-system framing path also missed timing; it was replaced with a registered remaining-byte counter before accepting programming images.", "",
          "The original BLAKE2s core passed standalone timing but missed 100 MHz inside the locked DFX system (-0.654 ns setup). "
          "Prefetching four scheduled message words during existing compression steps removes the message selection from the addition path. "
          "Its standalone implementation uses 1,122 more LUTs and 152 more FFs, with identical measured simulation cycle counts and improved internal timing. "
          "The previous standalone reports remain in `engines/blake2s_pre_prefetch/`; full-system acceptance is reported separately below.", "",
          "## Actual system and software scope", "",
          "[DFX implementation results](dfx_summary.md) report the complete PS7/DMA/static/RP design, its actual routed clock checks, "
          "compatible configurations, and image sizes. Those figures include infrastructure and are distinct from this core-only table.", ""]
x86 = results / "x86_software.json"
if x86.exists():
    software = json.loads(x86.read_text())
    lines += [f"Local software measurement: {software['cpu']}, Python {software['python']}, {software['openssl']}. "
              f"Each sample hashes {software['bytes']:,} in-memory bytes; {software['repeats']} repetitions per algorithm. "
              "Allocation, disk, and networking are excluded. Full sample times and start load are recorded in `x86_software.json`. "
              f"Measurement context: {software.get('measurement_context', 'not recorded')}.", "",
              "| x86 software | Median MB/s | Min–max milliseconds |", "| --- | ---: | ---: |"]
    for name, measurement in software["algorithms"].items():
        lines.append(f"| {name} | {measurement['median_MB_s']:.3f} | "
                     f"{measurement['min_ns']/1e6:.3f}–{measurement['max_ns']/1e6:.3f} |")
    lines.append("")
lines += ["Physical DDR-to-PL DMA, PCAP reconfiguration and ARM software measurements are retained separately in the "
          "[2026-11-15 board comparison](sha3-performance-20261115/comparison.md). External Ethernet throughput remains unmeasured. "
          "The Ethernet link's nominal 1 Gbit/s ceiling is 125 MB/s before protocol overhead. "
          "No desktop-x86 acceleration claim follows from these separate measurements.", "",
          "Regenerate this document with `python3 benchmarks/report.py` after the implementation and benchmark commands complete. "
          "Source hashes, full timing/resource reports, and test logs accompany the JSON evidence.", ""]
frequency_result = results / "sha3_wide_clock_80mhz/analysis.json"
if frequency_result.exists():
    frequency = json.loads(frequency_result.read_text())
    sample = next(row for row in frequency["simulation"] if row["message_bytes"] == 65536)
    lines += ["## Wide SHA3 at a lower clock", "",
              "The same completed wide-core route was reanalyzed at 80 MHz with the same 2 ns I/O budgets. "
              "Its RTL, placement, and routing were unchanged; this is a frequency tradeoff study, not another physical implementation or a production DFX configuration. "
              f"Setup slack is {frequency['timing']['setup_wns_ns']:+.3f} ns and hold slack is {frequency['timing']['hold_whs_ns']:+.3f} ns. "
              f"The simulated 64 KiB latency of {sample['continuous_cycles']:,} cycles predicts {sample['predicted_core_MB_per_s']:.3f} MB/s at 80 MHz. "
              "The 100 MHz failure remains in the comparison table above.", "",
              "This historical 80 MHz experiment is separate from the improved `sha3_fast` design, which registers framing validation and closes timing at 100 MHz in the existing static system. "
              "The higher predicted core rate does not measure DDR/DMA or Ethernet throughput. "
              "[Separate clock-analysis evidence](sha3_wide_clock_80mhz/analysis.json) includes coverage checks and checkpoint identity.", ""]
(results / "comparison.md").write_text("\n".join(lines))
for row in rows:
    row["message_bytes"] = 65536
    row["predicted_latency_us_at_100MHz"] = row["cycles"] / 100 if row["rate"] is not None else None
(results / "comparison.json").write_text(json.dumps({
    "scope": "Routed OOC resources; simulation-based core performance at 100 MHz; no hardware measurements",
    "implementations": rows}, indent=2) + "\n")
print(f"Wrote {len(rows)} measured implementation rows to results/comparison.md")
