# Common-interface engine tests

Run `./scripts/test_engines.sh sha3` from any directory. Python's standard-library hashlib generates the expected answers; Verilator compiles the synthesizable RTL and a C++ bus driver. Artifacts stay in `build/sim/<algorithm>/`.

The vector set contains 79 messages, including empty input, byte values 00/ff, `abc`, rate and compression-block boundaries, 32 deterministic random lengths, 64 KiB and 1 MiB files, and variants with a byte dropped, duplicated, or moved. Each distinct payload has its own independently computed expected digest. Each vector runs twice: full-width uninterrupted beats, then randomized 1–8 byte beats and source gaps. The latter exercises partial keeps anywhere in a file, independent of algorithm block boundaries.

The driver holds offered AXI data while ready is low. It checks output stability while withholding digest-ready, including an ignored start request while the result remains pending. Additional tests reject zero/noncontiguous keep masks, excess input bytes, and early/missing message TLAST. Reset is applied during absorption and computation, followed by another known-answer transaction. Error recovery through a fresh start is tested separately from reset recovery.

`continuous_cycles` is measured from the edge accepting start to the first valid digest, before result backpressure. It includes stream adaptation, absorption, padding, and permutation/compression; it is **not** raw permutation throughput and is **not** a DDR/DMA or Ethernet measurement. `stressed_cycles` includes deterministic randomized bus delays. Cycle-to-time conversion is meaningful only at an implemented and timing-closed clock frequency.

The common `hash_rm` top allows the same driver to compile separate algorithm implementations. Tests never use a run-time hardware multiplexer as evidence of DFX.
