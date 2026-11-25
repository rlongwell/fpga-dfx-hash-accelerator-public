# Charcoal demo evidence — 2026-11-15 local / 2026-11-16 UTC

[Final 3:23 movie](../../docs/media/sha3-comparison-charcoal.mp4) · [Edition guide](../../docs/demo-charcoal-video.md) · [Validation](validation.json)

**PASS:** the final 1920×1080 / 30 fps movie has 6,090 frames, ten chapters,
complete decoded audio/video, and continuous music. Final audio measures
−16.05 LUFS integrated and −1.60 dBTP. The 40-second physical portion runs at
1×; comparison against the assembled source over all 1,200 live frames gives
SSIM 0.999819 after encoding. Two final still seconds allow the narration to finish.

This edition uses neutral charcoal colors, narration-led diagram reveals,
brief data transfers along wires, curved pointer paths only for real control
clicks, and result focus boxes. `cue-alignment.json` maps the key visual reveals
to the spoken phrases; their start times differ by at most 0.274 seconds.
`contact-sheet.jpg` records sampled final frames. Dashboard light/dark and
presentation light-mode screenshots are UI review evidence, not movie frames.
The exported movie excludes browser chrome, the debugging banner, and the Codex
pointer. The live pointer is the credited presentation asset.

## Actual physical run

Final hash job: `8985bca4a27124fec651c8fd`.
Probe job: `82361f58c0409a8928ead7ff`.

- Backend: `physical-fpga-dma`, SHA3-256, one DMA transfer of **8,192 bytes**.
- Independent FPGA/PC digests match:
  `4efa6e9c526f34cb7ac46294a8370f94468977267d4ec2e84d659bcb4fcd96fa`.
- Local API time: **509,496 ns**; hardware cycle count: **27,073**.
- Installed bitstream, device tree, manifest and service identity are recorded
  in `hash.json` and the UART logs. Kernel: `6.6.40-dfx-hash`.
- The compact SHA3 empty-message restoration check passed; the service was
  restarted. All three board reports within the hash job retain the same
  `/boot/profile.env` checksum, profile `hash`, and next boot `hash`.
- Payload and helper used temporary RAM paths and were removed. No shared SD
  settings, FPGA artifacts, or boot files were changed for this video.

`cursor-actions.json` records the actual click, highlight, probe and hash times.
The 16.78 MB benchmark was **not rerun**. Its figures still come from the sealed
[physical performance evidence](../sha3-performance-20261115/comparison.md).
No simulation or QEMU result is presented as this physical run.

## Audio and pronunciation

Both generated voice takes and word-timed transcripts are retained. The selected
Jarnathan / Eleven v4 controls were unchanged: stability 0.62, similarity 0.75,
clone strength 0. Take 2 was chosen for the phrase pauses. The input uses
`shah three, two fifty-six`; postproduction applies pitch-preserving 1.06× pacing.

`phoneme-control.json` recognizes the old spelled-out opening as `ɛ s eɪ tʃ eɪ`.
`phoneme-takes.json` recognizes both new openings as `ʃ ɑː`.
`phoneme-remaining.json` checks the selected take's other three mentions;
`phoneme-mix.json` checks all five mentions in the continuous music mix.
`phoneme-export.json` independently checks the encoded movie opening. This
acoustic-label check addresses the ambiguity that ordinary ASR normalizes both
pronunciations to “SHA3.” It is automated QA, not a human listening claim.

`final-chapters-transcript.json` contains words extracted from the exported
movie with timestamps. Content checks cover SHA3-256/Oxide Quartz, 16.8 MB,
8.2 kB, 23%/58%, 169/72 ms, 2.36×/1.91×, AI assistance, USB exclusion and scope.
The benchmark remains exactly 16,777,216 bytes; only its displayed/spoken units
changed. Original music provenance and continuous per-second levels are retained.

## Reproduction and integrity

The edit list binds the committed silent
source master, selected original voice take, local music checksum, all cuts,
pacing, music joins and chapter timing. The [guide](../../docs/demo-charcoal-video.md)
has the render command. Raw browser captures remain local and are checksummed
in `artifacts.json`. Source and model revisions used for QA are recorded.
`demo/check_voice_phonemes.py` and `demo/transcribe_video.py` reproduce the checks
with the dependencies in `qa-environment.json`.

All twelve demo unit tests and Python/JavaScript syntax checks passed. Dark and
light modes were visually checked; selected input survived theme toggles and
`.settings/gui.json` remains ignored by Git. The six earlier evidence seals
still verify (**194 files**). Earlier videos and voice takes remain unchanged.

`SHA256SUMS` seals this evidence directory; `artifacts.json` binds the associated
media, scripts and presentation source. Generated voice, music, model and cursor
attribution retain their [separate rights boundaries](../../THIRD_PARTY_NOTICES.md).
