# Small-message explanation — 2026-11-15

[Watch the updated 3:37 demo](../../docs/media/sha3-comparison-explained.mp4) ·
[Script and reproduction](../../docs/demo-explained-video.md).

The replacement chapter at 2:12–2:41 explains the difference between higher
bulk throughput and lower tiny-request latency. Its displayed 64-byte medians
and observed ranges were recomputed from all 14 raw physical DMA samples.
Quartz had the lower median, but ranges overlap; the exact cause of the gap
was not isolated. The narration says overhead and variation **can** outweigh
streaming gains, without attributing the result to inherently faster Quartz
hash logic. See `benchmark-check.json` for input hashes and timing scope.

Both replacement voice takes were generated in the existing ElevenLabs tab
with Jarnathan / Eleven v4, without changing the voice controls. Both transcripts
contain the intended explanation. Take 1 was selected for its clause pauses
and processed with the existing leveling and pitch-preserving 1.06× pace.
This is automated transcript/signal QA, not a human listening claim.

The earlier narration before 2:12 and the retained credits/live narration are
sample-identical at the pre-mix stem level, preserving the prior acoustic
“sha” checks. The final encoded chapter, credits and live segment were also
transcribed with word timestamps. Reveal cues are within 0.14 seconds of the
corresponding selected-take word timings.

Export: 1920×1080, 30 fps, 6,510 frames, 217 seconds, ten chapters. Full decode
passes. The 5,640 retained frames compare to the preceding movie at SSIM
0.999804. The full 40-second physical capture and two-second hold remain at 1×;
this revision did not access the board or rerun benchmarks. The live digest
and control-only pointer/result boxes remain intact.

Music has nonzero content in every second, including the extended chapter.
Final AAC loudness is −16.06 LUFS, with a −1.66 dBTP true peak. A ten-bar score
insert shifts the later arrangement cue by 14.118 seconds against a 14-second
picture extension. Earlier media and sealed evidence remain unchanged.

`artifacts.json` binds the new movie, both voice takes, script and renderer
sources. `SHA256SUMS` seals this evidence directory. Screenshots document the
voice generation and final visual review; the browser screenshot is evidence
only and is never used in the movie.
