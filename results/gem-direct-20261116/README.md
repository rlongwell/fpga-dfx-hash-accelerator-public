# GEM and FPGA RAM input extension — 2026-11-16

**The corrected image passes all 84 packet/replay acceptance cases and 81 PS API
checks on the physical Zybo.** The GUI backend and ordinary TCP API also pass.
The [64-byte-to-1-GiB size sweep](sweep-64B-1GiB/README.md) also passes:
**700 timed measurements plus 100 warmups**, with charts and complete CSV/JSON data.

The accepted full-image SHA-256 is
`6102e03f31c175d8cba562a7be0fbf17e8890349f909713e8231cf20ce87987b`.
The [boot receipt](deployment-v2.json) identifies the matching DTB, retained
backup, saved hash profile and SD persistence checks.

## Corrected-image measurements

These are medians of three interleaved 1 GiB trials per SHA3-256 core, with a
16 MiB warmup before each trial. Every digest matched software. Timing excludes
reconfiguration and software reference hashing.

| Input and timing interval | Oxide Quartz | Compact | Compact speedup |
| --- | ---: | ---: | ---: |
| Repeated FPGA RAM data; hardware START to digest | 10.737419 s / 100.000 MB/s | 4.500242 s / 238.596 MB/s | **2.386×** |
| Same random-text file over raw Ethernet; first data send to digest reply | 21.875108 s / 49.085 MB/s | 20.769241 s / 51.699 MB/s | **1.053×** |

Replay uses a 128 KiB pattern repeatedly; it does not store a 1 GiB file in
FPGA RAM. Ethernet uses the original random-text file, so the two rows are
separate experiments with separate timing boundaries. The raw Ethernet path
removes ARM payload handling but is **slower than the earlier Linux/TCP path**
on this bench. The experiment includes the 12-frame window, acknowledgment
cadence, host sender and GEM path; their individual contributions have not
been isolated. Larger tested bursts caused receive overruns. This is not
gigabit line rate or a 2.386× Ethernet win.
The completed size sweep uses identical deterministic data across both modes.
Its seven-trial 1 GiB medians are 238.596 versus 100.000 MB/s for replay, and
51.339 versus 49.014 MB/s for Ethernet: 2.386× and 1.047×, respectively.

| Routed resource scope | Oxide Quartz | Compact | Reduction |
| --- | ---: | ---: | ---: |
| Hash-partition LUTs | 5,854 | 4,572 | **21.90%** |
| Hash-partition flip-flops | 4,222 | 1,774 | **57.98%** |
| Whole-design LUTs | 9,853 | 8,571 | 13.01% |
| Whole-design flip-flops | 8,947 | 6,499 | 27.36% |

Both use the same static shell, 65 RAMB36 + one RAMB18 overall, no DSPs, and
100 MHz. The hash partitions use no RAMB/DSP resources. Resource counts are
Vivado implementation results; the times above are physical measurements.
The reserved DFX area and partial-image size do not shrink with used-cell count.
The historical 22.6% LUT reduction belongs to the earlier static build.

[Raw acceptance](acceptance-final/results.json), [computed comparison](comparison-final.json),
and [routed reports](implementation-bram64/summary.json) retain the details.
Run `python3 results/gem-direct-20261116/recompute.py` to recompute the table
from recorded results; that command does not rerun the board.

The [architecture and reproduction guide](../../docs/gem-direct.md) describes
the three retained input paths, exclusive ownership, packet protocol and
rollback procedure. The unchanged pinned Oxide Quartz implementation and
license notices remain in [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).

