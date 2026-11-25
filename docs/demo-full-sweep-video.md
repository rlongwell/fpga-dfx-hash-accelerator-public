# Architecture and live FPGA replay sweep

[Watch the full video](media/sha3-comparison-full-sweep.mp4) · [Physical recording evidence](../results/demo-full-sweep-20261116/README.md)

This 4:04 edition retains the architecture walkthrough, explains the FPGA memory
experiment, then shows Hash Lab starting a new physical sweep. Its progress bars
advance from actual board responses. Waiting is labeled **Fast-forward 32x**;
the cursor motion, completion and result walkthrough remain at normal speed.
The earlier [2:04.8 replay explanation](demo-replay-video.md) is a separate
supplement, not the replacement for this full demonstration.

## Story and timing

| Time | Content |
| --- | --- |
| 0:00 | SHA3-256 comparison with Oxide Quartz |
| 0:13 | Quartz byte-stream adapter and two block buffers |
| 0:39 | Compact input buffering and direct state absorption |
| 1:09 | Padding and framing refinements; separately labeled standalone synthesis |
| 1:38 | FPGA block RAM pattern, continuous hash state and hardware timer |
| 2:19 | 25 sizes, warmup and seven measured rounds |
| 2:37 | Real GUI board check, Start sweep and accelerated waiting |
| 2:58 | New run's 1 GiB times, throughput graph and speedup graph |
| 3:39 | Matching-build routed resource counts |
| 3:53 | Oxide, AI-assistance and media credits |

The architecture opening shows the original DMA-fed AXI Stream interface. The
BRAM experiment feeds that same hardware interface from the FPGA replay reader.
This movie does not attribute the BRAM improvement to SSH or network speed.

## The recording's own measurements

The final capture is job `e0ac322556182145dce29990` over wired SSH. Both SHA3-256
cores run on the physical Zybo Z7-20 at 100 MHz, using the same 128 KiB byte
pattern. Messages double from 64 B through 1 GiB. One warmup and seven measured
rounds per core and size produce **400 hashes, including 350 measured samples**.
All 400 digests match independent PC software references. Core order alternates
between rounds; the cores do not run simultaneously.

| 1 GiB replay | Oxide Quartz | Compact |
| --- | ---: | ---: |
| Hardware cycles | 1,073,741,926 | 450,024,163 |
| Time | 10.73741926 s | 4.50024163 s |
| Throughput | 99.9999905 MB/s | 238.5964827 MB/s |

The gain is **2.385965×**. Each size's median exactly matches the previous
independent physical sweep. The new GUI graphs use this recording's own job
results. They label message size in B/KiB/MiB/GiB and throughput in decimal MB/s.
The timer spans hardware START through digest, including reader and framing.
Pattern loading, SSH traffic, reconfiguration and reference hashing are excluded.

The matching routed hash partitions use **5,854 versus 4,572 LUTs**, and
**4,222 versus 1,774 flip-flops**: **21.90% and 57.98% fewer**, respectively.
Shared replay memory is counted separately. The historical standalone synthesis
numbers in the padding chapter are explicitly a different experiment.

Earlier PS/API measurements found that tiny-request setup costs and variation
could favor Quartz. That is a different timing boundary; the BRAM replay results
here favor compact at every tested size. These measurements do not represent
Oxide's production SPI-NOR system or a power comparison.

## Capture, narration and music

The raw [GUI capture](media/sha3-replay-sweep-live.webm) retains the complete run.
The [cursor receipt](../results/demo-full-sweep-20261116/cursor-log.json) binds
control clicks to the real job ID. The pointer follows a
minimum-jerk curve and invokes the dashboard's ordinary authenticated handlers.
It does not replace result data. Focus boxes, rather than pointer movements,
identify the values being discussed.

After the run, the results page was recaptured from that same saved job to remove
intro copy, recording controls and the extra units explanation. The separate
[results receipt](../results/demo-full-sweep-20261116/results-cursor-log.json)
binds this cleaned layout and its focus boxes to the original job. No numbers
were edited or regenerated. The original complete capture is retained. A short
initial hold preserves narration timing; the edit also removes the discarded
intro copy from the progress picture without covering controls or measurements.

Chrome's tab capture excludes browser chrome. The recording hides the automation
overlay and native cursor. The selected capture includes all chart axes; its
content settles at 1920×966 after Chrome's capture controls appear. The 1080p
export preserves aspect ratio with charcoal padding. A first capture had clipped
axes; its valid physical measurements remain separately retained under
`first-capture/`, and its video was rejected for the edit.

The short live-sweep bridge was generated twice with the already selected
**Jarnathan / Eleven v4** voice, stability 0.62, similarity 0.75 and clone strength
0. Both takes were downloaded and transcribed. Take 1 fits the real result click
more closely. Existing reviewed architecture and replay narration is reused.
Every stem receives the same pitch-preserving **1.06×** pace adjustment. The
TTS inputs use “shah three, two fifty-six”; final audio is checked with word
transcription and a separate phoneme recognizer.

**Cyber Runner — 2050 / Artlist** plays throughout. The existing analyzed 170 BPM
edit grid supplies bar-aligned repeats and 120 ms crossfades. Arrangement changes
at 2:47 and 3:28 support the accelerated sweep and speedup walkthrough. Narration
ducks the score without gating it. The mixer verifies nonzero music in every
second and targets −16 LUFS with a −1.5 dBTP ceiling. The final AAC measures
−16.16 LUFS and −1.72 dBTP, with 0.1 dB of additional encoding headroom. Source music is not copied
into the repository; its checksum and edit positions are retained.

## Reproduce and review

The renderer verifies all media and evidence hashes, recomputes the new sweep's
medians, and refuses to render the fixed narration if its rounded claims differ
from the recorded results. It does not overwrite earlier exports.

```sh
build/demo/video-v3/.venv/bin/python demo/render_video_full_sweep.py \
  --music '/path/to/2050 - Cyber Runner.mp3' \
  --work build/demo/full-sweep-rebuild \
  --output build/demo/sha3-comparison-full-sweep-rebuild.mp4
```

Dependencies are NumPy and FFmpeg plus the existing Python video helpers. Review
receipts, source hashes, raw samples, final transcripts, phoneme checks, stills
and mix continuity in the [evidence directory](../results/demo-full-sweep-20261116/).
The board remains on hash with its compact core and service healthy. No FPGA
rebuild, boot-profile change, installed payload replacement or SD reformat was
needed for this edition. Simulation and QEMU are not used as physical evidence.

Credit belongs to **Oxide Computer Company and the Quartz contributors** for the
unchanged reference. The pinned original source, MPL-2.0 notices and attribution
remain in [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md). This project was
developed with AI assistance. The original voice, music and pointer credits
remain in the earlier media guides and final credits.
