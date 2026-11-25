# Vivado system and DFX build

The hardware target is `xc7z020clg400-1` on the Zybo Z7-20, using Vivado 2024.2. The design has one reconfigurable cell, `system_top/u_hash`. SHA3-256, SHA-256, and BLAKE2s-256 each supply a separate `hash_rm` netlist with identical ports. The algorithm is selected by loading its partial image; it is not selected by a data-path multiplexer.

The completed 100 MHz build has positive routed setup/hold timing for all three configurations, passes both `pr_verify -full_check` comparisons, and includes full/partial bitstreams plus Bootgen PCAP binaries. See the [implementation results](../results/dfx_summary.md), [runtime manifest](../results/dfx_manifest.json), and compact reports under `results/dfx/`. These reports document routing and image compatibility. The [later board acceptance](../results/demo-20261115/README.md) records physical hashing and engine switches.

## Build commands

Run from the project directory:

```bash
./scripts/build_system.sh bd     # Recreate and validate the PS/DMA block design
./scripts/build_system.sh ip     # Synthesize vendor IP out of context
./scripts/build_system.sh synth  # Synthesize static logic with a black-box u_hash
./scripts/build_system.sh dfx    # Build, route, verify, then emit all three configurations
# Or repeat all stages:
./scripts/build_system.sh all
```

`SYSTEM_PYTHON` and `DFX_PYTHON` may select Python 3.11+ interpreters for their respective build stages; their default is `/usr/bin/python3` and they run in isolated mode because Vivado prepends an older bundled Python to `PATH` and sets `PYTHONHOME`. `VIVADO` may specify the executable path. The default is `/opt/amd/xilinx/Vivado/2024.2/bin/vivado`. `DFX_RMS=sha3` selects a single configuration for an early implementation-only check. Subset builds emit no programming images or runtime manifest; they do not establish interchangeability between algorithms. The default DFX build requires all three source sets. After an interrupted run or alternate-RM timing fix, `DFX_RESUME=1 ./scripts/build_system.sh dfx` can preserve the initial routed configuration and locked static checkpoint. It checks unchanged static checkpoint, pblock, initial-RM source hashes, and static RTL freshness; changed alternate RMs are resynthesized. Unchanged alternates may also reuse their routed checkpoints when those are newer than the matching RM synthesis and locked static checkpoint. Every reused checkpoint has its route, timing, and DRC reports regenerated; every alternate passes `pr_verify -full_check` before any programming image is published. Changed or incomplete alternates are reimplemented. Complete source membership and hashes are compared; changed checkpoints are invalidated before the new source snapshot is published atomically. This is checkpoint-based recovery of the documented 7-series DFX flow, without incremental compilation. All generated files, projects, logs, reports, and programming images are under `build/`. Rebuilding `bd` replaces its generated project; rebuilding `dfx` replaces its generated outputs so a failed build cannot leave an old bitstream presented as current.

The static synthesis checkpoint is `build/vivado/system/static_synth.dcp`. `static_inputs.json` / `static_inputs.sha256` bind it to the shell/top RTL, system Tcl, generated BD, and board preset. New synthesis runs capture inputs before execution and reject changes before publishing that manifest. Every DFX run verifies both inputs and checkpoint hash, including ordinary non-resume builds. The initial development checkpoint was adopted after an explicit stable-HDL/session audit; its manifest records that capture mode rather than claiming a pre-build snapshot. A later host-Python invocation fix in `system.tcl` is recorded as an explicit orchestration-only amendment: the original manifest/source, exact diff, original adoption hashes, and unchanged checkpoint/HDL/BD identities are preserved under `build/vivado/system/provenance/` and in the compact evidence archive. That amendment does not claim resynthesis. `build/vivado/system/system.xsa` is the exported hardware handoff for an embedded platform; it does not contain a bitstream or a bootable board image. The non-project DFX flow:

1. Synthesizes each RM out of context using the same 100 MHz target.
2. Opens the static synthesis checkpoint, sets `HD.RECONFIGURABLE` on `u_hash`, applies the pblock, and links the first RM with strict port matching.
3. Optimizes, places, and routes the first complete configuration.
4. Removes the first RM, locks static placement and routing, and writes `static_locked.dcp`.
5. Links and implements every remaining RM against that same locked static checkpoint.
6. Requires complete routing, routed setup/hold timing, clock coverage, pulse-width checks, and no Error/Critical Warning DRC violations. A failing first routed timing result is preserved before one post-route `phys_opt_design -directive AggressiveExplore` attempt. Its checkpoint and timing report are preserved, and routing is repeated only if the optimized design has incomplete routing; all acceptance checks still apply. DRC command completion alone is insufficient: the script checks violation objects.
7. Runs `pr_verify -full_check` between the initial routed configuration and each alternate. Only after those checks pass does it generate programming images.

