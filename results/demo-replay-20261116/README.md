# Replay video evidence

[Movie](../../docs/media/sha3-comparison-replay.mp4) · [Production and reproduction guide](../../docs/demo-replay-video.md)

This directory contains presentation artifacts and review records for the
block RAM replay edition. The actual physical data remain in the unchanged,
checksum-sealed [size sweep](../gem-direct-20261116/sweep-64B-1GiB/README.md).
No new board measurements or live GUI recordings were made for this edition.

The summary was recomputed from all 800 original sweep rows and compared
exactly with the retained summary. The video displays only the replay subset:
350 timed measurements, 50 warmups, 25 sizes, two cores. Every digest passed.
All seven measured trials for each replay core/size returned identical cycles.

| 1 GiB input | Oxide Quartz | Compact |
| --- | ---: | ---: |
| Hardware cycles at 100 MHz | 1,073,741,926 | 450,024,163 |
| START → digest | 10.73741926 s | 4.50024163 s |
| Decimal MB/s | 99.9999905 | 238.5964827 |
| Matching-build partition LUTs | 5,854 | 4,572 |
| Matching-build partition FFs | 4,222 | 1,774 |

The 1 GiB SHA3-256 digest is
`160d628e26bf5db7e1c8aaa27c773f031bd5d8af11d6757f2e17a79115ae1e13`.
The replay pattern is 128 KiB, with byte i equal to `(i*131+(i>>8)) & 255`,
repeated or truncated to each message length. Loading and reference hashing
are outside the hardware timer. This is not a storage/file-transfer timer.

- [Throughput PNG](throughput.png) and [SVG](throughput.svg)
- [Speedup PNG](speedup.png) and [SVG](speedup.svg)
- [1 GiB time comparison](one-gib-times.png)
- [Matching-build partition resources](resources.png)
- [Measurement and media validation](validation.json)
- [Original voice acoustic labels](source-voice-phonemes.json)
- [Music tempo review](music-tempo-review.json)
- [ElevenLabs generation evidence](elevenlabs-generated.png)

Both graph scenes include explicit horizontal tick units and a Message size
axis title. The final movie's representative frames, mixed-audio transcript,
pronunciation review, music continuity, loudness and export probe are retained
alongside these files. `SHA256SUMS` binds the delivered movie, script, edit plan,
source takes, renderer, figures and review evidence.

Source recognition is automated and may normalize spoken numbers or proper
names. The phoneme review separately checks the spoken “sha” sound, while
chapter-level recognition checks quantities and sentence completeness.

Oxide Computer Company and the Quartz contributors are credited in the movie,
script and [third-party notices](../../THIRD_PARTY_NOTICES.md). Original source
and license are preserved. The final credit also identifies AI assistance.
