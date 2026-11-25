# Physical SHA3-256 comparison: 1 GiB of generated text

On 2026-11-16, the Zybo generated **1,073,741,824 bytes** of random printable
text directly on its shared SD card. Only the 13,179-byte program and 917-byte
configuration were uploaded over UART. The payload was not transferred to or
from the PC.

Both physical cores processed the same file. All six measured hashes and all
six prefix warmups matched the independent on-board software SHA3-256 reference.
This is a real Zybo result, not simulation or QEMU.

| Median of three trials | Oxide Quartz | Compact |
| --- | ---: | ---: |
| Full SD-file hashing time | 44.839728 s | 44.824387 s |
| Full-file throughput, decimal MB/s | 23.946 | 23.954 |
| Sum of synchronous DMA-call times | 10.890646 s | 4.658352 s |
| Sum of file-read times | 33.823367 s | 40.017077 s |
| Full-file sample range | 44.830793–44.857243 s | 44.820124–44.844236 s |

The full-file throughput ratio is **1.00034×**, with overlapping ranges: this
does **not** establish a meaningful end-to-end speedup. The DMA-call time ratio
is **2.33788×**, or about 57.2% less time for compact in that portion.
The stable total time and compensating file-read waits are consistent with an
SD throughput bottleneck and Linux readahead overlapping FPGA work. A faster
core does not remove that storage limit.

DMA-call timing includes the driver and hardware backpressure; it is not pure
Keccak compute time. The full timer includes file reads, the local API, driver,
DMA and core. Generation, software verification, UART traffic and partial
reconfiguration are excluded. Each total comprises its measured read calls,
DMA calls and remaining API overhead. Medians of the components need not sum
exactly to the median total because they can come from different samples.

## Input and method

- Board path: `/root/hash-bench-1gib-20261116-16288d0a/random-1gib.txt`.
- SHA-256: `125844319f0bd1e7310751e6b8a42cc057ab044944dc4cd5d2b2ecc0b029f5e6`.
- SHA3-256: `e8af7302ce25e585e530bbc336c6e3c05e7396e6b5320f86aeb33fbe193727b5`.
- `os.urandom` mapped uniformly to 64 ASCII characters; 127 characters plus LF
  per line, for 8,388,608 lines. The generation pass took 100.482 seconds.
- A separate persisted-file read checked the text and both software digests.
  Its 161.316 seconds includes SD reads, format validation, SHA-256 and SHA3;
  it must not be described as a standalone software SHA3 benchmark.
- Each measured run uses 1,024 DMA transfers of 1 MiB. The six FPGA elapsed
  counters exceed 2^32 cycles and are retained as full 64-bit values.
- Order: Quartz, compact, compact, Quartz, Quartz, compact. Each trial has a
  verified 16 MiB prefix warmup followed by file-scoped
  `POSIX_FADV_DONTNEED` and sequential-read advice. Cache eviction is advisory;
  unrelated system caches are not globally dropped.
- Kernel `6.6.40-dfx-hash-wifi`, pinned installed API and firmware. Both SHA3
  variants share ID 1, so every load switches through observed SHA-256 ID 2.
  Every partial checksum and actual reload time is recorded.

The full file is larger than usable board RAM. These SD-file results have a
different input path from the earlier 16 MiB RAM-file and DMA tests and are not
substitutes for those benchmark numbers. No FPGA build or installed software
was changed. Oxide Quartz remains the unchanged, credited reference described
in the [architecture mapping](../../docs/architecture-comparison.md).

## Evidence and restoration

[Raw board report](board-results.json), [event log](board-events.jsonl),
[validated summary](summary.json), [upload checksums](upload.log),
[hash boot](hash-boot.log), [initial state](initial-board.log),
[intermediate radar restore](radar-restore.log),
[file persistence after reboot](restored-status.log),
[final hash boot](final-hash-boot.log), and [final hash check](final-hash-check.log).

The runner restored compact, verified its empty digest, and restarted the hash
service. An initial return to radar was superseded by the user's instruction
to leave the board on hash. It was booted back into **hash**, with the service
running and a verified empty SHA3 digest. The next ordinary boot is also hash,
with the original profile-file checksum. Radar settings were not modified.
The generated file and board-side `results.json` remain on the SD card; the
file size and report checksum were checked after reboot.

The [method and reproduction guide](../../docs/sha3-1gib.md) links the small
generator and report validator. The generator's exact uploaded hash is recorded
in the board report. `artifacts.json` binds local sources and measurements;
run `sha256sum -c SHA256SUMS` here to verify the evidence bundle.
