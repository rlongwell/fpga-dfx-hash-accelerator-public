# Narrated SHA3 demo, version 3

[Complete 3:37 video](../../docs/media/sha3-comparison-v3.mp4)

Edited 2026-11-15 local time (2026-11-16 UTC). This adds generated narration
and a continuous music arrangement to the previously sealed v2 physical demo.
It introduces no new FPGA measurements, board actions, or SD changes.

| Check | Result and evidence |
| --- | --- |
| Two generated takes downloaded | PASS; distinct input SHA-256 values in [artifact inventory](artifacts.json) |
| Existing voice and settings retained | PASS; David / Multilingual v2, speed 1.04, stability 0.87, similarity 0.64, style 0.5, speaker boost on; [before/after check](voice-generation.json) |
| Narration text preserved | PASS; only seven supported SSML pause tags were added |
| Take choice | Take 1; narrower measured loudness range, 3.2 LU versus 5.9 LU; [comparison](take-comparison.json) |
| Narration cuts | PASS; all 417 ASR-recognized source words fall inside retained edits; no speech rate or pitch change |
| Final speech verification | PASS; [per-chapter transcript](final-chapters-transcript.json) recovers the key counts, speedups, exclusions and final live explanation; [checks](validation.json) |
| Music throughout | PASS; a 217-second stem with nonzero audio in every second, short endpoint fades, no gate-to-silence; [continuity](music-continuity.json) |
| Music structure | [Onset/energy analysis](music-analysis.json), [tempo review](music-tempo-review.json), and bar-aligned edit decisions |
| Mix levels | −15.99 LUFS integrated, −1.83 dBTP, 4.4 LU range after AAC encoding; [measurement](final-loudness.json) |
| Complete movie | PASS; H.264 1080p, 30 fps, 6,510 frames, 217 seconds, ten chapters, stereo 48 kHz AAC; [probe](export-probe.json), complete decode without errors |
| Clean picture | PASS; reviewed all chapter views and live result/ending frames; no browser debugging banner or Codex pointer; [validation](validation.json) |
| Physical capture timing | PASS; all 1,200 original live frames remain at 1×. Same-time frame comparison after encoding: SSIM 0.999769. Only the final still is held two extra seconds. |
| Existing evidence unchanged | PASS; all 132 benchmark, 15 demo, 9 first-recording and 11 v2-recording sealed files verified |

The selected delivery was assessed using transcript and signal checks. This
does not claim a human listening comparison. ASR confuses some proper names
and binary unit names; its transcript is diagnostic, not the authoritative
script. The original narration and on-screen KiB/MiB labels are preserved.
The initial mix review prompted a further 4 dB reduction in the music during
speech. Final chapter transcription disables voice-activity filtering so music
cannot cause speech to be excluded from that check.

The musical build reaches the resource chapter near 01:22. A strong arrangement
change falls near the start of the speed comparison at 02:02. A final lift follows
the spoken digest match near 03:21. The soundtrack is **Cyber Runner by 2050**,
from Artlist, using the owner's existing download. The source credit is visible
on the credits slide and in movie metadata. The original MP3 remains local;
see [audio rights and provenance](../../THIRD_PARTY_NOTICES.md#demo-audio).

The source video is [v2](../demo-recording-v2-20261115/README.md). The fresh
8 KiB physical request in that capture remains separate from the 16 MiB
comparative benchmark. The graphs continue to use the same sealed physical
data. Illustrations were slowed slightly where speech needed more room; the
recorded live clicks, digest, timing and backend results were not replaced.
The live segment begins at 02:55 and its final still extends to 03:37.

Reproduce with `demo/render_video_v3.py`, the
checksum-bound edit list, the v2 source movie,
selected original voice take, and matching local soundtrack. The full command
and dependencies are in the [video guide](../../docs/demo-video.md).
Local work, stems and review frames remain under ignored `build/demo/video-v3/`.

`SHA256SUMS` seals this evidence directory. `artifacts.json` binds the external
video, both takes, exact script and renderer to this record. Earlier evidence
and silent masters remain unchanged.
