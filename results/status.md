# Verification status

Offline implementation evidence was completed on 2026-11-12 UTC. The full offline verification suite was rerun successfully on 2026-11-15 UTC; see [the source-hashed run record](verification.json). Subsequent physical Zybo testing on 2026-11-15 passed 81 local PS hash checks plus a final SHA3 restoration digest: see [physical results](local-ps-20261115/physical.json), [UART evidence](local-ps-20261115/uart.log), and the [source receipt](local_ps_validation.json). The new local API adds no RTL or kernel changes. Its [25 host software tests](local-ps-20261115/host-tests.log) are separate from physical evidence.

| Area | Current evidence |
| --- | --- |
| Environment | Vivado 2024.2 installed; xc7z020clg400-1 and Zybo Z7-20 board preset available |
| Architecture | PS7/MIO Ethernet, DDR/DMA, length framing, common RP, registers, clock/reset and acceptance criteria documented |
| Oxide baseline | 160 independent message checks plus reset/abort pass; both buffer configurations meet 100 MHz in OOC routing |
| Digest-storage variant | Same simulation cycles; single buffer saves 135 routed LUTs and 265 FFs; both buffer configurations meet 100 MHz |
| Static shell | AXI Lite skew/backpressure/strobes, DMA splits, byte-order, length/error handling, abort/reset and hostile-RP isolation tests pass |
| Common algorithms | SHA3/SHA256/BLAKE2s each pass 79 hashlib vectors in continuous/stressed modes, plus protocol/reset/backpressure tests |
| Integrated shell + engines | All three pass 79 hashlib vectors with randomized DMA chunk boundaries plus five abort/error/isolation/reset cases, each followed by a verified recovery digest |
| DMA integration | PS7/MM2S block design validates; vendor IP and static synthesis pass; XSA exported |
| DFX implementation | All three full-system configurations route at 100 MHz with clean required DRC and positive setup/hold/pulse slack; both full `pr_verify` checks pass. Full/partial .bit and PCAP .bin images accepted |
| SHA3 experiments | Both pass 79 continuous/stressed vectors; routed comparisons complete. Wide misses 100 MHz and passes separate unchanged-route 80 MHz analysis; serialized rounds meet 100 MHz with measured latency/storage tradeoffs |
| PS software | Host and pinned ARM Linux module compile; 25 host software tests pass, including local stream/error handling and mocked ioctl/manifest failures. ARM kernel, device tree, U-Boot and root filesystem cross-built; Cortex-A9 QEMU userspace/UAPI checks pass. Physical local API/CLI tests verify actual driver operation with 1 MiB coherent buffers. |
| Board / Ethernet / PCAP timing | Physical SHA3/SHA256/BLAKE2s digests, DMA boundaries, PCAP switching and abort recovery pass. FPGA Manager durations are retained per job. Repeated physical DMA/local API profiles through 16 MiB are retained in the SHA3 comparison; the later [physical Ethernet and FPGA RAM extension](gem-direct-20261116/README.md) records external-link results separately. |

The current `./test.sh` suite passes for seven engine variants, five integrated models, the elastic comparison adapter, software tests, and retained-evidence audit. `verification.json` binds its before/after source hashes to the retained `verification_logs/`; `embedded_userspace_test.json` separately records the ARM QEMU checks.

Baseline evidence: `baseline_implementation.json`, `baseline_simulation.json`, and `oxide_no_digest_comparison.json`. Engine evidence is under `engines/` and `engine_measurements.json`. The first BLAKE2s DFX implementation failed setup timing (-0.654 ns, then -0.446 ns after recovery); it is preserved in `dfx_blake2s_pre_prefetch/`. The prefetch version passes the same static system at +0.101 ns setup slack, with unchanged simulation cycle counts and a documented resource cost.

Full-system setup slack is +0.262 ns for SHA3, +0.229 ns for SHA-256 and +0.101 ns for BLAKE2s; hold slack is +0.044 ns for all three. [The DFX summary](dfx_summary.md), `dfx_manifest.json`, and hashed reports under `dfx/` identify the accepted compatible images. Each PCAP partial is 2,400,480 bytes. Full-system results remain separate from standalone OOC measurements.

