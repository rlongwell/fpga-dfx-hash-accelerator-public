# Physical SHA3 performance and FPGA resource comparison

All physical measurements use the same Zybo Z7-20, 100 MHz static system, 1 MiB coherent DMA buffer, Linux driver and Python benchmark. Oxide is the unchanged pinned SHA3-256 implementation with double buffering enabled. SHA-256 and BLAKE2s are separate algorithms, not alternatives used to make a SHA3 speedup claim.

The primary Oxide comparison uses an elastic byte adapter that accepts a replacement AXI beat on the same clock as its last byte drains. This removes the original adapter's one-clock pause every eight bytes and permits Oxide's native one-byte-per-clock input rate. The original-adapter physical run is separately retained in `oxide-physical.json`; the headline uses the elastic-adapter run.

Oxide Quartz revision: `c0ccf08525f30c43f4c773c2295dabe80f97cd0e`; SHA3 source SHA-256: `14b59bbe2701626197ae1a5053a769a60d9dad4b484b1a520c7cfbfc5d35615b`. The MPL-2.0 source is unchanged; only the integration wrapper is local. [Pinned reference and license](../../reference/oxide/SOURCE.md).

Seven timed repetitions per input/method follow one warmup. Results below use 16 MiB inputs and decimal MB/s. Reference digests, allocation, algorithm switching, disk I/O and UART output are outside the hardware timing. DMA reuses prefilled coherent memory; local API timing includes copying application memory into it. ARM timing uses a preallocated RAM buffer. Every digest is checked. No Ethernet peer is involved.

| Physical implementation | DMA MB/s | Local API MB/s | RP LUTs | RP FFs | DMA MB/s per 1k LUTs | System LUTs | Setup slack, ns |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Our original byte core | 76.79 | 65.97 | 5,016 | 1,786 | 15.31 | 7,193 | +0.262 |
| Oxide double buffer + elastic adapter | 99.14 | 81.81 | 5,856 | 4,222 | 16.93 | 8,033 | +0.045 |
| Our improved wide core | 233.66 | 155.91 | 4,531 | 1,774 | 51.57 | 6,708 | +0.212 |

The improved core is **2.36× Oxide's measured DMA throughput** and **1.91× its local-API throughput**. Against our previous design it improves those measures by 3.04× and 2.36×.

For the comparable hash partitions, LUT use changes by -22.6% and register use by -58.0% versus Oxide. DMA throughput per LUT improves by 3.05×. These percentages refer to the partition, including its adapter; whole-system totals and native core-only counts are reported separately.

The design absorbs up to eight bytes at a time. Registering framing errors removes AXI keep/length validation from the high-fanout state-register enable. Invalid beats still fail before absorption. The compact revision decodes padding only across the 17 rate lanes, eliminating the dynamic read/modify/write mux over all 25 state lanes. Keccak remains one complete round per cycle. Both changes preserve the wide core's cycle counts. Earlier byte/wide variants remain available for comparison.

All three hash partitions use zero BRAM and zero DSP; the common static system retains one RAMB36 and one RAMB18. Resource counts above include each partition's input adapter. Native Oxide core-only numbers below exclude that adapter. Routed resource usage is a Vivado implementation result, not a counter measured by Linux.

The same DFX region remains reserved for every variant. Fewer used cells do not shrink the region reservation or the 2,400,480-byte partial image. No power measurement or power-saving claim is made.

## Latency and sample variation

