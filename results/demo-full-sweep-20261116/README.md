# Full architecture and live FPGA replay video

[Watch the 4:04 movie](../../docs/media/sha3-comparison-full-sweep.mp4) · [Production guide](../../docs/demo-full-sweep-video.md)

This edition preserves the architecture walkthrough, explains FPGA block RAM
replay, and shows a new physical sweep started from Hash Lab over wired SSH.
Progress comes from actual board responses. Only the wait is accelerated, with
**Fast-forward 32x** on screen. The measured values use FPGA cycles, independently
of the speed of the recording, SSH, Linux, or the PC.

## Physical evidence

Selected job: `e0ac322556182145dce29990`, recorded November 16, 2026 in America/Chicago
(November 17 UTC). The physical Zybo Z7-20 ran both SHA3-256 variants at 100 MHz.
The 128 KiB deterministic pattern is `(i*131+(i>>8)) & 255`, repeated or truncated
to the requested message length. Hash state continues across all pattern passes.

- **25 sizes:** 64 B through 1 GiB, doubling each step.
- **400 verified hashes:** one warmup plus seven measured runs for each core/size.
- **350 plotted samples:** warmups excluded; medians recomputed from raw rows.
- **16 verified DFX batches and 16 PS/DMA recovery checks.**
- **All 25 medians exactly reproduce the earlier independent physical sweep.**
- **No reboot:** the boot ID is unchanged; current and next profile remain hash.

| 1 GiB input | Oxide Quartz | Compact |
| --- | ---: | ---: |
| Hardware cycles | 1,073,741,926 | 450,024,163 |
| START to digest | 10.73741926 s | 4.50024163 s |
| MB/s | 99.9999905 | 238.5964827 |
| Matching routed partition LUTs | 5,854 | 4,572 |
| Matching routed partition FFs | 4,222 | 1,774 |

Large-message throughput improves **2.385965×**, with **21.90% fewer LUTs** and
**57.98% fewer FFs** in the matching hash partitions. Both hash partitions use
zero BRAM/DSP blocks; the shared shell's replay memory is counted separately
(65 RAMB36 and one RAMB18). This is not a memory-free design.

The digest for 1 GiB is
`160d628e26bf5db7e1c8aaa27c773f031bd5d8af11d6757f2e17a79115ae1e13`.

The timer includes the reader, framing and selected hash core from START to
completed digest. Pattern loading, SSH, reconfiguration and PC software hashing
are outside it. Compact wins all sizes in this BRAM experiment. Older tiny-file
PS/API results have a different timing boundary and can favor Quartz; these
results do not replace them. No simulation or QEMU results stand in for hardware.
The resource source is the unchanged [matching routed implementation](../gem-direct-20261116/implementation-bram64/summary.json).
The standalone synthesis example in the opening is separately labeled.

## Files and provenance

- `recorded-job.json`: final GUI job, events, software references and identities.
- `plan.json`, `results.json`, `summary.json`, `batch-00.json` through `batch-15.json`:
  full plan, all raw samples, computed medians and physical recovery receipts.
- `board-ssh.log`, `board-final-status.log`, `board-last-status.log`: physical console evidence.
- `wired-ssh-file-api.json`: separate 8 KiB PS/DMA file test, all three algorithms passed.
- `validation.json`: measurement validation and recorded board state.
- `cursor-log.json`: real board-check, Start and View results actions tied to the job.
- `results-cursor-log.json`: the same completed job recaptured after cosmetic text
  removal. It explicitly says `results_only`; it is not another physical sweep.
- `capture-source-sha256.json`, `results-capture-source-sha256.json`,
  `source-provenance.json`: source identities at capture and final differences.
- `final-*.png`: final exported frames, including both sides of the results cut.
- `final-mix-transcript.json`, `final-mix-phonemes.json`: chapter transcription
  and separate checks for the spoken “shah” sound in the final audio.
- `bridge-take-*-transcript.json`: both new ElevenLabs takes. Take 1 was selected.
- `audio-continuity-after-picture-edit.json`: encoded AAC identity across the
  visual cleanup; the reviewed transcription, phonemes and loudness still apply.
- `music-continuity.json`, `final-aac-loudness.json`, `premix-loudness.json`:
  nonzero background score in every second and measured final audio levels.
- `export-probe.json`, `final-review.json`, `unit-tests.log`: format and QA evidence.

The complete [raw sweep capture](../../docs/media/sha3-replay-sweep-live.webm)
retains the original wording. The separately retained
[clean results capture](../../docs/media/sha3-replay-results-clean.webm) supplies
the final result panels. The edit removes discarded intro copy from the progress
picture without covering controls or measurements. Capture startup frames are
trimmed, and a short hold preserves narration timing. VFR timestamps are
normalized before cutting so the older layout cannot flash at the transition.
Original raw recordings are not rewritten.

The first valid run is retained under [first-capture](first-capture/README.md).
Its video was rejected because of clipped chart axes. Its measurements are not
substituted into the selected final job.

The board script, SSH transport, replay runner and pinned hardware files are
unchanged since the measured run. Post-capture changes add completed-job reload,
results-only recording and cosmetic copy/layout cleanup. The plotting helper now
supports replay-only plans. Older sealed manifests retain their original source
hashes, which resolve at parent commit `f41b9a59649d68cbb0c9da081125a4ae1989b96a`;
old evidence directories and exports are not rewritten.

## Review and attribution

The final movie has 7,313 frames, 1920×1080 at 30 fps, with AAC narration and
**Cyber Runner by 2050 / Artlist** throughout. All voice stems use the selected
Jarnathan / Eleven v4 configuration and a pitch-preserving 1.06× pace adjustment.
The additional bridge was generated twice, downloaded and transcribed. The
original music is not redistributed as a standalone file; its checksum is in
the edit plan. Voice recognition is automated and can normalize proper names
or numbers; phoneme checks separately address pronunciation.

Oxide Computer Company and the Quartz contributors receive credit in the video,
script and [third-party notices](../../THIRD_PARTY_NOTICES.md). The pinned
reference source and MPL-2.0 notices remain intact. The video also identifies
AI assistance. This is a comparison of these specific implementations and
integration paths, not a claim about Oxide's production system or power use.

Run the checksum check from the repository root:

```sh
sha256sum -c results/demo-full-sweep-20261116/SHA256SUMS
```

All new board payloads were temporary RAM files. Installed images, shared-card
data and saved profile settings were not replaced. The compact hash core and
service are healthy; Wi-Fi stays down, and the board stays on hash.