`embedded_build.json` and `embedded_artifact_audit.json` identify the 336,592,896-byte SD image under `build/embedded/images/sdcard.img`. The audit checks its input/artifact hashes, both partition contents, six boot files, 15 installed runtime files, and FAT/ext4 integrity. This is an offline packaging and ARM-userspace result, not proof of board boot or FPGA peripheral operation.

Subsequent tests establish the external gigabit PHY/link and hash a 1 GiB file, larger than DDR; see the [TCP baseline](ethernet-20261116/README.md) and [FPGA-managed input extension](gem-direct-20261116/README.md). Remaining acceptance includes switching while existing network connections remain alive, DMA halt/reset failure injection, and long-duration reliability testing. Local PS acceptance tests cover inputs through 2 MiB + 17 bytes. The separate physical performance run covers inputs through 16 MiB, with seven samples after warmup and reference hashing outside the hardware timers.

## Compact SHA3 upgrade: 2026-11-15

The compact image booted on the physical Zybo and passed [81 post-boot API/CLI checks](sha3-performance-20261115/promoted-local-physical.json), plus a final SHA3 restoration digest. SHA3, SHA-256 and BLAKE2s all pass empty, block-boundary, multi-buffer, file and pipe cases; abort recovery and actual switching away and back pass. The original hash boot files and runtime inventory are retained on the SD for rollback.

The compact partition uses 4,531 LUTs and 1,774 FFs; the full system uses 6,708 LUTs and 4,269 FFs. Routed setup/hold slack is +0.212/+0.044 ns at 100 MHz. All three full compatibility checks pass. The new core passes the 79-vector two-mode engine suite and 79 integrated-shell vectors plus five recovery cases. These checks are included in the current full regression suite.

[Physical performance and resources](sha3-performance-20261115/comparison.md), [boot console](sha3-performance-20261115/compact-reboot.log), [installed manifest](sha3-performance-20261115/promoted_manifest.json), and [18-file package audit](sha3-performance-20261115/bundle-audit.json) identify the upgrade separately from the original build. The kernel, driver, DT, SHA-256 and BLAKE2s RTL are unchanged. The upgraded standalone SD image has not been regenerated; the complete shared-card profile is staged and physically deployed.

The final large-buffer SHA3 comparison measures 233.66 MB/s for compact versus 99.14 MB/s for full-rate, double-buffered Oxide: 2.36× throughput with 22.6% fewer partition LUTs and 58.0% fewer FFs. Local PS API rates are 155.91 versus 81.81 MB/s. The unchanged native Oxide source needed post-route physical optimization to close its integrated timing; the initial -0.079 ns result and final +0.045 ns result are both retained.

The [repository review](repository-review-20261115/README.md) verifies exact upstream source bytes, adds explicit attribution and licensing boundaries, and audits the immutable physical capture. Its source-only check is part of the offline suite and CI. The dated physical record was not rewritten and the board was not accessed during this review.


## FPGA-managed Ethernet and RAM replay: 2026-11-16

The new static shell preserves the local PS API, GUI and TCP path, and adds
exclusive GEM-to-FPGA RAM packet handling and repeated FPGA-resident patterns.
The corrected image and all four partials pass 100 MHz routed setup/hold,
route completion, DRC and full PR checks. Setup slack is +0.169 ns compact,
+0.161 ns Quartz, +0.141 ns SHA-256 and +0.110 ns BLAKE2s; hold is +0.016 ns.

The [dated report](gem-direct-20261116/README.md) records 84 physical input
acceptance cases, 81 retained PS API checks, GUI and TCP regressions, and
checksum-matched UART deployment. Replay measures 238.596 versus 100.000 MB/s;
raw Ethernet measures 51.699 versus 49.085 MB/s on the random-text comparison.
These intervals and inputs differ. The new hash partition uses 21.90% fewer
LUTs and 57.98% fewer FFs than the unchanged integrated Quartz baseline;
whole-design and historical-build counts are reported separately.


The [64 B–1 GiB size sweep](gem-direct-20261116/sweep-64B-1GiB/README.md)
adds 700 verified timed measurements and 100 warmups across the two SHA3 cores
and two new input modes. All 350 timed FPGA-replay measurements repeat exactly
by size/core; Ethernet retains observed variation and retries. The board is
left healthy on hash, its saved profile and SD sentinels unchanged, with its
original console log level restored; see [final health](gem-direct-20261116/final-health.json).
