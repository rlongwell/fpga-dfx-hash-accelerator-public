# Neutral narration and explicit S.H.A. pronunciation

[Complete 3:22 video](../../docs/media/sha3-comparison-neutral.mp4)

Created 2026-11-15 local time (2026-11-16 UTC), using the owner's current
**Jarnathan – Confident and Versatile / Eleven v4** configuration. The prior
David edition, its source files, and its evidence remain unchanged.

| Check | Result and evidence |
| --- | --- |
| Current voice configuration preserved | PASS; stability 0.5, similarity 0.75, clone strength 0; [before/after check](voice-generation.json) |
| Pronunciation | Input explicitly supplies the letter names “ess, aitch, ay three”; no unsupported SSML break tags |
| Neutral narration | PASS; no first-person authorship language; AI assistance acknowledged; Oxide credit and result boundaries retained |
| Two takes downloaded | PASS; distinct hashes in [generation record](voice-generation.json); [selection and measurements](take-comparison.json) |
| Speech edits | PASS; all 425 ASR-recognized source words retained inside the cuts; original speech rate and pitch preserved |
| Final content | PASS; key figures, AI credit, live explanation and exclusions recovered in [per-chapter ASR](final-chapters-transcript.json); [checks](validation.json) |
| Continuous music | PASS; source music remains present in every second, including its quiet breakdowns; [stem measurements](music-continuity.json) |
| Voice balance | Slow level envelope and peak limiting, distinct from the unchanged TTS controls; [parameters and applied gain](voice-leveling.json) |
| Encoded mix | −16.04 LUFS integrated, −1.68 dBTP; [measurement](final-loudness.json) |
| Movie | PASS; 202 seconds, 6,060 frames, H.264 1080p/30, stereo 48 kHz AAC, ten chapters; [probe](export-probe.json), full decode without errors |
| Picture | PASS; chapter views and final GUI result reviewed, without debugging banner or Codex pointer; [validation](validation.json) |
| Physical capture | All 1,200 live frames retain their timing at 1×; same-time SSIM 0.999769 after re-encoding. Two seconds of final still added. |
| Earlier evidence | All 182 sealed files across the five previous evidence bundles verified; all external artifacts bound by v3's inventory unchanged |

Automated transcripts normalize spelled letters to “SHA3” and can mislabel
proper names or binary units. They are diagnostic evidence, not a human
listening assessment. The explicit letter-name synthesis input and visible
KiB/MiB labels are preserved. Take 1 was selected for its clear edit boundaries
and slightly shorter delivery; no subjective voice-quality ranking is claimed.

Music remains **Cyber Runner by 2050 / Artlist**. Its rhythmic build leads into
resources, an arrangement change accompanies the Quartz timing, and another
lift precedes the live result reveal. The standalone source MP3 stays local.
The [media notices](../../THIRD_PARTY_NOTICES.md#demo-audio) retain its separate
rights boundary and identify the narration as generated media.

The physical footage is reused from the [sealed v2 recording](../demo-recording-v2-20261115/README.md).
No board work or new comparative benchmark is claimed. Figures, digest,
on-board timing and GUI outcomes are unchanged. Illustration timing adapts to
the new narration; the physical segment starts at 02:40 and runs at 1×.

The [edition guide](../../docs/demo-neutral-video.md) describes the published cut. `artifacts.json` binds the
delivered movie, source voices, scripts, and render code; `SHA256SUMS` seals this
directory. Local working media and review frames remain in ignored
`build/demo/video-v5/`.
