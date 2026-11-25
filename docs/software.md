# PS software and file protocol

## Driver and input paths

Local ARM applications can use [`software/hash_local.py`](local-ps.md) to hash memory buffers, regular files or binary streams directly. This uses the existing driver and bitstream without Ethernet. The TCP service is an alternative input source for the same hardware. The [2026-11-15 physical run](../results/local-ps-20261115/physical.json) verifies the local API/CLI, all three digests, real DMA and partial reconfiguration. Host mocks and QEMU results remain separate evidence.

`software/linux/hash_accel.c` is an original GPL-2.0 Linux platform driver. It owns the static registers and a DMAengine MM2S channel, allocates a 1 MiB coherent DDR buffer using the DMA controller's device, and exposes that buffer through `/dev/hash-accel`. A single open owner prevents two clients from interleaving file state. No userspace physical-address guesses or per-byte register writes are used.

The Python service receives socket data directly into the mapped buffer, submits a blocking DMA transfer, and reuses the buffer only after completion. Memory use does not grow with the file. This default implementation uses one buffer and serial chunk submission. An optional `--receive-mode prefetch` uses a bounded receiver thread and two cached buffers, but adds a copy into the DMA mapping. It regressed in the [physical 1 GiB TCP comparison](../results/ethernet-20261116/README.md), so `direct` remains the default. A 1 MiB buffer is well within the configured 26-bit DMA transfer length. Empty files submit no DMA transfer.

The [GEM/FPGA-RAM extension](gem-direct.md) preserves this interface and the
`LocalHasher` API. Its separate, exclusive test wrapper temporarily owns the
accelerator and, for packet mode, the Ethernet MAC; it restores the ordinary
service afterward. The new boot DT records the static-image SHA-256 so the
normal service can reject a mismatched partial-image manifest before opening
the device. Legacy accepted DTs without that property remain supported.

All file hashing in the production service goes through the RTL. Python hashlib is used only to validate firmware artifact checksums and optionally compare client results. The offline tests use a separate, explicit software reference backend; passing those tests is **not** a board DMA or Ethernet result.

The driver uses Linux FPGA Manager with `FPGA_MGR_PARTIAL_RECONFIG`. It explicitly requests firmware, then passes its buffer/count to the manager: AMD 2024.2's firmware-name helper overwrites image flags with manager-global flags, so that helper must not be used here. The manager is exclusively owned by this driver during operation; do not use its sysfs programming/flags interface concurrently. A pre-existing AMD DMA-BUF mode is rejected while isolation remains asserted. The Zynq manager drives PCAP and skips global PL reset for partial loads. Switching is serialized with all DMA operations. It refuses a switch during a file, terminates DMA, asserts static isolation, loads the image, releases partition reset/isolation, and verifies the algorithm ID. Failed programming remains isolated, including across a service restart. A file failure requests DMA termination and resets the engine before another file starts. If the DMA provider reports that termination failed, the driver quarantines the device instead of permitting another file.

A reported DMA termination failure latches `dma_fault`, asserts isolation, and rejects START, TRANSFER, RESULT and SWITCH. Closing/reopening the device does not clear the fault or release isolation. The module remains pinned while the fault is latched, preventing normal module unload from freeing a possibly active buffer or callback. An explicit `HASH_ABORT` retries termination; only a successful retry clears this DMA fault. Recovery retains isolation if `configuration_failed` is also set, until a subsequent successful image switch. ABORT returns the termination error when recovery fails.

