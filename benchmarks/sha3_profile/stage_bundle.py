#!/usr/bin/env python3
"""Stage the physically accepted variant over a known-good shared payload.

The original accepted manifest/build remains available as the baseline.
This writes staging directories only; it never accesses a disk device.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "results/sha3-performance-20261115"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def stage_original_payload(rootfs, boot):
    """Retain accepted runtime bytes even when host reporting tools have evolved."""
    assembler = ROOT.parent / "zybo-shared-sd/assemble-hash.py"
    spec = importlib.util.spec_from_file_location("shared_hash_assembler", assembler)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    accepted = json.loads((ROOT / "results/embedded_build.json").read_text())
    original = ROOT / "results/dfx_manifest.json"
    assert digest(original) == accepted["inputs_sha256"]["results/dfx_manifest.json"]
    manifest = json.loads(original.read_text())
    release = accepted["kernel_release"]
    module = ROOT / "build/embedded/module/hash_accel.ko"
    assert digest(module) == accepted["inputs_sha256"][str(module.relative_to(ROOT))]
    vermagic = subprocess.check_output(["modinfo", "-F", "vermagic", str(module)], text=True).strip()
    assert vermagic.split()[0] == release
    profile = rootfs / "opt/zybo/hash"
    transfers = [(original, profile / "dfx_manifest.json"),
                 (module, rootfs / "lib/modules" / release / "extra/hash_accel.ko")]
    for name in ["system.bit", "system.dtb"]:
        source = ROOT / "build/embedded/images" / name
        assert digest(source) == accepted["artifacts"][str(source.relative_to(ROOT))]["sha256"]
        transfers.append((source, boot / "profiles/hash" / name))
    for relative, expected in accepted["inputs_sha256"].items():
        parts = Path(relative).parts
        if len(parts) != 2 or parts[0] not in {"software", "benchmarks"} or not relative.endswith(".py"):
            continue
        source = ROOT / relative
        if digest(source) != expected:
            # These host-only report generators are not part of the runtime
            # change. Preserve the accepted copies already installed on the SD.
            assert relative in {"benchmarks/report.py", "benchmarks/engine_results.py"}, relative
            source = ROOT / "build/embedded/rootfs/target/opt/hash-accel" / relative
        assert digest(source) == expected, source
        transfers.append((source, profile / relative))
    helper = ROOT / "software/hash_local.py"
    assert digest(helper) == shared.local_helper_checksum(accepted, manifest)
    transfers.append((helper, profile / "software/hash_local.py"))
    for item in manifest["images"].values():
        source = (ROOT / item["source"]).resolve()
        source.relative_to(ROOT)
        name = Path(item["filename"])
        assert not name.is_absolute() and ".." not in name.parts
        assert digest(source) == item["sha256"]
        transfers.append((source, rootfs / "lib/firmware" / name))
    # Every source is validated before updating either staging tree.
    for source, target in transfers:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    starter = profile / "start.sh"
    starter.write_text(shared.STARTER)
    starter.chmod(0o755)
    hook = profile / "start"
    hook.unlink(missing_ok=True)
    hook.symlink_to("start.sh")
    payload = {"profile": "hash", "kernel_release": release, "module_vermagic": vermagic,
               "runtime": "Python 3.11+; HASH_LISTEN defaults to 127.0.0.1; TCP port 9237",
               "files": [{"tree": "rootfs" if target.is_relative_to(rootfs) else "boot",
                          "path": str(target.relative_to(rootfs if target.is_relative_to(rootfs) else boot)),
                          "sha256": digest(target)} for _, target in transfers]}
    (profile / "payload.json").write_text(json.dumps(payload, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rootfs", type=Path)
    parser.add_argument("boot", type=Path)
    args = parser.parse_args()
    rootfs, boot = args.rootfs.resolve(), args.boot.resolve()
    assert rootfs != Path("/") and boot != Path("/") and rootfs != boot
    manifest_path = EVIDENCE / "promoted_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    variant = Path(manifest["initial_full_bit"]).parent.name
    assert variant in {"fast", "compact"}
    implementation = json.loads((EVIDENCE / variant / "implementation.json").read_text())
    physical_path = EVIDENCE / "promoted-local-physical.json"
    physical = json.loads(physical_path.read_text())
    assert physical["passed"] and physical["kind"] == "physical-zybo-ps-dma"
    assert physical["files_sha256"]["/boot/profiles/hash/system.bit"] == manifest["static_sha256"]
    assert physical["files_sha256"]["/opt/zybo/hash/dfx_manifest.json"] == digest(manifest_path)
    assert physical["kernel_release"] == "6.6.40-dfx-hash"
    for line in (EVIDENCE / variant / "sources.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert digest(Path(name)) == expected, name
    for algorithm in ["sha3", "sha256", "blake2s"]:
        report = (EVIDENCE / variant / f"pr_verify_{algorithm}.rpt").read_text()
        assert "are compatible" in report and "ERROR:" not in report
    full = (ROOT / manifest["initial_full_bit"]).resolve()
    full.relative_to(ROOT)
    assert digest(full) == manifest["static_sha256"] == implementation["full_bit"]["sha256"]
    image = manifest["images"]["sha3"]
    partial = (ROOT / image["source"]).resolve()
    partial.relative_to(ROOT)
    assert digest(partial) == image["sha256"] == implementation["partial"]["sha256"]
    relative = Path(image["filename"])
    assert not relative.is_absolute() and ".." not in relative.parts
    stage_original_payload(rootfs, boot)
    profile = rootfs / "opt/zybo/hash"
    target = rootfs / "lib/firmware" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(partial, target)
    shutil.copy2(full, boot / "profiles/hash/system.bit")
    shutil.copy2(manifest_path, profile / "dfx_manifest.json")
    checksums = boot / "profiles/hash/SHA256SUMS"
    checksums.write_text("".join(digest(boot / "profiles/hash" / name) + "  " + name + "\n"
                                for name in ["system.bit", "system.dtb"]))
    payload_path = profile / "payload.json"
    payload = json.loads(payload_path.read_text())
    payload["files"].append({"tree": "rootfs", "path": str(target.relative_to(rootfs))})
    for item in payload["files"]:
        item["sha256"] = digest((rootfs if item["tree"] == "rootfs" else boot) / item["path"])
    payload.update(static_sha256=manifest["static_sha256"], hardware_tested=True,
                   variant="sha3-" + variant, physical_validation={"scope": "PS local API, DMA, DFX, all three hashes after boot",
                   "path": str(physical_path.relative_to(ROOT)), "sha256": digest(physical_path)})
    payload_path.write_text(json.dumps(payload, indent=2) + "\n")
    print("Validated SHA3 bundle:", variant, rootfs, boot)


if __name__ == "__main__":
    main()
