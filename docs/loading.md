# Loading and first board acceptance

This guide brings up the base three-engine design on a Zybo Z7-20. Start with a complete, verified DFX build and its matching ARM image. For an already configured Hash Lab board, use the [live tutorial](../tutorial.md#run-the-sample-on-a-zybo). The dashboard checks the extended shell and its installed software. The [build guide](build.md#fpga-implementation) identifies both configurations.

## Initial full configuration

Use the initial SHA3 full image listed by `results/dfx_manifest.json`, normally `build/vivado/dfx/sha3/full.bit`. Its SHA256 must match `static_sha256` in the manifest. All three partial images must come from that same manifest.

The optional deployment bundle is generated with:

```bash
./build.sh embedded all
python3 software/embedded/smoke.py
```

Its `build/embedded/images/sdcard.img` has a 64 MiB FAT boot partition and a 256 MiB ext4 root partition. `BOOT.BIN` contains U-Boot SPL with the GPL PS initialization exported from the matching XSA; SPL initializes DDR/MIO/FCLK and loads `u-boot.img`. U-Boot's `boot.scr` loads the initial `system.bit`, then `system.dtb` and `zImage`, and starts Linux with the second SD partition as its root. The full configuration occurs before the accelerator driver probes. A failed file load or FPGA configuration does not proceed to Linux.

The root filesystem contains the ARM-built `hash_accel.ko`, the firmware manifest and partial images, Python 3.11, and `/opt/hash-accel/{software,benchmarks}`. Neither driver loading nor the network service is started automatically. The image is a development system with a serial root login and an empty password; no SSH or Telnet service is enabled. The board acceptance sequence below checks boot, DDR and driver operation on a newly built image.

To boot the base image on your board:

1. Check `results/embedded_build.json` against the generated image. Write `sdcard.img` to the intended removable SD card with your usual disk-image writer; this replaces that card's contents. The build scripts never write a block device.
2. With board power off, install the card and select the **SD** position on JP5. Connect the USB-JTAG/UART port and open its serial interface at **115200 baud, 8 data bits, no parity, one stop bit**, then power on. These settings follow the [Digilent Zybo Z7 manual](https://digilent.com/reference/_media/reference/programmable-logic/zybo-z7/zybo-z7_rm.pdf).
3. Observe SPL, U-Boot and Linux messages. Log in as `root` on the serial console. Ethernet uses DHCP by default; inspect `ip addr show eth0` for the address.
4. Load the module and start the service explicitly:

```sh
uname -r                       # expected: 6.6.40-dfx-hash
modprobe hash_accel
ls -l /dev/hash-accel
cd /opt/hash-accel
python3 software/hash_service.py --manifest dfx_manifest.json --listen 0.0.0.0
```

Run the host client against the displayed IP address and perform the acceptance sequence below. Stop the service before running `benchmarks/board.py`, which requires exclusive device ownership.

For a separately chosen Linux/PetaLinux platform, a matching FSBL/bootloader flow remains an alternative: initialize PS from the same XSA, configure the initial full bitstream before driver probing, and boot the matching ARM kernel/device tree/module. Preserve the DMA failure-propagation patch or equivalent behavior. A `.bit` file alone does not initialize the ARM software stack or supply a bootable Linux image.

For JTAG PL bring-up, Vivado Hardware Manager can program the full bitstream once the target is connected. The following Tcl is an explicit, manual programming sequence; it was not executed here:

```tcl
open_hw_manager
connect_hw_server
open_hw_target
set devices [get_hw_devices -filter {PART =~ "xc7z020*"}]
if {[llength $devices] != 1} { error "Expected exactly one xc7z020 target" }
set dev [lindex $devices 0]
current_hw_device $dev
set_property PROGRAM.FILE /absolute/path/to/build/vivado/dfx/sha3/full.bit $dev
program_hw_devices $dev
```

Initialize the PS with the corresponding FSBL/platform before register or DMA tests. Hardware Manager programming is a full PL configuration and must not be used as the run-time algorithm-switch operation while the service is active.

## Runtime images and service

Install the ARM-built driver, the manifest, the Python service, and each manifest-selected `.bit.bin` under its content-specific `/lib/firmware/<filename>` path. The service requests partial PCAP loads through the driver; it does not reprogram the entire device. See [software deployment](software.md) for kernel requirements and client commands. Keep the static peripheral nodes in the base device tree throughout all switches.

## Board acceptance sequence

1. Boot the matching static design and Linux stack. Verify Ethernet connectivity and the ABI/algorithm ID through the driver; check the kernel log for DDR, DMA and FPGA-manager errors.
2. Hash empty, one-byte, block-boundary and multi-megabyte files with `--verify` for the initial SHA3 image.
3. Switch to SHA-256, then BLAKE2s, then SHA3 using the service. Verify every returned digest and monitor a separate Ethernet connection during each actual PCAP load.
4. Hash a file larger than DDR while monitoring resident memory and DMA errors. Confirm all DMA chunks contribute to one final digest.
5. Interrupt a file transfer, verify abort/recovery, then test an intentionally missing firmware filename through a local driver test. A failed load must leave isolation asserted until a successful recovery.
6. Measure cycles, DDR/DMA rate, complete Ethernet transfer rate, actual PCAP load time, and ARM software hashes separately. Record temperature, clocks, kernel/BSP versions, buffer size, file size and repetitions. Do not fill these measurements from simulation estimates.

Only after these checks pass should the corresponding rows in `results/status.md` be marked hardware tested.
