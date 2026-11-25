# Reviewing the hash accelerator results

The compact SHA3-256 implementation was built, booted, and tested on a physical
Digilent Zybo Z7-20. ARM applications can submit memory, files, or pipes through
the local API into a 1 MiB coherent DMA buffer; Ethernet is optional. Linux,
AXI DMA, the static DFX shell, and the selected FPGA core perform the operation.

The table below describes the original 2026-11-15 DDR/DMA study. The later
[FPGA-managed Ethernet and RAM replay study](../results/gem-direct-20261116/README.md)
has a different static shell, its own resource counts, and separate physical
input/timing boundaries. Do not combine resource counts or timing intervals
between these studies.

## The measured result

At 100 MHz, for 16 MiB messages, using the median of seven measured repetitions
after one warmup:

| Implementation | DMA MB/s | Local PS API MB/s | Hash-partition LUTs | Hash-partition FFs |
| --- | ---: | ---: | ---: | ---: |
| Original project byte core | 76.79 | 65.97 | 5,016 | 1,786 |
| Pinned Quartz core, double buffering, full-rate adapter | 99.14 | 81.81 | 5,856 | 4,222 |
| Project compact wide core, after boot | 233.66 | 155.91 | 4,531 | 1,774 |

The compact configuration delivers **2.36× measured DMA throughput**, with
**22.6% fewer LUTs and 58.0% fewer FFs** than the integrated Quartz baseline.
Local API throughput improves by **1.91×** and DMA throughput per LUT by **3.05×**.
Resources come from routed Vivado reports; rates come from the physical board.
MB/s uses decimal bytes. The reduction counts used cells in the partition;
the reserved DFX region and partial-image size remain unchanged.

The new core absorbs up to eight bytes at a time, registers framing validation
before it controls the state registers, and decodes padding only across the 17
rate lanes. It retains one Keccak round per cycle. These changes address this
project's wider input path and remove unnecessary mux logic.

## Credit and comparison boundary

