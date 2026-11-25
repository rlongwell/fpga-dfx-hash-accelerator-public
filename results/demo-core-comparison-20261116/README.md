# Physical core comparison and narrated demo — 2026-11-16

[Final 4:36 video](../../docs/media/sha3-comparison-architecture.mp4) ·
[Script and reproduction](../../docs/demo-architecture-video.md) ·
[Architecture source mapping](../../docs/architecture-comparison.md)

The 75-second GUI take at **3:21** hashes the same file through the physical
Oxide Quartz and compact SHA3-256 partitions on the USB-connected Zybo Z7-20.
It is recorded at normal speed. The preceding diagrams explain the source
architecture, and the earlier benchmark charts retain their Nov 15 evidence.

## Physical results

The input is 16,777,216 bytes (16.78 decimal MB), repeating bytes 0–255. The PC
computes its independent reference before transfer. Lossless gzip reduces the
UART payload to 65,411 bytes; the board verifies the expanded size and SHA-256
before hashing. Compression affects upload time, not the hash workload.

| Core | Median of 7 | Sample range | MB/s | Digest checks |
| --- | ---: | ---: | ---: | --- |
| Oxide Quartz | 211.687 ms | 211.450–211.941 ms | 79.25 | Warmup + all 7 pass |
| Compact | 113.815 ms | 113.720–113.902 ms | 147.41 | Warmup + all 7 pass |

This run measures **1.86× local-file API throughput** for compact. Both cores
use 16 DMA transfers per sample, the same static shell, driver and 100 MHz
clock. The timer includes RAM-file reads, driver calls, DMA and the core; it
excludes USB upload, decompression, reconfiguration and the PC reference.
Kernel: `6.6.40-dfx-hash-wifi`.

- Input SHA-256: `341aacac661ccb210720bedaa9ead5d668fe5ea41a73532fc147c71e34040df1`.
- SHA3-256: `b1870b48476671247200e7af392fe66d90bd62786daae75c70baf17843192d23`.
- [Recorded job](recorded-job.json): `5437bbfc579c24f2b5bb894e`, all raw samples,
  firmware identities, source hashes and restoration checks.
- [UART log](recorded-uart.log), [independent result checks](physical-check.json)
  and [cursor/action receipt](cursor-log.json).
- [Acceptance run](acceptance-job.json) completed before filming. An earlier
  [interrupted attempt](interrupted-job.json) was cancelled before file upload
  when the foreground server terminated; it contributes no results to the film.

Both variants report algorithm ID 1, so each load deliberately switches to
SHA-256 (ID 2) first, then loads the checksum-verified SHA3 image. The compact
image is restored the same way, an empty digest is verified and the installed
hash service restarts. Installed software remains checksum-pinned even though
the shared SD kernel now has the `-wifi` suffix.

These new local-file results are **separate** from the
[Nov 15 physical DMA/PS measurements and routed resources](../sha3-performance-20261115/comparison.md).
The RAM-file input path and shared kernel revision differ. Do not substitute
these absolute times into the earlier 2.36× DMA / 1.91× API comparisons.
Resource counts are existing implementation-tool reports, not a measurement
made by the GUI. No RTL was changed or rebuilt for this recording. This capture
does not retest SHA-256, BLAKE2s, audio, vision or external equipment.

## Restoration and SD preservation

[Initial state](initial-board.log): radar running, hash selected for the next
ordinary boot. The authorized reboot loaded hash; [boot checks](hash-boot.log)
verified the matching full bitstream and device tree. Temporary comparison
files were placed only in `/tmp`. No installed bitstreams, DTBs, manifest,
service files or user data were replaced.

After capture, the existing one-shot radar U-Boot helper restored radar.
[Restore log](radar-restore.log), [final status](restored-status.log) and
[live GUI screenshot](radar-restored.png) show radar ready and reconnected.
The saved next-boot choice remains hash. The profile file hash is unchanged:
`9dc14825fb83ef1fe366b1a2a9451395d67a966a0800ad4a4a9289dc612f46fc`.
The radar GUI settings hash before and after is
`5bd68aabd57ed45f1fb4e4e9a7f226252ad7095e728754fe514658e1c8882a53`.

## Offline and media validation

- [19 offline tests pass](offline-tests.log), including image/sample validation,
  bounded decompression, forced reconfiguration and failure restoration.
  These are software tests, not FPGA simulation or physical measurements.
- Two narration takes were generated with the user's existing voice settings;
  [selection record](voice-selection.json), both paragraph transcripts and
  the generation screenshot are retained. Take 2 supplies four revised sections.
- [Final word-timed transcript](final-transcript.json) covers all ten chapters.
  [Final acoustic phonemes](final-phonemes.json) recognize `/ʃɑː/`, not spelled
  letters, in the encoded live narration. Review used automated transcription,
  phoneme recognition and signal analysis; no human-listening claim is made.
- [Export probe](export-probe.json): 1920×1080, 30 fps, 8,280 frames, 276 seconds,
  ten chapters. Full audio/video decode passed. [Media QA](media-qa.json)
  records −16.05 LUFS integrated loudness and −1.50 dBTP true peak.
- [Live frame check](live-frame-check.json): all 2,250 decoded live frames match
  the complete normalized source take. No live timing is accelerated.
- [Music continuity](music-continuity.json): Cyber Runner by 2050 / Artlist is
  present in every second. The local licensed track is not included separately.
- Final architecture, credits and comparison frames were visually inspected.
  The source-based diagrams and tab capture contain no browser chrome,
  debugging banner or computer-use cursor. Result boxes follow the narration;
  the custom pointer is used only for controls.

Oxide Computer Company, Quartz contributors and nathanaelhuffman are credited
in the film and source documentation. The unchanged reference is pinned to
`c0ccf08525f30c43f4c773c2295dabe80f97cd0e`; MPL-2.0 notices are retained.
The project acknowledges AI assistance. No Oxide production-system or power
claim is made.

`artifacts.json` binds the source, voice and final movie hashes. Verify the
evidence bundle from this directory with `sha256sum -c SHA256SUMS`.
