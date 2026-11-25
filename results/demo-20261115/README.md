# Hash Lab validation

The desktop dashboard was exercised against the physical USB-connected Zybo
Z7-20 on the shared `hash` profile. [Validation](validation.json) records the
reviewed source hashes and UI checks. Timestamps inside receipts are UTC.

| Check | Result | Evidence |
| --- | --- | --- |
| Upload cancellation and recovery | PASS | First job in [physical acceptance](physical-acceptance.json), followed by successful jobs |
| Empty, 137-byte boundary, 1 MiB + 17-byte two-buffer inputs; all three engines | PASS: 9 verified digests | [Physical acceptance](physical-acceptance.json), [run log](physical-acceptance.log), adjacent per-job UART logs |
| Real browser file chooser, theme switch without losing input, all three engines | PASS: 3 verified digests | [README file receipt](gui-file-picker.json) |
| Final sample run shown in the screenshot | PASS: 3 verified digests | [8 KiB receipt](gui-sample.json), [screenshot](../../docs/assets/hash-lab.png) |
| Actual partial loads and SHA3 restoration | PASS | Positive manager-load durations for SHA-256/BLAKE2s, then a verified empty SHA3 restore in each successful job |
| Service restart and saved boot profile | PASS | Final board event in each GUI receipt; [post-test status](post-test-board-status.log) |
| Offline validation, recovery and HTTP-boundary tests | PASS: 12 tests | [Offline log](offline-tests.log); separate from hardware results |
| Existing SHA3 performance evidence | PASS: unchanged 132-file capture | [Offline evidence audit](existing-evidence-audit.json) |
| Light/dark rendering, theme persistence, animations, charts, export, presentation controls | PASS | Explicit UI checks in [validation](validation.json) |

The boundary/cancellation acceptance preceded the addition of per-job demo
source-hash metadata. Both later GUI receipts bind the final server, UART bridge
and board agent hashes. The production local API, service, driver and hardware
images were unchanged throughout.

These live numbers are individual local-API requests. Their timer includes the
on-board RAM input, driver, DMA and core; it excludes USB upload and partial
reconfiguration. They are not substitutes for the separate seven-sample, 16 MiB
[performance study](../sha3-performance-20261115/comparison.md). Architectural
animations are labelled illustrations, not internal signal captures.

The board is left on the original `hash` boot profile, compact SHA3 loaded, and
the hash service running. Boot bitstream, DTB, and saved profile hashes match the
pre-demo values. Demo payloads/helpers were removed from `/tmp`; user SD data and
installed boot assets were retained.