Outputs under `build/vivado/dfx/<algorithm>/` include `rm_synth.dcp`, `routed.dcp`, utilization/timing/DRC reports, `full.bit`, `full_pblock_hash_partial.bit`, and `full_pblock_hash_partial.bit.bin`. The `.bit.bin` file is a Bootgen-converted, 32-bit byte-swapped PCAP binary, not a renamed `.bit` file. The build checks its alignment and sync word. `sources.sha256`, `artifacts.sha256`, and `build_info.txt` identify the exact inputs and outputs. When validation tooling was updated after a job launched, its exact loaded Tcl versions were retained under `loaded_tcl/` and checked against the originally captured hashes. Compact synthesis/routing/timing/DRC reports, `pr_verify` reports, exact loaded-script provenance, and source/artifact identities are also retained under `results/dfx/`, with a relative-path `evidence.sha256` file for source-only sharing. Large checkpoints and programming images remain under `build/`. The runtime manifest requires exactly all three PCAP images and is emitted to `build/vivado/dfx/manifest.json` and `results/dfx_manifest.json`, with algorithm IDs, PCAP image hashes, and firmware names grouped by the initial full-image hash. Each filename also includes its own partial-image hash (`<algorithm>-<hash12>.bin`) so a changed alternate RM cannot reuse a cached firmware name. No files are installed in this workstation's `/lib/firmware`. Preserve a complete compatible artifact set; never combine partial images from different static builds. The hardware exposes an ABI version, not a unique static-build digest; the operator must ensure the running full image matches the manifest. File hashing alone cannot identify the image currently loaded on the board.

## PS/DMA static design

`system_bd.tcl` applies installed board preset `digilentinc.com:zybo-z7-20:part0:1.2`. DDR/FIXED_IO are the only external top-level ports. Ethernet is PS Ethernet0 on MIO16–27; MDIO is MIO52–53. The preset configures 1 GiB of 32-bit DDR, SD0 on MIO40–45 with card detect MIO47, and UART1 on MIO48–49.

The shell and every RM run on PS FCLK0 at 100 MHz. `proc_sys_reset` synchronizes the PS fabric reset. GP0 reaches the DMA and shell registers through an AXI interconnect. The MM2S-only AXI DMA reads DDR through HP0, has a 64-bit stream, data realignment enabled, simple mode, 32-bit addresses, and a 26-bit transfer-length field. A second interconnect converts the memory path to the PS HP0 interface. The software-visible digest remains in static registers, so no S2MM channel is needed.

| Endpoint | Address / interrupt |
| --- | --- |
| DMA registers | `0x40400000`, 64 KiB assigned aperture |
| Hash shell registers | `0x43C00000`, 4 KiB aperture |
| DMA DDR reads | `0x00000000` through `0x3FFFFFFF`; software must allocate valid DDR buffers |
| DMA MM2S interrupt | PS fabric interrupt input bit 0 |
| Shell interrupt | PS fabric interrupt input bit 1 |

The generated address map is `build/vivado/system/address_map.txt`. Use the eventual BSP/device tree for GIC interrupt numbers and DMA mappings.

The official Digilent DDR preset contains negative DQS-to-clock delay values (-0.050, -0.044, -0.035, -0.100 ns). Vivado reports four `PSU-1` through `PSU-4` critical warnings while generating PS7 for those values. They are preserved because replacing board timing with invented nonnegative values would change the hardware configuration. These preset-generation warnings do not waive implementation DRC or timing checks. The later [ARM-to-FPGA validation](../results/local-ps-20261115/physical.json) exercised the DDR/DMA path on the board.

## Reconfigurable pblock

`constraints/dfx.xdc` uses explicit resource ranges in the upper two right-hand clock regions:

```text
SLICE_X50Y50:SLICE_X113Y149
RAMB18_X3Y20:RAMB18_X5Y59
RAMB36_X3Y10:RAMB36_X5Y29
DSP48_X3Y20:DSP48_X4Y59
```

The nominal ranges cover 6,400 slices (25,600 LUT positions), 60 RAMB36 positions, and 80 DSP48 positions; Vivado derives the legal implementation geometry through snapping. `SNAPPING_MODE=ON`, `RESET_AFTER_RECONFIG=true`, routing containment, and placement exclusion apply. The ranges have been checked against the installed device and HDPR floorplan DRC. Final resource fit and timing are established by each algorithm's implementation reports, not by the nominal region capacity. Bare `CLOCKREGION` ranges did not produce valid 7-series snapping geometry in the isolated probe; explicit ranges avoid that problem.

