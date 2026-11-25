# Recorded SHA3 comparison

The [video](../../docs/media/sha3-comparison.mp4) combines the animated
architecture comparison with a fresh GUI request to the physical Zybo. Captures
were made on 2026-11-15 local time (2026-11-16 UTC). It is a captioned recording
without an audio track. The [guide](../../docs/demo-video.md) lists chapters and
maps the architectural claims to RTL and retained implementation reports.

## Evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Pinned performance data and sources | PASS, offline audit | [Source audit](source-audit.json): 132 sealed files, six physical reports, 48 recomputed measurement rows, 17 source files |
| Chart values and hashing-time conversion | PASS | [Presentation data](presentation-data.json), unchanged physical summary and report |
| Fresh board identification and installed assets | PASS, physical UART | [Board probe](board-probe.json), [console log](board-probe.uart.log) |
| Fresh 8 KiB GUI SHA3 request | PASS, physical FPGA DMA | [Receipt](gui-sha3.json), [console log](gui-sha3.uart.log): matching hardware/PC digest, 505,914 ns local API, 26,905 elapsed hardware cycles |
| Recovery and saved profile | PASS, physical UART | Receipt's verified empty SHA3 restore, restarted service, operating FPGA manager, unchanged profile.env hash; active and next profile both `hash` |
| Final movie | PASS | [Probe](video-probe.json), full FFmpeg decode, reviewed chapter frames; H.264, 1920 × 1080, 30 fps, ten chapters |
| UI and source checks | PASS | [Validation record](validation.json), dark/light review, saved theme, all nine presentation scenes, capture cancellation, automatic and manual recording stop |

The 8 KiB live request is a single check, not the source of the 16 MiB performance
comparison. It used the already-loaded compact SHA3 partition. It makes no new
claim of a partial reload or fresh Quartz benchmark. The earlier physical
benchmark and full GUI validation captures remain unchanged.

## Edit and reproducibility

The MP4 contains comparison seconds 0–30, live-capture seconds 0–32, then comparison
seconds 30–166. Live playback remains at its original speed. A caption identifies
the separate single-request check. The excess hold after the live result is
trimmed. No digest, measured time or benchmark value is replaced.

Chrome changed the capture resolution when its sharing bar appeared. The export
keeps frame timestamps while normalizing each frame to the final dimensions.
An initial export failed duration validation because FFmpeg reinitialized its
concat graph on that resize. It was rejected and retained only under ignored
`build/demo/video/rejected-resize-export.mp4`. The corrected exporter preserves
the full live segment and all chapter boundaries.

[Validation](validation.json) records SHA-256 identities of both raw WebM captures,
the final MP4, presentation code, export script, and preview images. Raw captures
are retained locally under ignored `build/demo/video/`. This directory's
`SHA256SUMS` seals the evidence files themselves. No FPGA rebuild or installed
software change was needed for this video.