[Oxide Computer Company and Quartz contributors](../THIRD_PARTY_NOTICES.md)
provided the reference core and prior work. The original SHA3 contribution is
[@nathanaelhuffman's PR #516](https://github.com/oxidecomputer/quartz/pull/516).
That work targets host-image hashing from SPI-NOR. Our benchmark adapts its
byte-stream core to a different system: Zynq DDR/DMA. Its native interface and
our wider absorption path are different architectural choices.

The baseline is the unchanged source at commit
`c0ccf08525f30c43f4c773c2295dabe80f97cd0e`, with `DOUBLE_BUFFER=true`.
The elastic adapter permits one byte per clock. The earlier adapter's extra
pause is not used in the headline comparison. Both variants pass 100 MHz
timing and full static compatibility checks. The original source, full MPL-2.0
license, and separately marked digest-storage derivative are retained.

This is not an Oxide production-system benchmark, an endorsement, or a
universal speedup claim. In the recorded 64-, 136-, and 1,024-byte cases the
compact implementation has higher wall-time latency than the integrated Quartz
baseline. Python, ioctl, and DMA setup dominate these short requests. This DDR/DMA study makes no power,
maximum-clock, sustained Ethernet, or long-duration reliability claim. The
later input-extension study reports bounded physical Ethernet trials separately.
This is one board and a small repeat sample, without affinity or thermal control.

At 64 bytes, Quartz's DMA median is 168.4 µs (158.7–213.2 µs observed range),
versus 187.3 µs (183.7–219.4 µs) for the compact core. These ranges overlap.
The wider input path accelerates streaming work, but a tiny payload offers
little such work over which to spread per-request software and DMA costs.
That explains why higher bulk throughput need not improve tiny-request latency.
The exact cause of the median gap was not isolated: scheduling and request
overhead can outweigh the streaming gain, but these samples do not prove a
specific cause or an intrinsic Quartz core-latency advantage. The hardware
counter also includes starvation and DMA/software gaps, so it cannot separate
pure hashing from those costs. The [demo explanation](demo-explained-video.md)
keeps that distinction explicit.

## Evidence map

| Question | Evidence |
| --- | --- |
| Exact upstream files and license | [Pinned inventory](../reference/oxide/SOURCE.json), [notices](../THIRD_PARTY_NOTICES.md), [fresh upstream byte comparison](../results/repository-review-20261115/upstream-verification.json) |
| All physical samples and size-dependent latency | [Comparison](../results/sha3-performance-20261115/comparison.md), [chart](../results/sha3-performance-20261115/profile.png), linked raw JSON reports |
| Accepted implementation and resource counts | [Compact](../results/sha3-performance-20261115/compact/implementation.json), [Quartz integration](../results/sha3-performance-20261115/oxide_elastic/implementation.json), adjacent timing/utilization/PR reports |
| New boot and all three algorithms | [81 post-boot API/CLI checks](../results/sha3-performance-20261115/promoted-local-physical.json), [boot log](../results/sha3-performance-20261115/compact-reboot.log) |
| Deployment identity and recovery | [Acceptance receipt](../results/sha3-performance-20261115/acceptance.json), [deployment](../results/sha3-performance-20261115/deployment.md), [manifest](../results/sha3-performance-20261115/promoted_manifest.json) |
| Recompute statistics and verify evidence | [Portable auditor](../benchmarks/sha3_profile/audit_results.py), [audit result](../results/repository-review-20261115/evidence-audit.json) |
| Current offline regression suite | [Verification record](../results/verification.json), [CI](../.github/workflows/verify.yml) |
| Original failed tradeoffs | [Core experiments](engines.md), [baseline study](baseline.md), retained placement/timing failures in the dated evidence directory |

The dated physical capture contains 132 checksum-sealed files. Review documents
and later offline tests are separate from that capture. Board wall-clock dates
start in 1970 because its clock was unset; host UTC entries in `uart.log`
establish chronology. Durations use a monotonic performance clock. Simulation,
QEMU, source audits, and physical runs are explicitly distinguished.

## Review from a clean clone

Python 3.11+ is sufficient; no board, Vivado, matplotlib, or ignored build tree
is required:

```sh
python3 benchmarks/sha3_profile/audit_results.py
python3 -m unittest discover -s benchmarks/sha3_profile/tests -v
```

The auditor verifies the seal, pinned source/license hashes, implemented source
files, raw-sample statistics and reference digests, routed resource/timing
summaries, manifest identities, and post-boot acceptance linkage. It explicitly
lists excluded generated artifacts. An audit of retained evidence is not a new
hardware measurement or independent attestation of the original capture.

On the original build workstation, additionally verify the captured binaries
and checkpoints with `--build-artifacts`. Run `./test.sh` with the documented
simulator dependencies for a new offline regression run.

## Build and deployment limits

The [profiling commands](sha3-performance.md) reproduce the incremental work
against the original accepted locked static checkpoint. These dated flows
deliberately require its exact full-image hash. The ignored `build/` artifacts
and original workstation paths in the raw ledgers are not delivered by Git.
A source-only clone can audit and simulate the design; it cannot reconstruct
that exact accepted checkpoint set from the stored hashes alone.

For a fresh full-system build, use the [base build guide](build.md). A newly
generated static design has a new artifact identity; its replacement partitions
must pass fresh routing, timing, compatibility and board acceptance before use.
Do not describe a fresh build as the already tested binary. The shared-card
staging helper also depends on the adjacent `zybo-shared-sd` project and retained
embedded artifacts; it is specific to the installed bench configuration. The
[exact assembler source](../results/repository-review-20261115/bench-environment/assemble-hash.py)
is archived for review and matches the checksum in the local-PS validation receipt.

At the end of the Nov 15 validation, the board ran the `hash` profile with the
compact image and service running. Verified original boot files were retained
for rollback. The subsequent repository/documentation audit did not access it.

The [architecture diagrams](architecture-comparison.md) map each highlighted change
to RTL. The [earlier GUI demo](demo-flow-video.md) includes the same-file
physical GUI comparison, with both core identities and all seven samples retained.
For that Nov 16 recording, the board was temporarily switched from radar to hash,
then restored to radar with its GUI connected. The saved next-boot choice remains
hash; the profile file and radar settings retained their original checksums.

The subsequent [GEM and BRAM replay acceptance](../results/gem-direct-20261116/README.md)
left the board on the healthy `hash` profile, as requested. The latest
[replay video](demo-replay-video.md) explains the hardware-fed experiment and
shows its 25-size physical results with explicit graph units. Producing that
edition reused the retained measurements and did not change the board.