| Check | Result | Scope and evidence |
| --- | --- | --- |
| Existing engines, shell, PS software and evidence audit | Pass | [Final offline source/checksum record](offline-verification-final.json); host simulation and software tests |
| GEM ingress and replay | Pass | [RTL simulation](final-ingress-tests.log): invalid/duplicate/reordered packets, ring wrap, stalls, partial final beats, replay patterns through 252 KiB and reset recovery |
| Outstanding transmit write across hash abort | Pass | Same RTL simulation; independent AXI transaction completion |
| Raw sender, empty and multi-packet inputs, dropped-frame retry | Pass | [20 final window/readiness cases](sender-final.log), plus [50 earlier stability cases](sender-stability.log); software peers, no physical FPGA |
| GUI validation/recovery tests | Pass | [20 host tests](demo-final-tests.log) |
| ARM executable compatibility and wrong-image guard | Pass | [Board preflight](arm-preflight.log); helper starts and refuses the old DT before mapping hardware |
| Updated runtime with the existing FPGA image | Pass | [UART installation/checksums](runtime-legacy-compatibility.log), [physical GUI job](gui-legacy-physical.json) and [physical TCP job](tcp-legacy-physical.json) |
| First new static image and all four partials | Pass | [Implementation reports](implementation/summary.json); routed timing, DRC, routing and full `pr_verify` |
| First new image boot and SD persistence | Pass | [UART deployment](deployment-v1-uart.log), matching bitstream/DT, saved hash selection and persistent sentinels |
| Existing PS API on first new image | Pass | [81 physical checks](ps-api-v1/results.json), all three algorithms, boundaries, multi-buffer DMA, abort recovery and real DFX |
| Existing GUI backend on first new image | Pass | [All three algorithms](gui-all-algorithms-v1.json) and [both SHA3 cores](gui-compare-v1.json), through the actual GUI HTTP API and UART |
| First new image BRAM replay | Pass | [42 physical cases](replay-first-image/results.json), all algorithms, maximum 252 KiB pattern, boundaries, and three 1 GiB trials per SHA3 core |
| First new image Ethernet | Fail, diagnosed | [Physical register capture](ethernet-diagnosis-v1.log), [netlist diagnosis](bram-write-diagnosis.json), [generated-memory regression](bram-write-fix/generated-memory-failure.log) |
| Corrected static image and all four partials | Pass | [Routed implementation and resources](implementation-bram64/summary.json); timing, route, DRC and full PR checks |
| Corrected image boot and SD persistence | Pass | [UART deployment](deployment-v2-uart.log); saved hash selection and both sentinels retained |
| Corrected image packet/replay smoke | Pass | [Physical smoke](smoke-v2/results.json), independent digests and PS DMA recovery |
| Ethernet without ARM payload handling | Pass | [Stopped-control case](acceptance-final/results.json): FPGA returns the digest while the control process remains stopped |
| Packet sender tuning | Pass | [Physical window sweep](sender-tuning.json), delayed-readiness retry repair, zero-overrun 12-frame probe |
| Corrected image complete packet/replay acceptance | Pass | [84 physical cases](acceptance-final/results.json), including three 1 GiB trials per core/mode and stopped-control proof |
| Corrected image PS API | Pass | [81 physical checks](ps-api-v2/results.json), all algorithms, empty/boundary/multi-buffer inputs, abort recovery and real DFX |
| Corrected image GUI backend | Pass | [All algorithms](gui-all-algorithms-v2.json) and [both SHA3 cores](gui-compare-v2.json) through the real GUI HTTP API/UART |
| Corrected image TCP API | Pass | [Four physical jobs](tcp-final.json), all three algorithms and return to SHA3 |
| Repeated 64 B–1 GiB size sweep | Pass | [700 timed observations + 100 warmups](sweep-64B-1GiB/README.md), identical inputs, both SHA3 cores and both new paths |
| Final board state and persistence | Pass | [Final health](final-health.json): running/next hash, service healthy, all partial checksums, SD sentinels and profile preserved, rescue verified |
| Exclusive ownership guards | Pass | [Final physical checks](ownership-v2-final.json); rejected competing operations without stopping the service |

The physical GUI compatibility job used the GUI server's actual HTTP job API,
USB UART delivery and board `LocalHasher` backend. SHA3-256, SHA-256 and
BLAKE2s-256 each matched an independent PC digest. This was a backend operation,
not a newly recorded GUI video. The TCP compatibility test used the physical
gigabit link. Both tests used the old full image:

`cbd8a4cf221032c15b11d6d0962ce070b221b5dd9b5081b0677742a97485ff40`.

The new runtime was deployed through UART after checksumming and saving the
previous runtime under `/root/hash-before-runtime-guard-20261116`. The saved
hash profile SHA remained
`9dc14825fb83ef1fe366b1a2a9451395d67a966a0800ad4a4a9289dc612f46fc`.
The first new full image is
`ce62bea7fd46a9ebff130ace3fc5f7be828cd1bdc587ed13ef43966abde31c24`.
Its matching bundle and original-image rollback were checked before reboot.
The complete original boot/runtime backup remains at
`/root/hash-before-gem-20261116-v1` on the board; the rescue profile is intact.

