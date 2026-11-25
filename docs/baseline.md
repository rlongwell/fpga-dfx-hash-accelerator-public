# Unchanged Oxide SHA3 baseline

The reference is Oxide Quartz commit `c0ccf08525f30c43f4c773c2295dabe80f97cd0e`, copied without edits into `reference/oxide`. The source manifest lists exact retrieval URLs and SHA256 hashes. Every build verifies those hashes. The original MPL-2.0 source notices and license are retained. No Git checkout or submodule is required.

## Reproduce

Run from the project root:

```sh
./scripts/test_baseline.sh
./scripts/build_baseline.sh
```

The simulation script downloads a pinned NVC 1.23.1 Ubuntu 24.04 x86_64 package, checks its SHA256, and unpacks it into `build/tools`; it does not install system packages. It needs Python 3, curl, dpkg-deb, and the package's shared libraries. This was verified on Ubuntu 24.04.5. `scripts/setup_nvc.sh` can prepare the tool separately.

The build script uses `/opt/amd/xilinx/Vivado/2024.2/bin/vivado`; `VIVADO_BIN` can select another location, but comparisons must retain the same tool version. Intermediate simulator libraries, vectors, logs and checkpoints remain in `build/`. Evidence copied into `results/` includes simulation logs, cycle CSVs, implementation reports and machine-readable summaries.

## What is preserved

Compilation order is `axist_if_2k19_pkg.vhd`, `calc_pkg.vhd`, `keccak_pkg.vhd`, then `sha3_256.vhd`, all in one work library using VHDL-2019. The generic AXIS package supplies the byte packet record and interface view; `calc_pkg` supplies the buffer-count selection function. The Keccak package has no other project dependencies.

`sim/baseline/baseline_wrapper.vhd` only exposes the record view as individual external ports and forwards the `DOUBLE_BUFFER` generic. Neither wrapper nor tests change the upstream state machine, buffer, permutation, padding or digest logic.

Vivado 2024.2 successfully parses the VHDL-2019 sources and synthesizes them natively. XSim's elaborator fails on the generic package's data-width expression with `[XSIM 43-3397]`, despite successful `xvhdl --2019` analysis; the captured failure is in `results/baseline_xsim_elaboration_failure.log`. NVC compiles, elaborates and runs the unchanged sources successfully. No source conversion is used.

