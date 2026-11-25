# Neutral narration edition

[Watch the 3:22 video](media/sha3-comparison-neutral.mp4) · [Edit evidence](../results/demo-neutral-20261115/README.md)

This separate edition uses the owner's current **Jarnathan – Confident and
Versatile** voice with **Eleven v4**. Stability remains 0.5, similarity 0.75,
and clone strength 0. The earlier [David video](media/sha3-comparison-v3.mp4)
and all silent masters remain unchanged.

The script describes the design and measurements without “I,” “my,” or “we.”
It opens with the question of whether the implementation could be improved,
and its credits explicitly say the project was developed with AI assistance.
Oxide attribution, the measured results, and the limitations are retained.

**SHA is spoken as the letters S, H, A.** The readable script uses “S. H. A.
three”; the synthesis input uses the explicit letter names “ess, aitch, ay
three.” The v4 input uses punctuation for pauses, with no unsupported SSML
break tags. This follows ElevenLabs' [pronunciation and pacing guidance](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices).

The original generated takes are retained: take 1
and take 2. Take 1 supplies the movie.
The edit balances the quiet raw voice against the soundtrack with a slow gain
envelope and peak limiting. It changes neither voice settings nor pitch or
speech rate. Automated transcripts check content and edit coverage; they are
not a claim of a human listening comparison.

Cyber Runner by 2050 plays throughout. Two bar-aligned joins extend the source
track across the video. A musical build leads into resources, an arrangement
change accompanies the Quartz timing, and another lift leads into the live
digest reveal. Music is lowered during speech, with short endpoint fades.

| Start | Section |
| --- | --- |
| 00:00 | Opening |
| 00:10 | Quartz architecture |
| 00:30 | Direct absorption |
| 00:53 | Padding and framing |
| 01:14 | Routed resources |
| 01:33 | Shared physical testbench |
| 01:50 | Measured hashing time |
| 02:11 | Limits |
| 02:26 | Oxide and AI-assistance credits |
| 02:40 | Physical GUI demonstration |

Illustrations are retimed to the new delivery. The entire 40-second physical
capture remains at its recorded speed, followed by a two-second final still.
No board operation or benchmark was rerun for this edit. The live request is
the separately recorded 8 KiB correctness check from the
[sealed v2 capture](../results/demo-recording-v2-20261115/README.md).
The [comparison guide](demo-video.md#claims-and-source-mapping) retains the
full architecture, timing and resource source mapping.

Reproduce with Python, NumPy, FFmpeg, ffprobe, and the owner's matching local
music download:

```sh
python3 demo/render_video_neutral.py \
  --video docs/media/sha3-comparison-v2.mp4 \
  --voice docs/media/voiceover-neutral-take-1.mp3 \
  --music '/path/to/2050 - Cyber Runner.mp3' \
  --work build/demo/neutral-reproduction \
  --output build/demo/sha3-neutral-reproduced.mp4
```

The edit list binds source checksums, all
narration cuts, level-balancing parameters, music joins and chapter timing.
The exporter refuses to overwrite an existing movie. Media retain their
[separate attribution and rights boundaries](../THIRD_PARTY_NOTICES.md#demo-audio).
