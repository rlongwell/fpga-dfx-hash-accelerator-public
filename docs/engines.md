# Hash engines

These SystemVerilog engines are original implementations of the published algorithms. They are separate from the unchanged, MPL-2.0 Oxide reference. The core arithmetic has no vendor primitives or software hashing calls. Each uses the common 64-bit stream interface; compile exactly one `rtl/rm/*.sv` file to select a DFX reconfigurable module at build time.

| Engine | Algorithm source | Datapath |
| --- | --- | --- |
| `hash_sha3` | [FIPS 202](https://doi.org/10.6028/NIST.FIPS.202), SHA3-256 | 1600-bit Keccak state, direct byte absorption, one full round per cycle |
| `hash_sha256` | [FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final), SHA-256 | 16-word sliding schedule, one compression round per cycle |
| `hash_blake2s` | [RFC 7693](https://www.rfc-editor.org/rfc/rfc7693), BLAKE2s-256 | Four parallel G functions, each split across four clocks, 80 round clocks per block |

## Stream and result behavior

`axis_bytes` retains one 64-bit input beat and presents the valid bytes in ascending lane order. This supplies partial-beat handling and lets the engine stop during computation without losing the remainder of a beat. It validates low-contiguous nonzero keep masks, total message length, and final-message TLAST. The static shell converts DMA chunk boundaries into this final-message convention; cores never see DMA TLAST directly.

`start` is accepted in idle or failed state, clears the previous transaction, and samples the length. An additional start while processing or while a result is pending is ignored. Length zero finalizes an empty message with no stream handshake. `digest_valid` and all digest bytes remain stable until `digest_ready`. Each digest's first conventional hexadecimal byte occupies bits 7:0. Reset aborts all state. Protocol failures latch error, prevent further transfers, and require reset or a fresh accepted start.

SHA-256 rejects byte lengths of `2^61` and above instead of allowing its 64-bit bit count to wrap. BLAKE2s uses a 64-bit cumulative byte counter. These are streaming cores; no allocation scales with the message length.

## SHA3 implementation

Input bytes XOR directly into the selected state byte. A full 136-byte rate block starts 24 Keccak rounds. After the final message byte, the core injects SHA3 domain/padding bytes (`06`, ending in `80`; `86` if combined). An exact rate boundary therefore gets another padded block. Empty input follows the same padding path.

The final state's first four lanes are the digest and are held until acceptance. There is no separate 256-bit digest register or 1088-bit block buffer in this implementation. It still has the 64-bit stream staging register. This structure may trade storage for state-update multiplexing; register removal alone does not prove lower LUT use or higher performance. A wider external bus still delivers bytes serially in this initial implementation.

## SHA-256 implementation

Incoming bytes populate a 512-bit block in big-endian word order. Padding inserts `80`, zero bytes, and the 64-bit bit length, producing an additional block when necessary. Compression uses eight working words and shifts a 16-word schedule. A separate commit cycle accumulates the final working words into the eight chaining words; this removes the final round's extra carry chain. Digest serialization reverses bytes within each word to match the external convention. The padding path is deliberately straightforward and sequential.

## BLAKE2s implementation

This implementation supports unkeyed sequential BLAKE2s with a 32-byte output, fanout 1 and depth 1. Keying, salt, personalization, and tree hashing are not exposed. Message words are little endian. Each block carries the cumulative number of message bytes. Final partial blocks are zero-filled, and the last-block flag is applied to the compression state. An exact 64-byte final block is compressed as final without an extra block. Empty input compresses a zero block with count zero and the final flag.

Four G functions execute columns, then diagonals, over ten rounds. Each G is split into four steps to limit combinational adder depth. Four message words are prefetched into registers during the existing c/b steps, then used by the next a/d step. This removes the sigma/message-selection logic from the addition path without introducing stalls. It still uses 80 round cycles plus initialization and chaining-state commit per block. No compression-round software executes in the RTL.

## Recorded simulation evidence

All three engines pass `scripts/test_engines.sh <sha3|sha256|blake2s>` with Verilator 5.020. Each run contains 79 hashlib vectors, two source-traffic modes, randomized result holding, repeated messages, spurious start rejection, five malformed-framing cases, and resets during absorption and compression. SHA-256 additionally checks its excessive-length rejection. See [the harness details](../sim/engines/README.md) and the logs in `build/sim/<algorithm>/results.log`.

| Engine | Empty-message cycles | `abc` cycles | 1 MiB continuous cycles |
| --- | ---: | ---: | ---: |
| SHA3-256 | 26 | 30 | 1,357,004 |
| SHA-256 | 124 | 125 | 2,244,733 |
| BLAKE2s-256 | 83 | 87 | 2,506,754 |

Cycles run from the accepted start through the first valid result, before output backpressure. These measurements include stream staging, algorithm absorption, padding, and computation. They are not DDR/DMA or network measurements. Subsequent [physical profiling](sha3-performance.md) records actual DMA and application throughput separately from these simulation results.

## Separate SHA3 experiments

The initial DFX build uses `hash_sha3`. The following experimental modules have their own wrappers and are not substituted into the production configuration without a new compatible DFX build.

The newer `hash_sha3_fast` registers framing validation before it reaches the state-register enable, closing the earlier wide design's timing path at 100 MHz. `hash_sha3_compact` additionally restricts padding decode to the 17 rate lanes instead of using a dynamic read/modify/write across all 25 lanes. It retains the fast design's exact simulation cycle counts and uses 4,498 LUTs / 1,774 FFs in the standalone route, with +0.500 ns setup slack. Its full-system route uses 4,531 partition LUTs / 1,774 FFs and closes timing at +0.212 ns. The [profiling guide](sha3-performance.md) describes the incremental build, physical comparisons, and provenance. Earlier experiments below retain their original results.

`hash_sha3_wide` stages one AXI beat and XORs up to eight bytes into the state in one clock. A masked 128-bit alignment network updates at most two adjacent state lanes, avoiding cascaded dynamic byte writes across the full state. It accepts arbitrary low-contiguous keep masks and retains the rest of a beat when absorption crosses the 136-byte rate boundary. The buffered remainder resumes after permutation; intermediate DMA chunk alignment therefore does not change the message. A beat is accepted only when the staging register is empty, so maximum acceptance is one beat every two clocks; this is not an eight-byte-per-clock sustained-input claim.

`hash_sha3_serial` shares a 64-bit theta/rho/pi lane datapath. Each round computes five parity lanes in one clock, transforms 25 individual lanes into a separate intermediate bank, then computes five 320-bit chi rows. This requires 31 clocks per round (744 per permutation) and an additional 1600-bit intermediate bank plus 320 parity bits. The experiment explicitly trades throughput and extra storage for reduced parallel arithmetic; lower LUT cost is not assumed before implementation results.

Both experiments pass the same 79-vector, two-mode, protocol-error, and reset suite. Run `scripts/test_engines.sh sha3_wide` or `scripts/test_engines.sh sha3_serial`.

| SHA3 implementation | Empty-message cycles | `abc` cycles | 1 MiB continuous cycles |
| --- | ---: | ---: | ---: |
| Direct byte absorption | 26 | 30 | 1,357,004 |
| Wide absorption | 26 | 28 | 439,500 |
| Shared lane/row rounds | 746 | 750 | 6,908,924 |

For reproducible common-interface measurements, run `scripts/build_engines.sh` (all seven engines) or pass selected engine names. It first reruns simulation, then synthesizes, places, physically optimizes, and routes each core with Vivado 2024.2 at a 10 ns period and 2 ns input/output delays, matching the baseline's OOC methodology. Reports, source hashes and simulation evidence are retained under `results/engines/`; `results/engine_measurements.json` collects completed measurements. The flow preserves negative timing and area results rather than asserting an optimization succeeded.

OOC ports do not have physical partition-pin locations. Vivado therefore warns that external path routing/timing is incomplete. Internal register-to-register timing is reported separately, and the actual DFX system's routed timing remains the authority for the deployed design. Clock estimates inferred from slack are explicitly estimates; there has been no maximum-frequency sweep. Physical DMA measurements at the fixed 100 MHz clock are recorded in the separate profiling report.

The initial SHA-256 implementation added the chaining state in the final round's clock and missed the 100 MHz OOC constraint by 0.567 ns. Its source and negative timing result are retained in `results/engines/sha256_pre_commit/`. The revised implementation separates this addition into one extra clock per block and passes the full engine and integrated-shell simulation suites. Its routed OOC setup slack is +0.329 ns at 100 MHz, with 1,741 LUTs and 1,249 FFs, as recorded in the current `sha256/` result directory.

The initial BLAKE2s implementation passed OOC timing but missed the complete DFX system's 100 MHz target by 0.654 ns. The selected prefetch implementation raises standalone internal register slack from +0.085 to +1.356 ns, at a cost of 1,122 LUTs and 152 FFs. All continuous/stressed simulation cycle counts remain identical. Previous OOC evidence and source are retained in `results/engines/blake2s_pre_prefetch/`; the failed full-system route is retained separately. These improvements establish standalone timing, while the full-system DFX report remains the deployment acceptance check.

## Completed OOC measurements

These are the final routed common-interface reports at 100 MHz. All five use zero BRAM and zero DSP. The timing scope and OOC boundary limitations above apply.

| Engine | LUTs | FFs | Setup WNS (ns) | Hold WHS (ns) | 100 MHz result |
| --- | ---: | ---: | ---: | ---: | --- |
| SHA3 byte absorption | 4,981 | 1,786 | +0.732 | +0.104 | Pass |
| SHA-256, separate commit | 1,741 | 1,249 | +0.329 | +0.058 | Pass |
| BLAKE2s, prefetched message words | 4,127 | 1,665 | +0.489 | +0.120 | Pass |
| SHA3 wide absorption | 5,704 | 1,795 | -0.738 | +0.137 | Fail |
| SHA3 serial rounds | 4,706 | 3,714 | +0.292 | +0.032 | Pass |

The serial implementation saves only 275 LUTs against the direct byte implementation, uses 1,928 more FFs, and takes about five times as many cycles for a large file. It also uses more LUTs and FFs than the original single-buffer Oxide baseline. This is an unfavorable tradeoff for the initial system; it remains a measured experiment.

The wide core's worst constrained path runs from `s_axis_tkeep[4]` through framing validation to a state-register clock enable. Its internal register-to-register setup slack is -0.104 ns. This version therefore does not support a claim of 100 MHz operation. The later `sha3_fast` and `sha3_compact` variants implement registered protocol validation; this earlier wide variant remains unchanged for comparison.

The unchanged wide physical route was also **reanalyzed at 80 MHz**, retaining 2 ns input/output delays and `BUFGCTRL_X0Y0`. It passes with +1.762 ns setup, +0.137 ns hold, and +2.396 ns internal register slack. There are no unclocked registers, unconstrained internal endpoints, or combinational loops; reset is the one intentional input-delay exception and is false-pathed. This is a clock-constraint reanalysis of the existing route, not a separately routed 80 MHz build or a production DFX configuration.

The 80 MHz clock and measured simulation cycles predict 190.84 MB/s for a 64 KiB message and 190.87 MB/s for 1 MiB, before DMA/network costs. These are predictions, not hardware measurements. The original negative 100 MHz result remains in the comparison table. Full evidence and source hashes are in [the separate clock analysis](../results/sha3_wide_clock_80mhz/analysis.json); the clock-adjusted checkpoint stays under `build/engines/sha3_wide_80mhz/`.

To reproduce that clock analysis after building the wide core, run from the project root:

```bash
project_root="$PWD"
mkdir -p build/engines/sha3_wide_80mhz
(
  cd build/engines/sha3_wide_80mhz
  "${VIVADO:-/opt/amd/xilinx/Vivado/2024.2/bin/vivado}" -mode batch -nojournal \
    -source "$project_root/scripts/vivado/engine_clock_analysis.tcl" \
    -tclargs "$project_root" sha3_wide 12.5
)
python3 benchmarks/clock_results.py \
  --build-dir build/engines/sha3_wide_80mhz \
  --output-dir results/sha3_wide_clock_80mhz
```