| Implementation | Bytes | DMA median µs (min–max) | Local API median µs (min–max) | ARM median µs |
| --- | ---: | ---: | ---: | ---: |
| Our original byte core | 64 | 187.9 (183.0–211.6) | 397.9 (390.9–447.6) | 36.8 |
| Our original byte core | 136 | 190.6 (181.3–232.0) | 397.4 (393.4–418.9) | 47.3 |
| Our original byte core | 1,024 | 181.6 (171.5–207.8) | 402.1 (400.6–408.9) | 112.0 |
| Our original byte core | 65,536 | 1019.9 (1010.5–1055.5) | 1347.9 (1327.0–1413.2) | 5323.5 |
| Our original byte core | 1,048,576 | 13746.9 (13743.1–13764.6) | 16169.6 (16159.9–16233.2) | 84982.0 |
| Our original byte core | 16,777,216 | 218495.7 (218492.7–218505.4) | 254320.8 (254207.3–254394.2) | 1358845.7 |
| Oxide double buffer + elastic adapter | 64 | 168.4 (158.7–213.2) | 371.1 (368.0–384.1) | 36.7 |
| Oxide double buffer + elastic adapter | 136 | 161.6 (157.0–190.7) | 370.4 (367.8–403.5) | 47.4 |
| Oxide double buffer + elastic adapter | 1,024 | 163.2 (160.9–180.5) | 376.9 (374.1–416.9) | 112.5 |
| Oxide double buffer + elastic adapter | 65,536 | 825.5 (823.0–850.7) | 1155.7 (1141.3–1221.8) | 5342.0 |
| Oxide double buffer + elastic adapter | 1,048,576 | 10665.5 (10658.8–10713.0) | 13138.0 (13115.4–13183.0) | 84986.0 |
| Oxide double buffer + elastic adapter | 16,777,216 | 169229.7 (169203.4–169242.6) | 205078.0 (205015.6–205201.9) | 1357223.6 |
| Our improved wide core | 64 | 187.3 (183.7–219.4) | 400.8 (395.4–413.7) | 36.6 |
| Our improved wide core | 136 | 188.7 (183.1–253.7) | 400.5 (396.8–417.9) | 47.5 |
| Our improved wide core | 1,024 | 176.4 (174.2–196.2) | 406.5 (401.5–424.7) | 113.6 |
| Our improved wide core | 65,536 | 456.3 (447.7–483.7) | 767.1 (758.7–852.9) | 5329.0 |
| Our improved wide core | 1,048,576 | 4578.5 (4572.0–4594.6) | 6995.4 (6980.1–7043.2) | 85025.6 |
| Our improved wide core | 16,777,216 | 71801.9 (71756.7–71963.6) | 107610.9 (107320.3–107965.9) | 1359301.8 |

Small messages are dominated by Python, ioctl and DMA setup latency. There is no promise of a speedup for every tiny request. The static-shell hardware cycle counter includes input starvation and software/DMA gaps; it must not be presented as pure Keccak cycles. Normal board scheduling was used, without affinity, governor changes or thermal stabilization. Seven samples are a measurement of this bench, not a guaranteed peak rate.

## Core-only comparison: simulation plus routed timing

These are predictions from a 65,536-byte simulation at the timing-closed 100 MHz clock, not physical DMA measurements. Oxide starts timing at the first accepted byte; our cores include their explicit start. This interface difference affects the start convention.

| Standalone core | Predicted MB/s | LUTs | FFs |
| --- | ---: | ---: | ---: |
| Oxide single buffer | 83.93 | 4,504 | 2,989 |
| Oxide double buffer | 99.94 | 5,406 | 4,075 |
| Our original byte core | 77.27 | 4,981 | 1,786 |
| Wide core, registered framing | 238.55 | 5,664 | 1,795 |
| Wide core, compact padding | 238.55 | 4,498 | 1,774 |

The board has no synchronized wall clock in this setup, so its JSON calendar timestamps start in 1970. Host UTC timestamps in `uart.log` establish run chronology. Performance durations use Python's monotonic `perf_counter_ns`, independent of that wall clock.

## Other installed algorithms

These physical 16 MiB measurements characterize the unchanged SHA-256 and BLAKE2s implementations. They are not like-for-like algorithm comparisons with Oxide's SHA3.

| Algorithm | DMA MB/s | Local API MB/s | ARM MB/s | RP LUTs | RP FFs |
| --- | ---: | ---: | ---: | ---: | ---: |
| sha256 | 46.56 | 42.39 | 40.86 | 1,776 | 1,249 |
| blake2s | 41.70 | 38.29 | 31.01 | 4,161 | 1,666 |

## Reproduction and evidence

- `./build.sh sha3-variant compact` and `OXIDE_ELASTIC=1 OXIDE_ELASTIC_PLACE=medium OXIDE_ELASTIC_POSTROUTE=1 ./build.sh sha3-variant oxide` reproduce the selected replacement partitions against the accepted locked static design. Each requires setup/hold/pulse-width timing, clean routing/DRC, and full `pr_verify` against all three existing configurations before emitting programming images. The accepted implementation record identifies the actual placement flow; post-route recovery retains the first route and verifies its source ledger.
- The pinned Oxide reference passes 160 independent message checks across single/double buffering and continuous/gapped traffic. The improved core passes 79 vectors in two traffic modes, framing/reset checks, and integrated-shell tests with random DMA splits and five verified recoveries.
- Primary physical sample files: `current-physical.json`, `oxide_elastic-physical.json`, `compact-postboot-physical.json`. The improved-core report uses the post-boot run when available. Earlier compact and fast samples remain retained. Benchmark source hashes, manifests, hardware cycle counts and all individual timings are included; `*-board.log` and `uart.log` capture the real console.
- The comparison image intentionally preserves Oxide's inability to encode an empty message; its empty case is excluded. Our improved core computes empty-message padding in hardware and is tested for it.
- `fast/`, `compact/`, `oxide/` and `oxide_elastic/` retain routed resource, timing, compatibility and source-hash evidence. Historical implementation reports remain distinct from this run.
