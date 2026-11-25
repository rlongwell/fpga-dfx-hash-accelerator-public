# Reproducing the offline work

The source tree is independent of Core Forge. Generated Vivado projects and checkpoints live under `build/`; deleting that directory discards only generated artifacts and locally downloaded tools. Build/test scripts locate the project from their own path, not the caller's working directory.

## Tools

- Vivado **2024.2**, device support for `xc7z020clg400-1`, and the installed Digilent Zybo Z7-20 board definition `digilentinc.com:zybo-z7-20:part0:1.2`.
- Bash, Python 3.11 or newer, C/C++ compiler, Make, ripgrep, curl, dpkg-deb, and sha256sum on x86-64 Linux.
- Verilator 5.020 was used for portable SystemVerilog tests.
- NVC 1.23.1 for unchanged VHDL-2019 baseline simulation. `scripts/setup_nvc.sh` downloads the pinned official Ubuntu 24.04 package, verifies its SHA256, and unpacks it under `build/tools`; it does not install system packages. Other distributions can supply a compatible NVC with equivalent VHDL-2019 support by adapting that tool path.
- The optional host driver build needs the running Linux kernel headers. An ARM deployment module needs the exact board kernel build tree and its cross compiler.

Vivado defaults to `/opt/amd/xilinx/Vivado/2024.2/bin/vivado`. Set `VIVADO` to a different executable path if necessary. The scripts and comparison results require the 2024.2 version. The installed tools provide the DFX capabilities for this device; no separate DFX license was needed in the measured build.

## Ubuntu 24.04 simulation setup

The full offline suite does not require Vivado or a board. Install these host packages before the first run:

```bash
sudo apt-get update
sudo apt-get install -y build-essential verilator ripgrep curl python3 \
  libllvm18 libdw1t64 libffi8 libreadline8t64 libtcl8.6 libzstd1 binutils
./test.sh
```

The listed libraries are runtime dependencies of the pinned NVC Ubuntu package. Python uses the standard library only. First-run NVC setup requires network access; later runs reuse `build/tools/`. The [CI workflow](../.github/workflows/verify.yml) uses the same platform and test command.

## Verification

```bash
./test.sh
```

This runs the unchanged reference, the minimal digest-storage variant, the static shell, all seven engine variants, five integrated shell/engine models, the elastic comparison adapter, software protocol tests, and the retained-evidence audit. It writes a source-hashed successful run record to `results/verification.json`, with individual logs under `build/verification`. Any failure stops the command. Tests use independent Python hashlib vectors; synthesizable RTL never calls Python hashing.

Useful individual checks:

```bash
./scripts/test_baseline.sh
./scripts/test_static.sh
./scripts/test_engines.sh sha3
./scripts/test_integration.sh sha256
./scripts/test_software.sh
```

## FPGA implementation

The commands below build the base three-engine DMA system. The installed Hash Lab dashboard checks a specific extended shell and software manifest. To study or reproduce that setup, use the [GEM and replay build](gem-direct.md#rebuild-and-reproduce) and check the [limits of rebuilding a recorded image](review-guide.md#build-and-deployment-limits).

```bash
./build.sh baseline
./build.sh digest-variant
./build.sh engines
./build.sh system
```

The baseline and engine comparisons are standalone out-of-context implementations, with their own reported timing boundary. The system command generates and validates the PS7/DMA block design, synthesizes vendor IP and the static shell, synthesizes each RM separately, routes the first configuration, locks/reuses static routing, routes the remaining RMs, checks DRC/timing/static compatibility, and writes full/partial images. See [DFX flow details](dfx.md) for exact outputs and floorplan constraints. Actual full-system timing is authoritative for the board build.

To resume a completed earlier stage without rebuilding the block design:

```bash
./build.sh system ip
./build.sh system synth
./build.sh system dfx
```

Do not run two copies of the same build stage in the same directory. Regenerating the block design or DFX output intentionally replaces its generated directory. Keep source and partial images from one build together; inspect the source/artifact hash manifest before deployment.

The hardware handoff is `build/vivado/system/system.xsa`. Successful DFX programming images live under `build/vivado/dfx`. These offline build and test commands do not open Hardware Manager, connect to a board, program PCAP, or modify an attached board. The explicitly invoked board service and board benchmark perform runtime PCAP loading on the target.

## Software and benchmarks

```bash
./build.sh driver
./build.sh embedded          # Optional pinned ARM/Linux boot and root filesystem
python3 benchmarks/x86_hashes.py
```

The default driver build is a local kernel API check. The optional `embedded` command downloads pinned public sources and a local ARM cross compiler, builds the matching kernel/module/device tree, U-Boot SPL and Python root filesystem, then packages the accepted DFX artifacts into an SD image under `build/embedded/images`. It does not write a physical SD card. It is a standalone deployment option and does not change the Vivado project-management workflow. `./build.sh embedded --help` lists individual stages; `EMBEDDED_JOBS` controls build parallelism and `EMBEDDED_PYTHON` selects a host Python 3.11+ interpreter. [Software deployment](software.md) describes the exact target build and service/client commands. The x86 benchmark hashes in-memory buffers, excludes file/network I/O, and records runtime/CPU/load and per-run timings. Run it without competing workloads for a cleaner software comparison.

`benchmarks/board.py` provides the corresponding real-board DMA/core, FPGA Manager, and ARM software measurements. It requires the configured Zybo and refuses to run on this x86 host.

`python3 benchmarks/ethernet.py BOARD_IP FILE --repeats 5 --output ethernet_measurements.json`
records client-observed transfer-through-digest and complete request times for all three algorithms. Its local reference hashes are outside the timed intervals; file reads during transmission are included. Reference prepasses and repeated reads can warm the filesystem cache. A localhost reference-backend test checks this harness, but is not an Ethernet/PL performance measurement.

Standalone core-rate predictions remain separate from the [physical DMA/API, ARM and reconfiguration measurements](review-guide.md). The [later Ethernet study](../results/ethernet-20261116/README.md) has its own input and timing interval. The dated compact incremental flow requires the original accepted checkpoint set; see [reproduction limits](review-guide.md#build-and-deployment-limits).
