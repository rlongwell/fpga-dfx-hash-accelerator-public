# Architecture and same-file physical comparison

[Watch the 4:36 demo](media/sha3-comparison-architecture.mp4) · [Architecture source mapping](architecture-comparison.md) · [Physical and media evidence](../results/demo-core-comparison-20261116/README.md)

The film begins with diagrams of both SHA3-256 architectures. The Quartz row
stays visible while the compact path appears below; outlines identify the
64-bit beat buffer, direct state absorption and digest readback. The Keccak
state and 24-round permutation remain visually unchanged. The following chapter
separates the compact core's padding/control refinements from the Quartz baseline.

| Time | Content |
| --- | --- |
| 0:00 | SHA3-256 comparison and scope |
| 0:13 | Oxide Quartz input, block buffers, permutation and digest register |
| 0:39 | Compact core, with changed blocks outlined below Quartz |
| 1:09 | Padding and registered framing checks |
| 1:38 | Routed partition resources |
| 1:58 | Shared physical benchmark method |
| 2:14 | Previously recorded DMA and local-API timings |
| 2:38 | Why tiny messages can favor Quartz |
| 3:07 | Oxide, contributors and AI-assistance credit |
| 3:21 | Fresh GUI comparison of the same 16.78 MB file |

The new 75-second GUI take runs at **1×**. It uses the real controls, transfers
one file to the board, reconfigures both physical cores and presents both results.
The pointer only clicks controls; boxes identify the times and matching digests.
The result shown is **211.687 ms for Quartz**, **113.815 ms for compact**, or
**1.86× local-file API throughput**, each a median of seven samples after warmup.
The timer includes RAM-file reads, driver calls, DMA and the FPGA. It excludes
USB transfer, decompression, reconfiguration and the PC reference calculation.
It is a fresh measurement on `6.6.40-dfx-hash-wifi`, separate from the dated
Nov 15 DMA/PS benchmarks used in the preceding charts. RAM-file input and
the shared-kernel revision differ, so these absolute times are not interchangeable
with the earlier benchmark values.

The sample repeats bytes 0–255. It compresses for the slow UART transfer, then
expands to the original 16,777,216 bytes in board RAM. The board checks that size
and SHA-256 before every core hashes the same file. Each request uses 16 DMA
transfers. Both image checksums, the forced ID-2 → ID-1 transitions, all samples
and the PC reference are retained in the receipt. The sample is not represented
as a user-selected document or an Ethernet transfer.

The board originally ran radar, while hash was saved for the next ordinary boot.
After the authorized comparison, radar was booted through its existing one-shot
U-Boot helper and the radar GUI was reconnected. The profile selection file and
radar settings have their original checksums. No installed FPGA files, manifest,
DTB or user SD data were replaced.

Four narration sections were regenerated: Quartz architecture, compact changes,
padding/control refinements and the live comparison. Both downloaded takes are
retained. Take 2 was selected after word-timed transcription of each paragraph;
the source includes every intended clause and resource count. An acoustic
phoneme check confirms `/ʃɑː/` for “sha.” This is automated speech/signal review,
not a claim of human listening. The same Jarnathan / Eleven v4 configuration was
kept: stability 0.62, similarity 0.75, clone strength 0. Leveling and the existing
pitch-preserving 1.06× pace are applied in the edit. Unchanged chapters reuse the
accepted voice sources. The script avoids first-person authorship claims.

Cyber Runner by 2050 / Artlist runs throughout. The score follows its previously
analyzed 170 BPM editing grid (85 BPM half-time), with bar-aligned repeats and
120 ms crossfades. Arrangement cues lead into resources, the Quartz timing and
the live digest box. Music ducks under speech without being gated to silence.
The raw licensed music file is not redistributed; reproducing the mix requires
the matching local track and appropriate rights for the intended use.

The presentation uses the same pure SVG functions as the movie exporter. No
browser chrome, debugging banner or computer-use cursor can enter the diagram
frames. The GUI was captured as a Chrome tab, not the desktop. The three
previously removed explanatory/capture captions remain absent. Earlier movies
and sealed evidence are preserved.

Reproduce with Node, CairoSVG, NumPy, FFmpeg and the matching music file:

```sh
python3 demo/render_video_architecture.py \
  --music '/path/to/2050 - Cyber Runner.mp3' \
  --work build/demo/architecture-reproduction \
  --output build/demo/architecture-reproduced.mp4
```

The edit plan binds source media hashes,
word-aligned narration cuts and score edits. The renderer requires a successful
cursor receipt matching the two-core board job and refuses to accelerate or
truncate the physical capture, or overwrite an existing movie. The
storyboard carries chapter timing and prose.