## Loading through PCAP

The original implementation evidence above is offline. Subsequent [physical acceptance](review-guide.md) verifies DDR/DMA hashing, boot, and partial reconfiguration, with measured FPGA Manager durations. The [later Ethernet study](../results/ethernet-20261116/README.md) records external-link measurements. The build command itself never opens hardware manager or programs a device.

Before a partial load, software must stop new work, finish or abort the current message, quiesce/reset the DMA, assert shell isolation, and check the isolation status. Keep the partition reset asserted while writing the compatible partial image. On success, release isolation, allow the shell's reset-release delay, and verify algorithm ID/readiness. On failure, remain isolated. Do not pulse global PL reset or perform a full-configuration sequence during a partial load; those operations would interrupt static logic.

For bare-metal software, AMD's `devcfg` driver provides `XDcfg_Transfer(..., XDCFG_NON_SECURE_PCAP_WRITE)`. The partial path selects PCAP/PR mode, avoids global reset and PS–PL level-shifter changes, and waits for both DMA completion and `D_P_DONE`. Production code also needs bounded waits, error-bit handling, 8-byte source alignment, lengths in 32-bit words, and appropriate cache flushing. The installed reference example is `/opt/amd/xilinx/Vivado/2024.2/data/embeddedsw/XilinxProcessorIPLib/drivers/devcfg_v3_8/examples/xdevcfg_polled_example.c`.

For Linux, use a kernel-supported FPGA manager/region workflow with the partial-reconfiguration flag and proper driver ownership. The AMD 2024.2 Zynq driver handles this flag and skips global resets for partial loads. Its input is a byte-swapped `.bin`; the configuration DMA requires 8-byte-aligned starting addresses and lengths divisible by four. An old 2019 wiki page says partial loading is unsupported; that statement does not describe the inspected 2024.2 driver. Do not transplant ZynqMP-specific loader commands to this Zynq-7000 system without checking the actual kernel interface.

The optional `./build.sh embedded [stage]` flow uses a pinned Bootlin ARM GNU/Linux toolchain under `build/embedded/tools/`, with archive identities in `software/embedded/sources.json`. It builds the board-side Linux deployment components separately from Vivado. See [software](software.md) and [loading](loading.md) for exact build stages, artifacts, verification evidence, and board-loading steps. Cross-compilation does not establish DDR, Ethernet, PCAP, or accelerator operation on the physical board.

## Evidence and primary sources

An isolated `/tmp` probe on the actual installed part successfully created two distinct RMs, routed a common static design, produced full and partial `.bit` images, and passed `pr_verify -full_check`. This establishes tool capability, not verification of the hash accelerator. The project build reports provide the accelerator's own evidence.

- [AMD DFX licensing, UG909 2024.2](https://docs.amd.com/r/2024.2-English/ug909-vivado-partial-reconfiguration/Dynamic-Function-eXchange-Licensing): no separate DFX license code is needed from Vivado 2019.1 onward.
- [AMD non-project implementation flow, UG909 2024.2](https://docs.amd.com/r/2024.2-English/ug909-vivado-partial-reconfiguration/Implementation)
- [AMD configuration verification and bitstream generation, UG947 2024.2](https://docs.amd.com/r/2024.2-English/ug947-vivado-partial-reconfiguration-tutorial/Step-9-Generating-Bitstreams)
- [AMD 7-series pblock snapping](https://docs.amd.com/r/2024.2-English/ug909-vivado-partial-reconfiguration/Automatic-Adjustments-for-Reconfigurable-Partition-Pblocks)
- [Digilent board preset](https://github.com/Digilent/vivado-boards/blob/master/new/board_files/zybo-z7-20/A.0/preset.xml): the installed copy matched SHA256 `f1da413772d4be2d6c2a703ceb54502304840e11fe8fd8c2b02dc450c86335e6`.
- [AMD Zynq PCAP example](https://github.com/Xilinx/embeddedsw/blob/master/XilinxProcessorIPLib/drivers/devcfg/examples/xdevcfg_polled_example.c)
- [AMD 2024.2 Zynq FPGA manager driver](https://github.com/Xilinx/linux-xlnx/blob/xlnx_rebase_v6.6_LTS_2024.2/drivers/fpga/zynq-fpga.c)