The initial implementation came from [Quartz PR 516](https://github.com/oxidecomputer/quartz/pull/516). Compared with that PR's merge revision, the pinned core has only the later port-view spelling change from [PR 538](https://github.com/oxidecomputer/quartz/pull/538). Its permutation and sponge behavior are unchanged.

## Independent correctness checks

Python's `hashlib.sha3_256` generates every expected digest independently of the RTL. The generator uses seed 20261111 and emits 40 messages: 00, ff, ASCII a/abc, the 200-byte A3 vector, block boundaries 134/135/136/137 and 271/272/273, short lengths, a 4 KiB and 64 KiB message, and twenty further deterministic random messages. All four combinations of single/double buffering and continuous/gapped source passed: 160 message checks in total.

Each configuration additionally verifies stable digest retention, repeated messages without init, backpressure, an init held high with active input, asynchronous reset during absorption, asynchronous reset during permutation, and a correct recovery hash after each abort. The gapped source inserts one idle cycle before each seventh byte. The continuous double-buffer test asserts zero mid-message backpressure; long single-buffer cases must exercise backpressure. The testbench has a watchdog and exits unsuccessfully on any mismatch.

Empty input is **not representable** at the original byte-stream port. An idle core does not spontaneously produce the empty hash. Empty-file behavior belongs in the common-interface adapter and must be tested separately; it is not counted as a passing baseline vector.

## Interface details that matter

Input bytes transfer only on valid AND ready. Last marks the final byte of an entire message, not a DMA chunk. Digest byte zero occupies bits 7:0, so conventional hex display must visit bytes from least to most significant. Padding uses 06, 80 or their combined 86 byte; an exact multiple of the 136-byte rate needs a separate padding block.

Reset is asynchronous active-high and init is synchronous active-high. Both clear the sponge, output validity and in-flight work. Ready remains high while clear is held, so integration must mask input traffic during reset/init. A synchronous init has priority over an apparent handshake.

Digest-valid is a level rather than a pulse. It clears one clock after the first byte of the next message is accepted, and busy clears one clock after digest-valid rises. The digest register itself retains the old value until a later result or clear. An adapter must track its own transaction state and cannot treat an old valid level as the new result. The single-buffer core stalls 26 clocks at a full-block boundary, including WAIT_BLOCK; the documented 25 absorb/round clocks omit that additional wait state.

## Measured cycles and core throughput

CSV cycle counts include both the first accepted-byte clock and the final accepted-byte/result clock. Throughput below uses total message clocks, including final padding and permutation, for a continuous 65,536-byte source at a nominal 100 MHz. MB/s means decimal million bytes per second.

| DOUBLE_BUFFER | Input clocks | Result clocks | Input stall clocks | Simulated core MB/s |
| --- | ---: | ---: | ---: | ---: |
| false | 78,042 | 78,084 | 12,506 | 83.930 |
| true | 65,536 | 65,578 | 0 | 99.936 |

With the deterministic source gaps these values become 75.004 and 87.451 MB/s respectively. A one-byte message takes 162 inclusive clocks in either configuration because the byte-shift absorption buffer must also shift its padding. Complete per-message measurements are in the four `results/baseline_*_cycles.csv` files.

These are standalone core cycle measurements. They are not Ethernet rates, DMA measurements, PS software performance, or board measurements. The full design includes additional buffering and control and has separate implementation timing.

## OOC implementation comparison

Both configurations use `xc7z020clg400-1`, Vivado 2024.2, a 10 ns clock, 2 ns input/output budgets, rebuilt hierarchy and the same default synthesis/optimization/place/physical-optimization/route flow with four threads. The external asynchronous reset is false-pathed; a full system must synchronize deassertion. The OOC clock source is constrained to BUFGCTRL_X0Y0. The wrapper has no board I/O buffers, PS, DMA or DFX pblock. Unplaced OOC boundary ports have no partition-pin locations, so their external routing is absent; boundary delays are budgeting assumptions, and the register-to-register result is the core frequency comparison.

The expected standalone-Zynq DRC warning ZPS7-1 notes that this isolated core has no PS7 block; the full system must instantiate PS7. Reports distinguish post-synthesis estimates from placed-and-routed results. Register-frequency estimates use `1000 / (10 ns - register setup slack)` from a single routed run. They are estimates at this placement and constraint, not verified maximum frequencies; negative I/O/hold slack would still invalidate the target operating point. `results/baseline_implementation.json` and the routed timing/DRC/route-status reports provide the actual results.


Measured on 2026-11-11:

| DOUBLE_BUFFER | Synth LUT / FF | Routed LUT / FF | BRAM / DSP | Setup WNS | Hold slack | Estimated register Fmax |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| false | 4,522 / 2,989 | 4,504 / 2,989 | 0 / 0 | +0.617 ns | +0.020 ns | 106.576 MHz |
| true | 5,416 / 4,075 | 5,406 / 4,075 | 0 / 0 | +1.018 ns | +0.116 ns | 111.334 MHz |

Both runs have zero routing errors, zero DRC errors and no unconstrained internal endpoints. Clock-source constraints are present in both checkpoints. The register Fmax column is an estimate with the limitations above; the actual implemented target is 100 MHz.

## Direct-state digest variant

`rtl/sha3/oxide_no_digest/sha3_256.vhd` is a separately marked MPL-2.0 derivative. It removes only the `permute_reg.dig` field, its reset value and its final-round update, and derives output from `digest_of(perm_reg.st)` while digest-valid is high. Invalid output is zero. The original directory remains unchanged; `SOURCE.json` records both original and derived hashes. The entity remains `sha3_256`, so select exactly one implementation file per work library.

Run `./scripts/test_digest_variant.sh` and `./scripts/build_digest_variant.sh` after the baseline commands. Both reuse the same compile order, wrapper, tests, clock constraints, implementation commands and report parser. Each of the four simulation configurations passed forty independent messages and the reset/abort checks. All four cycle CSV files are byte-for-byte identical to the baseline measurements: this change targets area, not throughput. Results are written separately as `results/oxide_no_digest*`; the comparison JSON reports the measured resource and slack changes instead of assuming a saving.


| DOUBLE_BUFFER | Derived routed LUT / FF | LUT / FF change | Setup WNS | Hold slack |
| --- | ---: | ---: | ---: | ---: |
| false | 4,369 / 2,724 | −135 / −265 | +0.743 ns | +0.091 ns |
| true | 5,223 / 3,820 | −183 / −255 | +0.787 ns | +0.142 ns |

Both derived implementations meet the 100 MHz target with zero BRAM/DSP, routing errors or DRC errors. The single-buffer variant saves 3.0% of routed LUTs and 8.9% of FFs; the double-buffer variant saves 3.4% and 6.3%. These are resource deltas after synthesis optimization; they need not match the removed source register width exactly. Total setup WNS includes the now-combinational digest output and its 2 ns output budget. Register-only slack is +1.114 ns (single) and +1.481 ns (double), corresponding to estimates of 112.537 and 117.385 MHz under the same caveats as the baseline. No measured throughput gain is claimed.
