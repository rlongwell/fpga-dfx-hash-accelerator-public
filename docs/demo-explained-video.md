# SHA3-256 demo: small-message latency explained

[Watch the 3:37 video](media/sha3-comparison-explained.mp4) · [Validation](../results/demo-small-messages-20261115/README.md)

The chapter at **2:12–2:41** now explains why Oxide Quartz can have a lower
whole-request time for small messages even though the compact core achieves
higher large-buffer throughput. Software and DMA setup dominate tiny requests;
there is little data for the wider input path to accelerate. Request overhead
and variation can outweigh that gain.

The screen reveals setup costs, then the 64-byte medians and observed ranges,
then the distinction between bulk throughput and tiny-request latency:

| 64-byte DMA request | Median | Observed min–max, 7 samples |
| --- | ---: | ---: |
| Oxide Quartz | 168.4 µs | 158.7–213.2 µs |
| Compact SHA3-256 | 187.3 µs | 183.7–219.4 µs |

The ranges overlap. The sealed physical results establish which integration
had the lower median in this run; they do not isolate the exact cause of the
gap or establish an intrinsic Quartz core-latency advantage. The explanation
uses “can outweigh,” not a claim that a particular cause was measured. The
[physical report](../results/sha3-performance-20261115/comparison.md) and
[review guide](review-guide.md) retain the timing scope and limitations.

Only this chapter's narration was regenerated. Both original downloads are
retained, using the existing Jarnathan / Eleven v4 configuration: stability
0.62, similarity 0.75, clone strength 0. Take 1 has clear sentence boundaries
for the visual cues; both takes transcribe correctly. The replacement receives
the same leveling and pitch-preserving 1.06× pacing as the prior narration.
Other chapters reuse the previous accepted voice take, including its verified
one-word “sha” pronunciation.

The inserted chapter lasts 29 seconds, extending the movie by 14 seconds.
Credits begin at 2:41 and the physical demonstration at 2:55. The complete
40-second physical capture and its two-second final hold remain at 1×. This
edit does not access the board or rerun any benchmark. Charcoal styling,
control-only pointer motion, result boxes, Oxide/AI credits, and all three
requested caption removals are retained.

Cyber Runner by 2050 continues throughout. A ten-bar insert on the established
170 BPM editing grid extends the score, with a short crossfade. Its later
arrangement cue shifts by 14.118 seconds, within 0.118 seconds of the picture
extension, preserving the lift into the digest reveal.

The presentation and movie use the same SVG scene code. The new chapter is
rendered directly from that code, so no browser chrome or computer-use cursor
can enter it. Previous movies and their evidence remain unchanged.

Reproduce with NumPy, CairoSVG, Node, FFmpeg and the matching local music:

```sh
python3 demo/render_video_explained.py \
  --video docs/media/sha3-comparison-charcoal-clean.mp4 \
  --voice docs/media/voiceover-charcoal-take-2.mp3 \
  --replacement-voice docs/media/voiceover-small-messages-take-1.mp3 \
  --music '/path/to/2050 - Cyber Runner.mp3' \
  --work build/demo/explained-reproduction \
  --output build/demo/explained-reproduced.mp4
```

The edit plan binds media checksums and all
voice/music cuts. The storyboard records the
revised chapter timing and script. The renderer refuses to overwrite a movie.
