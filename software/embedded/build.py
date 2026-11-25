#!/usr/bin/env python3
"""Optional local ARM/SD build, independent of repository-management tools.

All downloads, cross compilers and generated artifacts remain under build/embedded.
This script never installs host packages, writes an SD device, or programs a board.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BUILD = ROOT / "build/embedded"
PINS = json.loads((HERE / "sources.json").read_text())
LINUX = BUILD / "sources" / PINS["linux"]["directory"]
UBOOT = BUILD / "sources" / PINS["uboot"]["directory"]
BR = BUILD / "sources" / PINS["buildroot"]["directory"]
TC = BUILD / "tools" / PINS["toolchain"]["directory"]
CROSS = str(TC / "bin/arm-linux-")
JOBS = os.environ.get("EMBEDDED_JOBS", "2")
KERNEL = BUILD / "kernel"
UOUT = BUILD / "uboot"
RFS = BUILD / "rootfs"


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run(command, log, cwd=ROOT):
    print(f"{log}: {' '.join(map(str, command))}", flush=True)
    with (BUILD / "logs" / f"{log}.log").open("a") as output:
        subprocess.run(list(map(str, command)), cwd=cwd, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


def bootstrap():
    for directory in ("downloads", "sources", "tools", "logs", "hardware", "images"):
        (BUILD / directory).mkdir(parents=True, exist_ok=True)
    for name, item in PINS.items():
        archive = BUILD / "downloads" / item["archive"]
        if not archive.exists():
            temporary = archive.with_suffix(archive.suffix + ".partial")
            urllib.request.urlretrieve(item["url"], temporary)
            temporary.replace(archive)
        if digest(archive) != item["sha256"]:
            raise RuntimeError(f"Download checksum mismatch: {archive}")
        parent = BUILD / ("tools" if name == "toolchain" else "sources")
        if not (parent / item["directory"]).exists():
            run(["tar", "-xf", archive, "-C", parent], "extract")
            if name == "toolchain":
                run([TC / "relocate-sdk.sh"], "toolchain-relocation")
    dma = LINUX / "drivers/dma/xilinx/xilinx_dma.c"
    if "Keep descriptors owned until hardware reset" not in dma.read_text():
        run(["patch", "-p1", "--forward", "-i", HERE / "xilinx-dma-terminate-error.patch"],
            "kernel-patch", cwd=LINUX)


def kmake(*arguments, log="kernel-build"):
    run(["make", "-C", LINUX, f"O={KERNEL}", "ARCH=arm", f"CROSS_COMPILE={CROSS}",
         *arguments], log)


def kernel():
    kmake("xilinx_zynq_defconfig", log="kernel-config")
    run([LINUX / "scripts/config", "--file", KERNEL / ".config",
         "--enable", "XILINX_DMA", "--enable", "FPGA", "--enable", "FPGA_MGR_ZYNQ_FPGA",
         "--enable", "REALTEK_PHY", "--enable", "DEVTMPFS_MOUNT", "--enable", "EXT4_FS",
         "--enable", "FAT_FS", "--enable", "VFAT_FS", "--disable", "MODULE_FORCE_UNLOAD",
         "--disable", "DEBUG_INFO", "--disable", "DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT",
         "--set-str", "LOCALVERSION", "-dfx-hash", "--disable", "LOCALVERSION_AUTO"], "kernel-config")
    kmake("olddefconfig", log="kernel-config")
    kmake(f"-j{JOBS}", "zImage", "modules", "dtbs")
    module()
    device_tree()


def module():
    output = BUILD / "module"
    output.mkdir(exist_ok=True)
    for name in ("hash_accel.c", "hash_accel.h", "Makefile"):
        shutil.copy2(ROOT / "software/linux" / name, output / name)
    kmake(f"M={output}", "modules", log="arm-module")
    run([CROSS + "readelf", "-h", output / "hash_accel.ko"], "arm-module")


def device_tree():
    preprocessed = BUILD / "hardware/zybo-hash.dts"
    command = [CROSS + "gcc", "-E", "-P", "-x", "assembler-with-cpp", "-nostdinc",
               "-undef", "-D__DTS__", "-I", LINUX / "arch/arm/boot/dts/xilinx",
               "-I", LINUX / "include", "-I", ROOT / "software/linux",
               HERE / "zybo-hash.dts", "-o", preprocessed]
    run(command, "device-tree")
    run([KERNEL / "scripts/dtc/dtc", "-I", "dts", "-O", "dtb", "-o",
         BUILD / "images/system.dtb", preprocessed], "device-tree")


def uboot():
    xsa = ROOT / "build/vivado/system/system.xsa"
    xsa_hash = digest(xsa)
    stamp = BUILD / "hardware/uboot_inputs.json"
    stamp.unlink(missing_ok=True)
    with zipfile.ZipFile(xsa) as archive:
        for name in ("ps7_init_gpl.c", "ps7_init_gpl.h"):
            (BUILD / "hardware" / name).write_bytes(archive.read(name))
    base = ["make", "-C", UBOOT, f"O={UOUT}", f"CROSS_COMPILE={CROSS}"]
    run([*base, "xilinx_zynq_virt_defconfig"], "uboot-config")
    run([UBOOT / "scripts/config", "--file", UOUT / ".config",
         "--set-str", "DEFAULT_DEVICE_TREE", "zynq-zybo-z7",
         "--set-str", "OF_LIST", "zynq-zybo-z7",
         "--set-str", "XILINX_PS_INIT_FILE", BUILD / "hardware/ps7_init_gpl.c",
         "--enable", "OF_SEPARATE", "--disable", "OF_BOARD",
         "--disable", "ENV_IS_IN_FAT", "--disable", "ENV_IS_IN_NAND",
         "--disable", "ENV_IS_IN_SPI_FLASH", "--enable", "ENV_IS_NOWHERE",
         "--disable", "TOOLS_MKEFICAPSULE"], "uboot-config")
    run([*base, "olddefconfig"], "uboot-config")
    run([*base, f"-j{JOBS}"], "uboot-build")
    if digest(xsa) != xsa_hash:
        raise RuntimeError("XSA changed during U-Boot build")
    stamp.write_text(json.dumps({"xsa_sha256": xsa_hash,
                                "ps_init_sha256": {name: digest(BUILD / "hardware" / name)
                                                   for name in ("ps7_init_gpl.c", "ps7_init_gpl.h")},
                                "uboot_sha256": {name: digest(UOUT / name)
                                                 for name in ("spl/boot.bin", "u-boot.img")}}, indent=2)+"\n")


def rootfs():
    config = (HERE / "buildroot.defconfig").read_text().replace("@TOOLCHAIN@", str(TC))
    config = config.replace("@OVERLAY@", str(BUILD / "overlay"))
    (BUILD / "overlay").mkdir(exist_ok=True)
    (BUILD / "buildroot.defconfig").write_text(config)
    run(["make", "-C", BR, f"O={RFS}", f"BR2_DEFCONFIG={BUILD / 'buildroot.defconfig'}",
         "defconfig"], "rootfs-config")
    run(["make", "-C", BR, f"O={RFS}"], "rootfs-build")


def package():
    images = BUILD / "images"
    accepted = ROOT / "results/embedded_build.json"
    accepted.unlink(missing_ok=True)
    (images / "sdcard.img").unlink(missing_ok=True)
    (images / "boot.vfat").unlink(missing_ok=True)
    stamp = json.loads((BUILD / "hardware/uboot_inputs.json").read_text())
    if digest(ROOT / "build/vivado/system/system.xsa") != stamp["xsa_sha256"]:
        raise RuntimeError("XSA changed since U-Boot was built; rebuild the uboot stage")
    for name, expected in stamp["ps_init_sha256"].items():
        if digest(BUILD / "hardware" / name) != expected:
            raise RuntimeError("PS initialization changed since U-Boot build")
    for name, expected in stamp["uboot_sha256"].items():
        if digest(UOUT / name) != expected:
            raise RuntimeError("U-Boot artifact changed since its accepted build")
    manifest_path = Path(os.environ.get("HASH_MANIFEST", ROOT / "results/dfx_manifest.json")).resolve()
    manifest_path.relative_to(ROOT)
    manifest = json.loads(manifest_path.read_text())
    if set(manifest["images"]) != {"sha3", "sha256", "blake2s"}:
        raise RuntimeError("A completed three-algorithm DFX set is required")
    # A timing-closed replacement RM can retain the locked static system and
    # matching PS initialization. Its accepted manifest selects the boot image.
    full = (ROOT / manifest.get("initial_full_bit", "build/vivado/dfx/sha3/full.bit")).resolve()
    full.relative_to(ROOT)
    if digest(full) != manifest["static_sha256"]:
        raise RuntimeError("Initial full bitstream does not match DFX manifest")
    module()
    device_tree()
    overlay = BUILD / "overlay"
    opt = overlay / "opt/hash-accel"
    opt.mkdir(parents=True, exist_ok=True)
    for directory in ("software", "benchmarks"):
        destination = opt / directory
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(ROOT / directory, destination,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "embedded", "linux", "tests"))
    shutil.copy2(manifest_path, opt / "dfx_manifest.json")
    for image in manifest["images"].values():
        source = ROOT / image["source"]
        if digest(source) != image["sha256"]:
            raise RuntimeError(f"PCAP checksum mismatch: {source}")
        destination = overlay / "lib/firmware" / image["filename"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    kmake(f"INSTALL_MOD_PATH={overlay}", "DEPMOD=true", "modules_install", log="modules-install")
    release = (KERNEL / "include/config/kernel.release").read_text().strip()
    modules = overlay / "lib/modules" / release
    (modules / "extra").mkdir(exist_ok=True)
    shutil.copy2(BUILD / "module/hash_accel.ko", modules / "extra/hash_accel.ko")
    for name in ("build", "source"):
        (modules / name).unlink(missing_ok=True)
    run(["depmod", "-b", overlay, release], "modules-install")
    rootfs()
    for source, name in [(KERNEL / "arch/arm/boot/zImage", "zImage"),
                         (UOUT / "spl/boot.bin", "BOOT.BIN"),
                         (UOUT / "u-boot.img", "u-boot.img"), (full, "system.bit"),
                         (RFS / "images/rootfs.ext4", "rootfs.ext4")]:
        shutil.copy2(source, images / name)
    run([UOUT / "tools/dumpimage", "-T", "zynqimage", "-l", images / "BOOT.BIN"], "boot-inspection")
    run([UOUT / "tools/dumpimage", "-l", images / "u-boot.img"], "boot-inspection")
    run([UOUT / "tools/mkimage", "-A", "arm", "-T", "script", "-C", "none",
         "-n", "Zybo DFX hash boot", "-d", HERE / "boot.cmd", images / "boot.scr"], "boot-script")
    temporary = BUILD / "genimage-tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    empty_root = BUILD / "genimage-root"
    empty_root.mkdir(exist_ok=True)
    host_path = f"{RFS / 'host/bin'}:{RFS / 'host/sbin'}:{os.environ['PATH']}"
    run(["env", f"PATH={host_path}", RFS / "host/bin/genimage", "--rootpath", empty_root, "--tmppath", temporary,
         "--inputpath", images, "--outputpath", images, "--config", HERE / "genimage.cfg"], "sd-image")
    run(["make", "-C", BR, f"O={RFS}", "legal-info"], "licenses")
    inputs = [ROOT / "build/vivado/system/system.xsa", manifest_path,
              KERNEL / ".config", UOUT / ".config", RFS / ".config",
              ROOT / "build.sh", ROOT / "scripts/build_embedded.sh"]
    inputs += [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    inputs += list((ROOT / "software/linux").glob("*"))
    inputs += list((ROOT / "software").glob("*.py"))
    inputs += list((ROOT / "benchmarks").glob("*.py"))
    inputs += [LINUX / "drivers/dma/xilinx/xilinx_dma.c", BUILD / "hardware/ps7_init_gpl.c",
               BUILD / "hardware/ps7_init_gpl.h", BUILD / "hardware/uboot_inputs.json",
               BUILD / "module/hash_accel.ko"]
    report = {"built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "hardware_tested": False, "kernel_release": release, "sources": PINS,
              "scope": "Cross-built kernel/module/device tree, U-Boot SPL and SD image; not boot-tested",
              "validation": {"cross_compiled": True, "board_boot_tested": False,
                             "userspace_qemu_record": "results/embedded_userspace_test.json"},
              "inputs_sha256": {str(p.relative_to(ROOT)): digest(p) for p in inputs if p.is_file()},
              "artifacts": {str(p.relative_to(ROOT)): {"bytes": p.stat().st_size, "sha256": digest(p)}
                            for p in images.iterdir() if p.is_file()}}
    temporary_report = accepted.with_suffix(".json.tmp")
    temporary_report.write_text(json.dumps(report, indent=2) + "\n")
    temporary_report.replace(accepted)
    print(images / "sdcard.img")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("bootstrap", "kernel", "module", "device-tree", "uboot",
                                          "rootfs", "package", "all"), default="all", nargs="?")
    args = parser.parse_args()
    bootstrap()
    if args.stage == "all":
        kernel(); uboot(); rootfs(); package()
    elif args.stage != "bootstrap":
        {"kernel": kernel, "module": module, "device-tree": device_tree,
         "uboot": uboot, "rootfs": rootfs, "package": package}[args.stage]()


if __name__ == "__main__":
    main()
