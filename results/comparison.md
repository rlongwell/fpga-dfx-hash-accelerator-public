# Measured comparison

Vivado 2024.2, xc7z020clg400-1, 100 MHz target, standalone out-of-context implementations. LUT/FF/BRAM/DSP and slack come from routed reports. File rates are **predictions from simulation cycles at the constrained clock**, not board measurements. Decimal MB/s is used throughout.

All table rates use a 65,536-byte message with continuous source traffic. At 100 MHz, the corresponding predicted latency in microseconds is the listed cycle count divided by 100. Oxide latency starts at its first accepted byte; common-interface engines include their explicit start. The Oxide rows expose the original byte interface, whereas SystemVerilog rows include their 64-bit stream adapter and length checking. Compare the isolated digest-storage change within the Oxide pair, and the original RTL experiments within the common-interface group. There is no claim that a wide AXI port alone improves a byte core.

| Implementation | LUT | FF | BRAM | DSP | Setup slack, ns | Cycles / 64 KiB | Predicted MB/s | MB/s per LUT |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Oxide original, single buffer | 4,504 | 2,989 | 0 | 0 | +0.617 | 78,084 | 83.930 | 0.01863 |
| Oxide original, double buffer | 5,406 | 4,075 | 0 | 0 | +1.018 | 65,578 | 99.936 | 0.01849 |
| Oxide without digest register, single buffer | 4,369 | 2,724 | 0 | 0 | +0.743 | 78,084 | 83.930 | 0.01921 |
| Oxide without digest register, double buffer | 5,223 | 3,820 | 0 | 0 | +0.787 | 65,578 | 99.936 | 0.01913 |
| BLAKE2s-256 | 4,127 | 1,665 | 0 | 0 | +0.489 | 156,674 | 41.830 | 0.01014 |
| SHA-256 | 1,741 | 1,249 | 0 | 0 | +0.329 | 140,413 | 46.674 | 0.02681 |
| SHA3 direct byte absorption | 4,981 | 1,786 | 0 | 0 | +0.732 | 84,817 | 77.268 | 0.01551 |
| SHA3 wide, compact padding | 4,498 | 1,774 | 0 | 0 | +0.500 | 27,473 | 238.547 | 0.05303 |
| SHA3 wide, registered framing | 5,664 | 1,795 | 0 | 0 | +0.324 | 27,473 | 238.547 | 0.04212 |
| SHA3 shared lane/row rounds | 4,706 | 3,714 | 0 | 0 | +0.292 | 431,857 | 15.175 | 0.00322 |
| SHA3 wide absorption | 5,704 | 1,795 | 0 | 0 | -0.738 | 27,473 | timing failed | — |

## What the measurements establish

The minimal Oxide modification removes redundant digest storage while preserving valid digest behavior and measured cycle counts. Single-buffer routing saves 135 LUTs and 265 FFs; double buffering saves 183 LUTs and 255 FFs. The different FF deltas reflect synthesis transformations, rather than an assumption that every removed bit maps one-for-one to a flip-flop.

Direct state absorption removes the large input buffer and lowers storage, but the measured common-interface byte design uses more LUTs than the original byte-input baseline. The wide and shared-datapath rows retain their measured tradeoffs, including any negative result; fewer arithmetic units are not automatically fewer FPGA resources.

At 100 MHz, a 24-cycle Keccak permutation has a theoretical capacity of 4.167 million permutations/s (566.667 MB/s of SHA3 rate blocks if absorption were free). The 744-cycle serialized permutation has 0.1344 million permutations/s (18.280 MB/s of rate blocks). These datapath capacities exclude absorption, padding, stream buffering, DMA, and networking, and must not be substituted for file throughput.

All compared flows use the same part, tool version, 10 ns clock, 2 ns input/output budgets, BUFGCTRL_X0Y0 OOC clock source, rebuilt synthesis hierarchy, and default opt/place/phys_opt/route stages. The Oxide pair used four tool threads; the common-interface group used two. OOC external pins have no physical partition-pin placement, so internal register timing is also recorded separately. Frequencies inferred from one routed slack value are estimates, not measured maximum clocks; no frequency sweep was performed.

[Routing congestion evidence](congestion.md) preserves the actual post-placement regional estimates and final global routing-resource percentages. These are separate from the zero-routing-error acceptance checks.

The original SHA-256 final-round accumulation missed 100 MHz. The retained negative result is in `engines/sha256_pre_commit/`; the current core adds one chaining-state commit clock per block and is independently reverified. The initial full-system framing path also missed timing; it was replaced with a registered remaining-byte counter before accepting programming images.

The original BLAKE2s core passed standalone timing but missed 100 MHz inside the locked DFX system (-0.654 ns setup). Prefetching four scheduled message words during existing compression steps removes the message selection from the addition path. Its standalone implementation uses 1,122 more LUTs and 152 more FFs, with identical measured simulation cycle counts and improved internal timing. The previous standalone reports remain in `engines/blake2s_pre_prefetch/`; full-system acceptance is reported separately below.

## Actual system and software scope

[DFX implementation results](dfx_summary.md) report the complete PS7/DMA/static/RP design, its actual routed clock checks, compatible configurations, and image sizes. Those figures include infrastructure and are distinct from this core-only table.

Local software measurement: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz, Python 3.12.3, OpenSSL 3.0.13 30 Jan 2024. Each sample hashes 16,777,216 in-memory bytes; 9 repetitions per algorithm. Allocation, disk, and networking are excluded. Full sample times and start load are recorded in `x86_software.json`. Measurement context: After FPGA and ARM compilation completed; no project implementation jobs running. Normal user processes remain active; no CPU affinity, governor control or thermal stabilization. Not a peak-performance claim..

| x86 software | Median MB/s | Min–max milliseconds |
| --- | ---: | ---: |
| sha3 | 359.696 | 45.641–54.259 |
| sha256 | 418.031 | 38.274–41.054 |
| blake2s | 387.705 | 41.433–77.477 |

Physical DDR-to-PL DMA, PCAP reconfiguration and ARM software measurements are retained separately in the [2026-11-15 board comparison](sha3-performance-20261115/comparison.md). External Ethernet throughput remains unmeasured. The Ethernet link's nominal 1 Gbit/s ceiling is 125 MB/s before protocol overhead. No desktop-x86 acceleration claim follows from these separate measurements.

Regenerate this document with `python3 benchmarks/report.py` after the implementation and benchmark commands complete. Source hashes, full timing/resource reports, and test logs accompany the JSON evidence.

## Wide SHA3 at a lower clock

The same completed wide-core route was reanalyzed at 80 MHz with the same 2 ns I/O budgets. Its RTL, placement, and routing were unchanged; this is a frequency tradeoff study, not another physical implementation or a production DFX configuration. Setup slack is +1.762 ns and hold slack is +0.137 ns. The simulated 64 KiB latency of 27,473 cycles predicts 190.838 MB/s at 80 MHz. The 100 MHz failure remains in the comparison table above.

This historical 80 MHz experiment is separate from the improved `sha3_fast` design, which registers framing validation and closes timing at 100 MHz in the existing static system. The higher predicted core rate does not measure DDR/DMA or Ethernet throughput. [Separate clock-analysis evidence](sha3_wide_clock_80mhz/analysis.json) includes coverage checks and checkpoint identity.
