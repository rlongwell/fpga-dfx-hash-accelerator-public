# Charcoal SHA3-256 comparison

The [latest 3:37 edition](demo-explained-video.md) adds a narrated explanation of
small-message latency. This page retains the preceding 3:23 edition's edit record.

[Watch the 3:23 video](media/sha3-comparison-charcoal-clean.mp4) · [Evidence](../results/demo-charcoal-20261115/README.md)

This edition compares the project's compact **SHA3-256** core with **Oxide's
Quartz SHA3-256** reference. It uses neutral charcoal surfaces in both the
presentation and Hash Lab. Diagrams reveal one point at a time as it is narrated.
Brief packets illustrate the described wire transfers; lane highlights and
numerical counters no longer loop. Resource and timing figures appear with
their corresponding spoken claims.

The current export removes three requested on-screen lines: the recurring
diagram disclaimer, the recorded-measurements caption in the timing chapter,
and the scripted-cursor footer during the live demo. Narration, music, chapter
timings, measurements, and credits are retained. The [previous charcoal
master](media/sha3-comparison-charcoal.mp4) remains available. This edit and its
checks are recorded [separately](../results/demo-caption-cleanup-20261115/README.md).

The narration uses the selected Jarnathan voice with Eleven v4, stability 0.62,
similarity 0.75, and clone strength 0. Those generation controls were unchanged.
The input writes `shah three, two fifty-six` so **sha is one spoken word**.
Both original takes are retained; take 2 supplies the edit. Postproduction
speeds the voice up by 6% with pitch-preserving `atempo=1.06`. The script retains
the AI-assistance credit and avoids first-person authorship claims.

Whisper word timestamps check the content and guide the edit. A separate
[phoneme recognizer](https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft)
checks the actual sound: the old opening produces the letter-name sequence
`ɛ s eɪ tʃ eɪ`, while the new takes produce `ʃ ɑː` followed by “three.” All five
SHA3-256 mentions in the selected take were checked. This distinction matters:
ordinary transcription normalizes both pronunciations to “SHA3.” These are
automated acoustic/content checks, not a claim of a human listening review.

The benchmark input is unchanged at **16,777,216 bytes**: 16.777216 decimal MB,
rounded to **16.8 megabytes** in speech and **16.78 MB** on screen. The live
sample remains **8,192 bytes**, shown/spoken as **8.2 kB / kilobytes**. The units
change does not change any measured times, throughput, or resource counts.

Cyber Runner by 2050 continues throughout, ducked under speech. The score's
build accompanies resources, an arrangement change accompanies the Quartz
timing, and another lift precedes the physical digest reveal. The edit list
records the bar-aligned joins and cue times.

| Start | Section |
| --- | --- |
| 00:00 | Compact SHA3-256 vs. Oxide Quartz |
| 00:13 | Oxide's byte-fed block buffers |
| 00:32 | Compact direct absorption |
| 00:53 | Padding and framing |
| 01:12 | Routed resource counts |
| 01:32 | Shared physical testbench |
| 01:48 | SHA3-256 hashing times |
| 02:12 | Workload limits |
| 02:27 | Oxide and AI-assistance credits |
| 02:41 | Fresh physical-board demonstration |

The live segment is a new USB-UART run on the physical Zybo Z7-20. A scripted
pointer uses curved paths, gradual acceleration/deceleration, and a hover before
each real control click. It checks the board, selects the sample, and starts the
request, then fades away. Focus boxes identify the actual FPGA/PC digests and
hash time. The complete 40-second capture runs at **1×**, followed by a two-second
still. It is an independent correctness demonstration, not a rerun of the
16.78 MB performance benchmark. The shared SD settings and original hash boot
profile are retained.

Earlier [neutral](demo-neutral-video.md), [David](demo-video.md), and silent
masters remain available unchanged. The [comparison guide](demo-video.md#claims-and-source-mapping)
retains the RTL, resource, timing, and attribution mapping. Media have separate
[rights boundaries](../THIRD_PARTY_NOTICES.md#demo-audio).

Reproduce with Python, NumPy, FFmpeg/ffprobe and the matching local music file:

```sh
python3 demo/render_video_charcoal.py \
  --video docs/media/sha3-comparison-charcoal-source.mp4 \
  --voice docs/media/voiceover-charcoal-take-2.mp3 \
  --music '/path/to/2050 - Cyber Runner.mp3' \
  --work build/demo/charcoal-reproduction \
  --output build/demo/sha3-charcoal-reproduced.mp4
```

The edit list binds source checksums, voice
cuts, pitch-preserving pacing, music edits, and chapter boundaries. The
storyboard and presentation source specify
progressive reveals. Both renderers refuse to overwrite an existing master.

To reproduce the current caption cleanup from the retained charcoal master:

```sh
python3 demo/clean_video_captions.py \
  --output build/demo/sha3-charcoal-clean-reproduced.mp4
```

The cleanup edit list binds the source
checksum and the three frame-bounded caption regions. Audio is copied directly.
The presentation and live assembler sources also omit these lines in future
captures.