Ethernet diagnosis found that the generated memory tied `WEB[7:4]` low.
Alternate 32-bit reply words and the transmit descriptor's ownership word
therefore stayed unchanged. The external BRAM port still described 32-bit
memory while the internal port had been widened to 64 bits. Correct metadata
also exposed the vendor's unsupported asymmetric controller configuration.
The repair uses 64-bit controller/memory ports and an AXI width adapter, and
adds a regression against the synthesized vendor memory before static synthesis.

Boot also reported a pre-existing FAT dirty flag. A read-only filesystem check
found no allocation/directory errors. After a full 512 MiB boot-partition backup,
`fsck.fat` cleared only byte 65 from 1 to 0; a byte-for-byte comparison confirmed
no other changes. The subsequent read-only check passed. See
[repair evidence](fat-repair.json) and [UART log](fat-clean-flag.log).

The original host protocol test intermittently timed out because the desktop
network manager changed a temporary veth interface's MAC between discovery
and sender startup. Running the software peer in a private network namespace
removed that interference; ten complete runs then passed, including intentional
packet loss. This was a host test-environment fault, not physical-board evidence.

The first implementation attempt missed 100 MHz setup timing by 0.570 ns.
Its [retained reports](timing-attempt-1/routed_timing.rpt) and
[failing endpoints](timing-attempt-1/failing-endpoints.txt) identified static
BRAM control paths. The repairs remove the core-ready dependency from RAM
enable, simplify replay address generation, and register configuration decoding.
The hash algorithms and Oxide source were not changed.

The existing [1 GiB physical TCP baseline](../ethernet-20261116/README.md) is
separate evidence: 13.732343 s for Quartz and 12.210009 s for compact, using the
same random-text input and three interleaved trials per core.

## FPGA-only replay on the first image

These physical measurements use 128 KiB of deterministic FPGA-resident data
repeated 8,192 times, for a total of 1 GiB hashed. They do not store a 1 GiB file
in BRAM. Pattern loading, software reference hashing and reconfiguration are
outside the interval. The existing FPGA counter measures START through digest
completion at 100 MHz, including the FPGA input reader and framing.

| SHA3-256 implementation | Hardware cycles, each of three trials | Seconds | Decimal MB/s |
| --- | ---: | ---: | ---: |
| Oxide Quartz, double buffer and elastic adapter | 1,073,741,926 | 10.73741926 | 99.99999050 |
| Compact | 450,024,163 | 4.50024163 | 238.59648265 |

The observed ratio is **2.385965×**. Every digest matched the independent
software reference; each job forced an actual partial switch and afterward
passed a real PS DMA recovery hash. Identical cycle counts across repeated
trials are expected for this deterministic hardware workload. ARM monotonic
elapsed times independently agree with a 100 MHz counter to within polling
overhead. These are datapath measurements, not isolated Keccak-round latency
or Ethernet throughput. The corrected-image acceptance repeated these checks with
identical replay cycle counts, as recorded above.

## Retained interruptions and tooling repairs

The original diagnostic acceptance run was interrupted after 22 passing cases
to tune the sender. The final acceptance then needed two resumptions: a Linux
link message interrupted an encoded log record, and another interrupted a
UART command-completion marker. The saved board results show correct hashes
in both affected cases. The cases were rerun under fresh artifact names;
previous reports, raw logs and harness source history remain in the directory.
No missing result was promoted to a pass.

Log reads now retry at most three times and require valid whole-record base64
and gzip CRC/length. During the longer tests, informational console logging was
temporarily reduced while kernel ring-buffer logging remained active; its
original level of 7 was restored, as recorded in [console-level.json](console-level.json).

The [TimingLens evaluation](timinglens/README.md) records parser repairs,
project-aware recommendations, the implemented timing experiment, UI previews,
and software validation separately from physical throughput evidence.


## Retained deployment and evidence integrity

The [18-file bundle inventory](bundle-v2-inventory.json), [deployed manifest](deployed-v2-dfx_manifest.json),
[comparison variants](deployed-v2-core_variants.json), [device-tree source](device-tree-v2.dts),
and [build acceptance ledger](accepted-v2.sha256) identify the matched files.
Generated images/checkpoints remain in ignored workstation build storage and
on the board; their hashes do not make them available in a source-only clone.
All three corrected-image full PR checks are retained with the routed reports
under `implementation-bram64/`.

`SHA256SUMS` seals the retained files in this directory, excluding ignored bulk
inputs and the seal itself. From this directory, run `sha256sum -c SHA256SUMS`.
This checks the captured files, not whether a new board run happened. Copy the
capture before regenerating plots so the original seal remains meaningful.
