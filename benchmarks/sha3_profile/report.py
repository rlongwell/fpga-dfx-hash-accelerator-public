#!/usr/bin/env python3
"""Compare retained physical samples with like-for-like routed resource counts."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/sha3-performance-20261115"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["fast", "compact"], default="compact")
    parser.add_argument("--baseline", choices=["oxide", "oxide_elastic"], default="oxide_elastic")
    args = parser.parse_args()
    chosen, baseline = args.variant, args.baseline
    report_paths = {name: OUT / f"{name}-physical.json" for name in ["current", baseline, chosen]}
    postboot = OUT / f"{chosen}-postboot-physical.json"
    if postboot.exists():
        report_paths[chosen] = postboot
    reports = {name: json.loads(path.read_text()) for name, path in report_paths.items()}
    original = json.loads((ROOT / "results/dfx_summary.json").read_text())["configurations"]["sha3"]
    resources = {"current": original}
    for name in [baseline, chosen]:
        resources[name] = json.loads((OUT / name / "implementation.json").read_text())
    names = {"current": "Our original byte core", baseline: "Oxide double buffer + " + ("elastic adapter" if baseline == "oxide_elastic" else "byte adapter"),
             chosen: "Our improved wide core"}
    baseline_build = "OXIDE_SPREAD=1 ./build.sh sha3-variant oxide"
    if baseline == "oxide_elastic":
        extra = ""
        if resources[baseline]["placement_directive"] == "AltSpreadLogic_medium":
            extra = "OXIDE_ELASTIC_PLACE=medium "
        if resources[baseline].get("post_route_physical_optimization"):
            extra += "OXIDE_ELASTIC_POSTROUTE=1 "
        baseline_build = "OXIDE_ELASTIC=1 " + extra + "./build.sh sha3-variant oxide"
    large = {}
    benchmark_sha = hashlib.sha256((ROOT / "benchmarks/sha3_profile/run_board.py").read_bytes()).hexdigest()
    for name, report in reports.items():
        assert report["passed"] and report["kind"] == "physical-zybo-performance"
        assert report["bench_source_sha256"] == benchmark_sha
        assert report["kernel"] == "6.6.40-dfx-hash" and report["buffer_size"] == 1048576
        assert report["repeats"] == 7 and report["warmup_per_method"] == 1
        assert report["abort_rejected"] and report["initial_manager_load_ns"] > 0 and report["return_manager_load_ns"] > 0
        if name != "current":
            assert report["manifest"]["images"]["sha3"] == resources[name]["partial"]
            assert resources[name]["clock_mhz"] == 100
            assert resources[name]["timing"]["wns_ns"] >= 0
            assert resources[name]["timing"]["whs_ns"] >= 0
            for line in (OUT / name / "sources.sha256").read_text().splitlines():
                expected, source = line.split("  ", 1)
                assert hashlib.sha256(Path(source).read_bytes()).hexdigest() == expected, source
        large[name] = next(row for row in report["algorithms"]["sha3"] if row["bytes"] == 16777216)
    lines = ["# Physical SHA3 performance and FPGA resource comparison", "",
             "All physical measurements use the same Zybo Z7-20, 100 MHz static system, 1 MiB coherent DMA buffer, Linux driver and Python benchmark. Oxide is the unchanged pinned SHA3-256 implementation with double buffering enabled. SHA-256 and BLAKE2s are separate algorithms, not alternatives used to make a SHA3 speedup claim.", "",
             ("The primary Oxide comparison uses an elastic byte adapter that accepts a replacement AXI beat on the same clock as its last byte drains. This removes the original adapter's one-clock pause every eight bytes and permits Oxide's native one-byte-per-clock input rate. The original-adapter physical run is separately retained in `oxide-physical.json`; the headline uses the elastic-adapter run." if baseline == "oxide_elastic" else "This Oxide run uses the same byte adapter as our original core. That adapter pauses once per eight bytes; the separate native core table does not include that adaptation overhead."), "",
             "Oxide Quartz revision: `c0ccf08525f30c43f4c773c2295dabe80f97cd0e`; SHA3 source SHA-256: `14b59bbe2701626197ae1a5053a769a60d9dad4b484b1a520c7cfbfc5d35615b`. The MPL-2.0 source is unchanged; only the integration wrapper is local. [Pinned reference and license](../../reference/oxide/SOURCE.md).", "",
             "Seven timed repetitions per input/method follow one warmup. Results below use 16 MiB inputs and decimal MB/s. Reference digests, allocation, algorithm switching, disk I/O and UART output are outside the hardware timing. DMA reuses prefilled coherent memory; local API timing includes copying application memory into it. ARM timing uses a preallocated RAM buffer. Every digest is checked. No Ethernet peer is involved.", "",
             "| Physical implementation | DMA MB/s | Local API MB/s | RP LUTs | RP FFs | DMA MB/s per 1k LUTs | System LUTs | Setup slack, ns |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    summary = {}
    for name in reports:
        row, area = large[name], resources[name]
        dma, api = row["summary"]["dma"]["MB_s"], row["summary"]["local_api"]["MB_s"]
        lut, ff = area["rp"]["luts"], area["rp"]["ffs"]
        summary[name] = {"dma_MB_s": dma, "local_api_MB_s": api, "rp_luts": lut, "rp_ffs": ff,
                         "dma_MB_s_per_1000_LUTs": dma * 1000 / lut,
                         "physical_report": report_paths[name].name}
        lines.append(f"| {names[name]} | {dma:.2f} | {api:.2f} | {lut:,} | {ff:,} | {dma*1000/lut:.2f} | {area['total']['luts']:,} | {area['timing']['wns_ns']:+.3f} |")
    fast, oxide, old = [summary[key] for key in [chosen, baseline, "current"]]
    lines += ["", f"The improved core is **{fast['dma_MB_s']/oxide['dma_MB_s']:.2f}× Oxide's measured DMA throughput** and **{fast['local_api_MB_s']/oxide['local_api_MB_s']:.2f}× its local-API throughput**. Against our previous design it improves those measures by {fast['dma_MB_s']/old['dma_MB_s']:.2f}× and {fast['local_api_MB_s']/old['local_api_MB_s']:.2f}×.", "",
              f"For the comparable hash partitions, LUT use changes by {(fast['rp_luts']/oxide['rp_luts']-1)*100:+.1f}% and register use by {(fast['rp_ffs']/oxide['rp_ffs']-1)*100:+.1f}% versus Oxide. DMA throughput per LUT improves by {fast['dma_MB_s_per_1000_LUTs']/oxide['dma_MB_s_per_1000_LUTs']:.2f}×. These percentages refer to the partition, including its adapter; whole-system totals and native core-only counts are reported separately.", "",
              "The design absorbs up to eight bytes at a time. Registering framing errors removes AXI keep/length validation from the high-fanout state-register enable. Invalid beats still fail before absorption. The compact revision decodes padding only across the 17 rate lanes, eliminating the dynamic read/modify/write mux over all 25 state lanes. Keccak remains one complete round per cycle. Both changes preserve the wide core's cycle counts. Earlier byte/wide variants remain available for comparison.", "",
              "All three hash partitions use zero BRAM and zero DSP; the common static system retains one RAMB36 and one RAMB18. Resource counts above include each partition's input adapter. Native Oxide core-only numbers below exclude that adapter. Routed resource usage is a Vivado implementation result, not a counter measured by Linux.", "",
              "The same DFX region remains reserved for every variant. Fewer used cells do not shrink the region reservation or the 2,400,480-byte partial image. No power measurement or power-saving claim is made.", "",
              "## Latency and sample variation", "",
              "| Implementation | Bytes | DMA median µs (min–max) | Local API median µs (min–max) | ARM median µs |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for name in reports:
        for row in reports[name]["algorithms"]["sha3"]:
            d, a, cpu = [row["summary"][key] for key in ["dma", "local_api", "arm"]]
            lines.append(f"| {names[name]} | {row['bytes']:,} | {d['median_ns']/1000:.1f} ({d['min_ns']/1000:.1f}–{d['max_ns']/1000:.1f}) | {a['median_ns']/1000:.1f} ({a['min_ns']/1000:.1f}–{a['max_ns']/1000:.1f}) | {cpu['median_ns']/1000:.1f} |")
    lines += ["", "Small messages are dominated by Python, ioctl and DMA setup latency. There is no promise of a speedup for every tiny request. The static-shell hardware cycle counter includes input starvation and software/DMA gaps; it must not be presented as pure Keccak cycles. Normal board scheduling was used, without affinity, governor changes or thermal stabilization. Seven samples are a measurement of this bench, not a guaranteed peak rate.", "",
              "## Core-only comparison: simulation plus routed timing", "",
              "These are predictions from a 65,536-byte simulation at the timing-closed 100 MHz clock, not physical DMA measurements. Oxide starts timing at the first accepted byte; our cores include their explicit start. This interface difference affects the start convention.", "",
              "| Standalone core | Predicted MB/s | LUTs | FFs |",
              "| --- | ---: | ---: | ---: |"]
    baseline_area = json.loads((ROOT / "results/baseline_implementation.json").read_text())["configurations"]
    baseline_sim = json.loads((ROOT / "results/baseline_simulation.json").read_text())["configurations"]
    for double, title in [(False, "Oxide single buffer"), (True, "Oxide double buffer")]:
        area = next(row for row in baseline_area if row["double_buffer"] == double)
        sim = next(row for row in baseline_sim if row["double_buffer"] == double and not row["source_gaps"])
        assert area["timing_met"]
        lines.append(f"| {title} | {sim['largest_message_MB_s_at_100MHz']:.2f} | {area['routed']['lut']:,} | {area['routed']['ff']:,} |")
    engines = json.loads((ROOT / "results/engine_measurements.json").read_text())["engines"]
    for key, title in [("sha3", "Our original byte core"), ("sha3_fast", "Wide core, registered framing"),
                       ("sha3_compact", "Wide core, compact padding")]:
        area = next(row["routed"] for row in engines if row["engine"] == key)
        assert area["timing_met"]
        simulation = (ROOT / f"results/engines/{key}/simulation.log").read_text()
        cycles = int(re.search(r"random_65536 length=65536 continuous_cycles=(\d+)", simulation)[1])
        lines.append(f"| {title} | {65536*100/cycles:.2f} | {area['lut']:,} | {area['ff']:,} |")
    lines += ["",
              "The board has no synchronized wall clock in this setup, so its JSON calendar timestamps start in 1970. Host UTC timestamps in `uart.log` establish run chronology. Performance durations use Python's monotonic `perf_counter_ns`, independent of that wall clock.", "",
              "## Other installed algorithms", "",
              "These physical 16 MiB measurements characterize the unchanged SHA-256 and BLAKE2s implementations. They are not like-for-like algorithm comparisons with Oxide's SHA3.", "",
              "| Algorithm | DMA MB/s | Local API MB/s | ARM MB/s | RP LUTs | RP FFs |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    configurations = json.loads((ROOT / "results/dfx_summary.json").read_text())["configurations"]
    for name in ["sha256", "blake2s"]:
        row = reports["current"]["algorithms"][name][-1]["summary"]
        area = configurations[name]["rp"]
        lines.append(f"| {name} | {row['dma']['MB_s']:.2f} | {row['local_api']['MB_s']:.2f} | {row['arm']['MB_s']:.2f} | {area['luts']:,} | {area['ffs']:,} |")
    lines += ["", "## Reproduction and evidence", "",
              f"- `./build.sh sha3-variant {chosen}` and `{baseline_build}` reproduce the selected replacement partitions against the accepted locked static design. Each requires setup/hold/pulse-width timing, clean routing/DRC, and full `pr_verify` against all three existing configurations before emitting programming images. The accepted implementation record identifies the actual placement flow; post-route recovery retains the first route and verifies its source ledger.",
              "- The pinned Oxide reference passes 160 independent message checks across single/double buffering and continuous/gapped traffic. The improved core passes 79 vectors in two traffic modes, framing/reset checks, and integrated-shell tests with random DMA splits and five verified recoveries.",
              "- Primary physical sample files: " + ", ".join(f"`{path.name}`" for path in report_paths.values()) + ". The improved-core report uses the post-boot run when available. Earlier compact and fast samples remain retained. Benchmark source hashes, manifests, hardware cycle counts and all individual timings are included; `*-board.log` and `uart.log` capture the real console.",
              "- The comparison image intentionally preserves Oxide's inability to encode an empty message; its empty case is excluded. Our improved core computes empty-message padding in hardware and is tested for it.",
              "- `fast/`, `compact/`, `oxide/` and `oxide_elastic/` retain routed resource, timing, compatibility and source-hash evidence. Historical implementation reports remain distinct from this run.", ""]
    (OUT / "comparison.md").write_text("\n".join(lines))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), layout="constrained")
    for name, report in reports.items():
        rows = report["algorithms"]["sha3"]
        x = [row["bytes"] for row in rows]
        for axis, method in zip(axes[:2], ["dma", "local_api"]):
            axis.plot(x, [row["summary"][method]["MB_s"] for row in rows], "o-", label=names[name])
            axis.set_xscale("log", base=2)
            axis.set_xlabel("Message bytes")
            axis.set_ylabel("Measured MB/s")
            axis.grid(alpha=.25)
    axes[0].set_title("Physical DMA + core")
    axes[1].set_title("Physical API including PS copies")
    axes[0].legend(fontsize=8)
    xs = list(range(3))
    axes[2].bar([x-.18 for x in xs], [summary[name]["rp_luts"] for name in reports], .36, label="LUTs")
    axes[2].bar([x+.18 for x in xs], [summary[name]["rp_ffs"] for name in reports], .36, label="FFs")
    axes[2].set_xticks(xs, ["Original", "Oxide", "Improved"])
    axes[2].set_title("Routed partition resources")
    axes[2].legend()
    fig.suptitle("Zybo Z7-20 · SHA3-256 · 100 MHz · seven samples after warmup")
    fig.savefig(OUT / "profile.png", dpi=180)
    print(OUT / "comparison.md")


if __name__ == "__main__":
    main()
