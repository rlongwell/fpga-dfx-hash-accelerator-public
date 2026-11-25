# Accepted compact SHA3 deployment

The physical Zybo boots the compact SHA3 full image and remains on the original
`hash` profile. All 81 post-boot local PS API/CLI checks pass across SHA3-256,
SHA-256 and BLAKE2s-256, including empty inputs, boundaries, multi-buffer inputs,
abort recovery, and actual partial switching away and back. The final service
request verifies SHA3 after restoring the compact partial from the comparison.

The installed full image is
`cbd8a4cf221032c15b11d6d0962ce070b221b5dd9b5081b0677742a97485ff40`.
The unchanged DT is
`3d2809a8f625f698e720bc6254e9520ceb233d2d3c79192dcfe0933bbe6e25ed`.
The matching runtime manifest is
`0ea0df9299508deac45af403960d484f892c723b0d029177e504bb02eb773ab3`.

All 18 staged payload file checksums match the installed files. The staged trees
are `build/sha3-profile/accepted-rootfs` and `build/sha3-profile/accepted-boot`.
Only the selected partition was rebuilt; the compatible static system, kernel,
driver, device tree, SHA-256 and BLAKE2s images were retained. Deployment used the
existing USB UART. No SD formatting, bootloader replacement, or other-profile
replacement was performed.

The original boot files, manifest and payload inventory remain under
`/boot/profiles/hash/before-sha3-fast-20261115/`; the directory name was established
by the promotion helper before the compact variant was selected. The final audit
verifies the original backup hashes and unchanged `/boot/profile.env`.
The rescue profile remains available. See the profiling guide for rollback.

`acceptance.json` binds the measured results, deployed identities and final logs.
`comparison.md` separates physical measurements from routed resource counts and
simulation predictions. The board wall clock is unset; chronology uses host UTC
in `uart.log`. Timed durations use a monotonic clock. External Ethernet throughput,
long-duration stress, and power measurements were not performed in this run.