The supplied target kernel carries the small GPL patch `software/embedded/xilinx-dma-terminate-error.patch`. The unpatched [AMD Linux 2024.2 DMA provider](https://github.com/Xilinx/linux-xlnx/blob/xlnx_rebase_v6.6_LTS_2024.2/drivers/dma/xilinx/xilinx_dma.c) ignores its reset error and returns zero from termination. The patch returns a failed reset before freeing descriptors; a successful reset after a failed halt is accepted because reset completion establishes quiescence. The client also checks `dmaengine_result`, since a completed cookie alone can conceal a vendor-reported transfer error. This behavior was inspected and cross-compiled; actual timeout, halt/reset failure and recovery remain board acceptance tests. An independently selected board kernel must contain equivalent error propagation. Do not force-remove the device or its device-tree node while a DMA fault is latched. If removal nevertheless encounters a termination error, the driver retains the DMA buffer/channel and logs that reboot is required rather than returning potentially active memory to the allocator.

The driver's static platform device must remain in the base device tree; do not remove it with an overlay while a mapping or file is open. It is not a hotplug interface. Manual bind/unbind is disabled. `/dev/hash-accel` defaults to mode 0600.

## Optional target build and deployment boundary

`./scripts/build_driver.sh` remains a host kernel API compile check. Its x86 `.ko` is not the target module. The optional plain-script flow below supplies a complete ARM deployment build without requiring PetaLinux or locking the project into a repository-management workflow:

```bash
# Run after the complete DFX build has passed.
./build.sh embedded all
python3 software/embedded/smoke.py
```

The flow downloads checksum-pinned sources and an ARM cross compiler under `build/embedded`; it installs no host packages. Individual stages are `bootstrap`, `kernel`, `module`, `device-tree`, `uboot`, `rootfs`, and `package`. The `package` stage requires the final three-image DFX manifest and refuses mismatched bitstreams. `EMBEDDED_JOBS` controls kernel/U-Boot parallelism (default two); Buildroot also defaults to two jobs. Ubuntu build prerequisites include a native C/C++ compiler, Make, Python 3.11+, tar, patch, unzip, rsync, bison, flex, bc, cpio, OpenSSL development headers and standard Buildroot host tools.

| Component | Pinned selection |
| --- | --- |
| Linux | AMD 2024.2, 6.6.40, commit `2b7f6f70a62a52a467bed030a27c2ada879106e9`, plus the documented DMA error patch |
| U-Boot | AMD 2024.2 / 2024.01, commit `7f6ec94aac7eacfec07bd45c83a6d17df4b7d383` |
| Cross compiler | Bootlin ARMv7 EABI hard-float glibc stable 2024.05-1, GCC 13.3.0 |
| Userspace | Buildroot 2024.02.12, Python 3.11.11 with OpenSSL, mmap, fcntl and sockets |
| Board initialization | GPL PS initialization exported from this build's `system.xsa` |
| Device tree | Pinned upstream Zybo Z7 board plus `software/embedded/zybo-hash.dts` and the static DMA/hash nodes |

Kernel options include OF, DMA_ENGINE, XILINX_DMA, FPGA, FPGA_MGR_ZYNQ_FPGA, the PS Ethernet/Realtek PHY drivers, ext4 and CMA. The board DTS extends the existing `&amba` AXI bus and retains the upstream Ethernet PHY, SD, UART and 1 GiB DDR description. FCLK0 is assigned 100 MHz. The source manifest is `software/embedded/sources.json`; local patches remain outside the downloaded source archive.

`build/embedded/images/sdcard.img` contains U-Boot SPL, U-Boot, the kernel, device tree, matching initial full bitstream and a root filesystem containing the ARM driver, service/client, benchmarks, manifest and all partial images. The boot script performs full initial PL configuration before Linux probes the accelerator. Runtime switching uses partial PCAP loads only. No service starts automatically. See [loading](loading.md) for SD and serial steps.

`results/embedded_build.json` records completed build inputs, configurations, patches and artifact hashes. `results/embedded_artifact_audit.json` records read-only checks of the SD partition table, filesystem integrity, boot files, installed module/service/firmware contents and their source hashes. `results/embedded_userspace_test.json` separately records ARM userspace execution under QEMU: all three software reference hashes, required Python imports, anonymous mmap, socket protocol tests and C/Python ioctl layout. QEMU user mode delegates syscalls to the development host; it does not test the ARM kernel, driver, Zybo hardware, DMA or PCAP. Subsequent physical local PS evidence is recorded separately in `results/local-ps-20261115/physical.json`; it does not retroactively change those historical build/audit records.

Buildroot's `build/embedded/rootfs/legal-info` retains package license notices/manifests and source-redistribution information. The downloaded kernel/U-Boot/toolchain archives and local modifications are retained under `build/embedded`. The external toolchain is outside Buildroot's target-package manifest; its README identifies the corresponding [Bootlin source archives](https://toolchains.bootlin.com/downloads/releases/sources/) and [license texts](https://toolchains.bootlin.com/downloads/releases/licenses/), including its glibc/GCC runtime libraries. The exact Buildroot source archive is retained in `build/embedded/downloads/buildroot.tar.xz` even though legal-info does not copy it automatically. Preserve required sources and notices when distributing the resulting image; generated third-party trees do not belong in the project source directory.

An independently selected Linux distribution remains supported. Use its exact kernel build tree and a matching cross compiler, preserve the board PS preset, include equivalent DMA termination-error handling, and merge `software/linux/hash-system.dtsi` into the existing bus. For example:

```bash
KERNEL_BUILD=/path/to/board/kernel/build ./scripts/build_driver.sh \
  ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf-
```

Never perform a full FPGA reload while the Linux driver or DMA is active.

After a successful DFX build, `results/dfx_manifest.json` identifies the compatible images and expected hashes. Copy each image's `source` to `/lib/firmware/<filename>` on the board, preserving the manifest's directory names. Copy the manifest and the `software/` and `benchmarks/` directories as well. The service checks each partial image's SHA256 before loading it. The static image must be the **same build** as `static_sha256` in that manifest. The ABI register is a version check, not proof of the exact loaded static image; the operator must verify this deployment pairing.

On the board, once the matching static design, driver, and firmware are installed:

```bash
python3 software/hash_service.py --manifest dfx_manifest.json --listen 0.0.0.0
```

On the development computer:

```bash
python3 software/hash_client.py BOARD_IP path/to/file --algorithm sha3 --verify
python3 software/hash_client.py BOARD_IP path/to/file --algorithm sha256 --verify
python3 software/hash_client.py BOARD_IP path/to/file --algorithm blake2s --verify
```

This is a development TCP service with no authentication or encryption. Its default bind address is loopback; use an isolated development network or an SSH tunnel when exposing it remotely.

## Protocol

One file per TCP connection, port 9237 by default. The client sends a UTF-8 JSON line:

```json
{"algorithm":"sha3","length":1048576}
```

The server selects the algorithm and starts the file, then replies with a `status: ready` JSON line. The client sends exactly `length` binary bytes. The final `status: ok` JSON line contains a conventional hex digest, core cycle count, byte count, and elapsed receive-plus-DMA-plus-finalization time. Configuration time occurs before `ready` and is not included in that transfer measurement. The ready response also contains `manager_load_ns`, measured in the kernel around explicit firmware retrieval and the FPGA Manager load; the client includes it in its printed result. This duration includes firmware retrieval, PCAP transfer and driver completion, and is zero when the image was already selected. It is not a pure PCAP bus transfer measurement. Requests can select `sha3`, `sha256`, or `blake2s`. All initial modes produce 32 digest bytes. Length is bounded to `2^61-1` bytes for a common SHA-256-compatible API.

The header limit is 4096 bytes. Truncated files, socket timeouts, DMA failures, and engine errors abort the file. The next client starts fresh. The server handles one file at a time, so algorithm switching never interleaves files. A connection ending before its declared length is an error; data beyond the declared length is not part of the file and the connection closes after the result.

Run offline checks with `./scripts/test_software.sh`. They exercise all three reference hashes, empty/boundary/large payloads across thousands of small DMA-sized chunks, malformed headers, short files, recovery, rejected configuration, and C/Python ioctl layout agreement. Run the host kernel API build check with `./scripts/build_driver.sh`. Neither command loads a driver or programs hardware.

For actual board measurements, stop the service so the benchmark can own the device, then run:

```bash
python3 benchmarks/board.py --manifest dfx_manifest.json --bytes 67108864 --repeats 5
```

This command is intentionally rejected on the x86 development machine. On the board it measures DMA-plus-core time without Ethernet, hardware cycle counts, repeated FPGA Manager loads between files, and ARM hashlib performance on the same repeated byte pattern. It verifies every measured hash, keeps memory bounded, and writes actual samples to `board_measurements.json`. Network measurements use `python3 benchmarks/ethernet.py BOARD_IP path/to/file --repeats 5`, which runs all three algorithms, verifies each result, and retains individual samples. The host client reports `client_transfer_and_result_ns` from receipt of ready through receipt/parsing of the digest, and `client_request_ns` from before TCP connection through that result. The latter includes selection/configuration. `--verify` computes the software reference before starting these timers; this prepass can warm the host file cache and is recorded. The server receive/DMA/hash timer remains a separate measurement. The later [physical profiling run](review-guide.md) retains real DMA/API and ARM measurements; its timing scopes remain separate from client/network timing.

## Primary implementation references

- [Linux DMAengine client API](https://docs.kernel.org/driver-api/dmaengine/client.html)
- [Linux FPGA Manager API](https://docs.kernel.org/driver-api/fpga/fpga-mgr.html)
- [AMD Linux 2024.2 Zynq FPGA manager](https://github.com/Xilinx/linux-xlnx/blob/xlnx_rebase_v6.6_LTS_2024.2/drivers/fpga/zynq-fpga.c)
- [AMD Linux 2024.2 AXI DMA driver](https://github.com/Xilinx/linux-xlnx/blob/xlnx_rebase_v6.6_LTS_2024.2/drivers/dma/xilinx/xilinx_dma.c)
