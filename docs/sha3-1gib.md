# One-GiB random-text comparison on the Zybo

[Recorded results and UART evidence](../results/sha3-text-1gib-20261116/README.md):
44.840 s Quartz versus 44.824 s compact for the whole SD file; the ranges
overlap. DMA calls total 10.891 s versus 4.658 s. The storage-bound file result
does not show a meaningful overall speedup despite the faster DMA portion.

This experiment generates **1,073,741,824 bytes** of text directly on the
board's ext4 SD filesystem. Only the small Python program and core configuration
are uploaded over UART. The payload stays on the board.

The [generator and runner](../benchmarks/sha3_profile/board_text_1gib.py) uses
`os.urandom` to choose uniformly from 64 printable ASCII characters. Every line
contains 127 random characters and an LF, for 8,388,608 lines in total. It writes
in 1 MiB chunks, flushes the file to storage, then independently reads it back
to check the text, its SHA-256 identity and its software SHA3-256 digest.
Generation and software verification are outside the FPGA timers.

Both physical SHA3-256 cores hash that same regular file through the installed
`LocalHasher.hash_stream` API. Each measured trial follows a verified 16 MiB
prefix warmup. There are three full-file trials per core, in the order Quartz,
compact, compact, Quartz, Quartz, compact. File-scoped
`POSIX_FADV_DONTNEED` is requested before every trial; no global cache drop is
performed. This is advisory cache eviction, not a claim that every cache in
the storage device is cold.

The timer covers SD reads, the local API, driver calls, DMA and the core. It
excludes generation, software reference hashing, UART traffic and partial
reconfiguration. Additional counters separately total file-read calls and
synchronous DMA calls. The latter includes driver overhead and hardware
backpressure: it is **not pure Keccak compute time**. The FPGA's elapsed cycle
counter also includes time spent waiting for the next file chunk.

A 1 GiB input exceeds the board's usable RAM, so storage can limit file-level
throughput even when the core is substantially faster. These results must not
be substituted into the earlier small RAM-file or DMA benchmark charts.

The runner verifies the pinned static design, DTB, software and partial images.
Before every SHA3 load it selects SHA-256 (ID 2), observes that ID, then loads
the selected SHA3 partial (ID 1). Both SHA3 implementations share ID 1; a switch
away is necessary to force an actual reload. Every result must match the
separate software reference. The installed compact image and hash service are
restored after measurement, with a verified empty digest. Installed files and
the saved boot choice are never replaced.

To reproduce on the matching installed hash profile, upload the runner and
[`demo/core_variants.json`](../demo/core_variants.json) with the checksum-verifying
UART uploader, then run the following in the board's Linux console, choosing
a fresh output directory:

```sh
python3 -u /tmp/board_text_1gib.py \
  --variants /tmp/core_variants.json \
  --output-dir /root/hash-bench-1gib-new-run
```

The program refuses an existing directory, requires room for the file plus
1 GiB of remaining free space, uses bounded application buffers and has a
30-minute execution bound. The generated file and `results.json` remain in
the new directory. Do not run it while another program owns the accelerator.

The host-side [report validator](../benchmarks/sha3_profile/report_text_1gib.py)
checks all samples, warmups, image identities and the restoration receipt:

```sh
python3 benchmarks/sha3_profile/report_text_1gib.py board-results.json \
  --output summary.json
```

The reference implementation is the unchanged Oxide Quartz source and local
elastic adapter already credited in the [review guide](review-guide.md).
This comparison concerns this Zybo integration, not an Oxide production system.
