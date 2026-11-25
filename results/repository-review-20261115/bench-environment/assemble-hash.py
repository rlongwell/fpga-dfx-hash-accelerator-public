#!/usr/bin/env python3
"""Copy the accepted hash profile into writable rootfs and boot staging trees.

Usage: assemble-hash.py ROOTFS_STAGE BOOT_STAGE
Uses the existing 6.6.40-dfx-hash kernel/module; never writes a disk image or SD.
Run depmod for the staged rootfs after all profile modules have been installed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


REPO = Path(__file__).resolve().parent.parent / "fpga-dfx-hash-accelerator"

STARTER = r'''#!/bin/sh
# Foreground controls for the background hash service. Boot selects its DT/PL.
# LAN opt-in: HASH_LISTEN=0.0.0.0 /opt/zybo/hash/start start
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
base=/opt/zybo/hash
service=$base/software/hash_service.py
pidfile=/run/zybo-hash.pid
logfile=/var/log/zybo-hash.log
lock=/run/zybo-hash.lock
mkdir -p /run /var/log
if ! mkdir "$lock" 2>/dev/null; then
    echo 'Another hash service operation is in progress.' >&2
    exit 1
fi
trap 'rmdir "$lock"' 0
trap 'exit 1' 1 2 15

running() {
    [ -s "$pidfile" ] || return 1
    read -r pid < "$pidfile"
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    kill -0 "$pid" 2>/dev/null || return 1
    [ -r "/proc/$pid/cmdline" ] || return 1
    tr '\000' '\n' < "/proc/$pid/cmdline" | grep -Fxq "$service"
}

start_service() {
    model=$(tr -d '\000' < /proc/device-tree/model)
    if [ "$model" != 'Digilent Zybo Z7-20 DFX hash accelerator' ]; then
        echo "Hash profile is not selected by this boot: $model" >&2
        return 1
    fi
    if running; then
        echo "Hash service is already running (PID $pid)."
        return 0
    fi
    rm -f "$pidfile"
    modprobe hash_accel
    if [ ! -c /dev/hash-accel ]; then
        echo 'The matching hash driver did not create /dev/hash-accel.' >&2
        return 1
    fi
    /usr/bin/python3 "$service" --manifest "$base/dfx_manifest.json" \
        --listen "${HASH_LISTEN:-127.0.0.1}" >> "$logfile" 2>&1 < /dev/null &
    echo "$!" > "$pidfile"
    sleep 1
    if running; then
        echo "Hash service started (PID $pid); log: $logfile"
    else
        rm -f "$pidfile"
        echo "Hash service failed to start; see $logfile" >&2
        return 1
    fi
}

stop_service() {
    if running; then
        kill -TERM "$pid"
        waited=0
        while running && [ "$waited" -lt 10 ]; do
            sleep 1
            waited=$((waited + 1))
        done
        if running; then
            echo "Hash service did not stop (PID $pid); driver remains loaded." >&2
            return 1
        fi
    fi
    rm -f "$pidfile"
    if [ -d /sys/module/hash_accel ]; then
        modprobe -r hash_accel
    fi
}

case "${1:-start}" in
    start) start_service ;;
    stop) stop_service ;;
    restart) stop_service; start_service ;;
    status) if running; then echo "Hash service running (PID $pid)"; else echo 'Hash service stopped'; exit 1; fi ;;
    *) echo "Usage: $0 [start|stop|restart|status]" >&2; exit 2 ;;
esac
'''


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(path: Path, expected: str) -> None:
    if not path.is_file() or digest(path) != expected:
        raise RuntimeError(f"Missing or changed accepted hash artifact: {path}")


def copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def local_helper_checksum(accepted: dict, manifest: dict) -> str:
    """Accept the separately board-tested helper without rewriting build history."""
    receipt = json.loads((REPO / "results/local_ps_validation.json").read_text())
    if (receipt.get("schema") != 1 or receipt.get("passed") is not True
            or receipt.get("kernel_release") != accepted["kernel_release"]
            or receipt.get("static_sha256") != manifest["static_sha256"]):
        raise RuntimeError("Local PS helper validation does not match this hash profile")
    evidence_path = (REPO / receipt["physical_report"]["path"]).resolve()
    evidence_path.relative_to(REPO)
    verify(evidence_path, receipt["physical_report"]["sha256"])
    evidence = json.loads(evidence_path.read_text())
    if (evidence.get("passed") is not True or evidence.get("kind") != "physical-zybo-ps-dma"
            or evidence.get("kernel_release") != accepted["kernel_release"]
            or evidence["files_sha256"]["/boot/profiles/hash/system.bit"] != manifest["static_sha256"]):
        raise RuntimeError("Missing matching physical local PS evidence")
    for name in ("software/hash_local.py", "software/hash_service.py", "software/tests/board_local.py"):
        verify(REPO / name, receipt["inputs_sha256"][name])
    checksum = receipt["inputs_sha256"]["software/hash_local.py"]
    if evidence["files_sha256"]["/opt/zybo/hash/software/hash_local.py"] != checksum:
        raise RuntimeError("Local helper differs from the physically tested source")
    return checksum


def assemble(rootfs: Path, boot: Path) -> None:
    rootfs, boot = rootfs.resolve(), boot.resolve()
    if rootfs == Path("/") or boot == Path("/") or rootfs == boot:
        raise ValueError("Use separate rootfs and boot staging directories, not the host root")
    accepted = json.loads((REPO / "results/embedded_build.json").read_text())
    manifest_path = REPO / "results/dfx_manifest.json"
    verify(manifest_path, accepted["inputs_sha256"][str(manifest_path.relative_to(REPO))])
    manifest = json.loads(manifest_path.read_text())
    if manifest["part"] != "xc7z020clg400-1" or manifest["abi"] != 65536:
        raise RuntimeError("Unsupported hash FPGA part or hardware ABI")
    if set(manifest["images"]) != {"sha3", "sha256", "blake2s"}:
        raise RuntimeError("All three matching hash partial images are required")
    release = (REPO / "build/embedded/kernel/include/config/kernel.release").read_text().strip()
    if release != accepted["kernel_release"]:
        raise RuntimeError("Hash kernel release differs from accepted build")
    module = REPO / "build/embedded/module/hash_accel.ko"
    verify(module, accepted["inputs_sha256"][str(module.relative_to(REPO))])
    vermagic = subprocess.check_output(["modinfo", "-F", "vermagic", str(module)], text=True).strip()
    if vermagic.split()[0] != release:
        raise RuntimeError("Hash module does not match the shared hash kernel")

    transfers: list[tuple[Path, Path]] = []
    for name in ("system.bit", "system.dtb"):
        source = REPO / "build/embedded/images" / name
        verify(source, accepted["artifacts"][str(source.relative_to(REPO))]["sha256"])
        transfers.append((source, boot / "profiles/hash" / name))
    verify(REPO / "build/embedded/images/system.bit", manifest["static_sha256"])
    profile = rootfs / "opt/zybo/hash"
    transfers.extend([(manifest_path, profile / "dfx_manifest.json"),
                      (module, rootfs / "lib/modules" / release / "extra/hash_accel.ko")])
    for source in sorted((REPO / "software").glob("*.py")) + sorted((REPO / "benchmarks").glob("*.py")):
        relative = source.relative_to(REPO)
        expected = accepted["inputs_sha256"].get(str(relative))
        if expected is None and str(relative) == "software/hash_local.py":
            expected = local_helper_checksum(accepted, manifest)
        if expected is None:
            raise RuntimeError(f"No accepted build/validation record for {relative}")
        verify(source, expected)
        transfers.append((source, profile / relative))
    for image in manifest["images"].values():
        source = (REPO / image["source"]).resolve()
        source.relative_to(REPO)
        name = Path(image["filename"])
        if name.is_absolute() or ".." in name.parts:
            raise RuntimeError("Invalid hash firmware destination")
        verify(source, image["sha256"])
        with source.open("rb") as stream:
            prefix = stream.read(128)
        if source.stat().st_size % 4 or b"\x66\x55\x99\xaa" not in prefix:
            raise RuntimeError(f"Invalid PCAP byte order/alignment: {source}")
        transfers.append((source, rootfs / "lib/firmware" / name))

    # Validate every source before updating either destination tree.
    for source, target in transfers:
        copy(source, target)
    starter = profile / "start.sh"
    starter.write_text(STARTER)
    starter.chmod(0o755)
    hook = profile / "start"
    hook.unlink(missing_ok=True)
    hook.symlink_to("start.sh")
    info = {"profile": "hash", "kernel_release": release, "module_vermagic": vermagic,
            "static_sha256": manifest["static_sha256"],
            "hardware_tested": False,
            "runtime": "Python 3.11+; HASH_LISTEN defaults to 127.0.0.1; TCP port 9237",
            "files": [{"tree": "rootfs" if target.is_relative_to(rootfs) else "boot",
                       "path": str(target.relative_to(rootfs if target.is_relative_to(rootfs) else boot)),
                       "sha256": digest(target)} for _, target in transfers]}
    (profile / "payload.json").write_text(json.dumps(info, indent=2) + "\n")
    print(f"Hash profile staged: {profile}")
    print(f"Boot payload: {boot / 'profiles/hash'}")
    print(f"Run depmod -b ROOTFS_STAGE {release} after assembling all profiles.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rootfs_stage", type=Path)
    parser.add_argument("boot_stage", type=Path)
    args = parser.parse_args()
    assemble(args.rootfs_stage, args.boot_stage)
