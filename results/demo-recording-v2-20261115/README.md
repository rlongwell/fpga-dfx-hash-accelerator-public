# Architecture-first comparison video, version 2

[Watch the 3:28 video](../../docs/media/sha3-comparison-v2.mp4) · [Chapter and source guide](../../docs/demo-video.md)

Recorded 2026-11-15 local time (2026-11-16 UTC). Architecture animations come
first, followed by routed resource usage, physical hashing measurements,
limitations, Oxide attribution, and the live GUI check at 02:48.
The video is captioned and silent; the user will supply generated narration.

| Check | Result | Evidence |
| --- | --- | --- |
| Installed image, Linux and saved boot choice | PASS, physical UART | [Probe](board-probe.json), [UART log](board-probe.uart.log) |
| Fresh 8 KiB SHA3 request | PASS, physical FPGA DMA | [Hash receipt](gui-sha3.json), [UART log](gui-sha3.uart.log): 506,370 ns on-board local API, 26,925 elapsed hardware cycles, hardware digest equals PC SHA3 |
| Compact engine and profile retained | PASS, physical UART | Verified empty SHA3 restore, service restarted, FPGA manager operating, active/next profile `hash`, unchanged boot assets and profile.env hashes |
| Smooth cursor activates real controls | PASS | [Cursor timeline](cursor-log.json) binds the probe/hash job IDs and actual clicks; sample selected at 7.2 s, hash submitted at 10.2 s, response complete at 16.1 s |
| Clean capture | PASS, visual review | [Validation](validation.json), all architecture chapters, live click/result frames, cut boundary and last frame; no debugging notice or Codex pointer |
| Existing benchmark | PASS, offline audit | [Audit](source-audit.json): 132 sealed files, six physical reports, 48 recomputed rows, 17 source files; no fresh comparative benchmark claimed |
| Movie export | PASS | [Probe](video-probe.json), complete decode: H.264, 1920 × 1080, 30 fps, 208 s, 6,240 frames, ten chapters, no audio |
| Voiceover pipeline | PASS, synthetic fixture only | [Validation](audio-validation.json): all ten quiet test tones aligned to chapter starts, silence padding, oversized clip rejected; no generated voice has been included |
| Backend checks | PASS | [12 tests](unit-tests.log), including restoration on failure and local API request validation |

The cursor uses a pinned, licensed Lucide graphic with eased motion and click
pulses. At each click, the app invokes its normal button handler and waits for
real API responses from the physical board. These are guided actions, not a
claim of manual mouse operation. Backend timings, digests and success states
are not replaced or synthesized. The architecture animation is illustrative,
not an internal signal trace. The physical measurement charts reuse the sealed
comparison; the live request is a separate single correctness check.

The first exploratory take contained the automation pointer. It was rejected;
only the later clean capture is in this MP4. The previous v1 movie and sealed
results remain unchanged. Raw captures are local in `build/demo/video-v2/`;
[validation](validation.json) records their hashes and the identities of the
final source files and MP4. The live browser capture omits some duplicate frames
after the pointer fades; the export repeats the final static frame for less than
one second to retain the documented 40-second hold. It changes no measured value
or action timing. No board software, FPGA image, or SD setting was updated.
