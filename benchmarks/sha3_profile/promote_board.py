#!/usr/bin/env python3
"""Promote a measured, compatible SHA3 build while retaining boot rollback files.

Requires successful physical current/oxide/fast reports and a faster 16 MiB
fast result. Upload inputs through the checksum-verifying UART helper first.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("full_gzip", type=Path)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--oxide", type=Path, required=True)
    parser.add_argument("--fast", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    reports = {name: json.loads(getattr(args, name).read_text()) for name in ["current", "oxide", "fast"]}
    for name, report in reports.items():
        assert report["passed"] and report["kind"] == "physical-zybo-performance", name
    assert manifest["images"] == reports["fast"]["manifest"]["images"]
    def rates(report):
        return next(row["summary"] for row in report["algorithms"]["sha3"] if row["bytes"] == 16777216)
    for name in ["current", "oxide"]:
        for method in ["dma", "local_api"]:
            assert rates(reports["fast"])[method]["MB_s"] > rates(reports[name])[method]["MB_s"]
    boot = Path("/boot/profiles/hash")
    installed_manifest = Path("/opt/zybo/hash/dfx_manifest.json")
    assert digest(boot / "system.bit") == reports["current"]["manifest"]["static_sha256"]
    assert digest(installed_manifest) == reports["current"]["manifest_sha256"]
    assert manifest["abi"] == 65536 and manifest["part"] == "xc7z020clg400-1"
    for item in manifest["images"].values():
        name = Path(item["filename"])
        assert not name.is_absolute() and ".." not in name.parts
        assert digest(Path("/lib/firmware") / name) == item["sha256"]
    # Backups are persistent and never replaced on a retry.
    backup = boot / "before-sha3-fast-20261115"
    backup.mkdir(exist_ok=False)
    for name in ["system.bit", "system.dtb", "SHA256SUMS"]:
        shutil.copy2(boot / name, backup / name)
    shutil.copy2(installed_manifest, backup / "dfx_manifest.json")
    original = {name: digest(backup / name) for name in ["system.bit", "system.dtb", "SHA256SUMS", "dfx_manifest.json"]}
    (backup / "backup.json").write_text(json.dumps(original, indent=2) + "\n")
    pending = boot / "system.bit.sha3-fast-pending"
    with gzip.open(args.full_gzip, "rb") as source, pending.open("xb") as target:
        shutil.copyfileobj(source, target, 65536)
        target.flush()
        os.fsync(target.fileno())
    assert digest(pending) == manifest["static_sha256"]
    new_manifest = installed_manifest.with_name("dfx_manifest.sha3-fast-pending.json")
    with new_manifest.open("x") as target:
        target.write(args.manifest.read_text())
        target.flush()
        os.fsync(target.fileno())
    checksums = boot / "SHA256SUMS.sha3-fast-pending"
    checksums.write_text(manifest["static_sha256"] + "  system.bit\n" + digest(boot / "system.dtb") + "  system.dtb\n")
    os.sync()
    pending.replace(boot / "system.bit")
    new_manifest.replace(installed_manifest)
    checksums.replace(boot / "SHA256SUMS")
    os.sync()
    print("PROMOTED full bitstream", digest(boot / "system.bit"))
    print("PROMOTED manifest", digest(installed_manifest))
    print("ROLLBACK", backup)
    print("Reboot the hash profile, then run all three algorithm acceptance tests.")


if __name__ == "__main__":
    main()
