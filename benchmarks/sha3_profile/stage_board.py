#!/usr/bin/env python3
"""Verify and publish a new SHA3 partial from a checksum-verified UART gzip."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("compressed", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    assert manifest["abi"] == 65536 and manifest["part"] == "xc7z020clg400-1"
    assert digest(Path("/boot/profiles/hash/system.bit")) == manifest["static_sha256"]
    item = manifest["images"]["sha3"]
    name = Path(item["filename"])
    assert not name.is_absolute() and ".." not in name.parts
    target = Path("/lib/firmware") / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".staged-", delete=False) as out:
        temporary = Path(out.name)
        try:
            with gzip.open(args.compressed, "rb") as source:
                shutil.copyfileobj(source, out, 65536)
            out.flush()
            os.fsync(out.fileno())
            assert digest(temporary) == item["sha256"], "decompressed checksum mismatch"
            with temporary.open("rb") as source:
                assert b"\x66\x55\x99\xaa" in source.read(128)
            assert temporary.stat().st_size % 4 == 0
            if target.exists():
                assert digest(target) == item["sha256"], "existing destination differs"
            else:
                os.link(temporary, target)  # Publish without replacing any existing file.
        finally:
            temporary.unlink(missing_ok=True)
    os.sync()
    print("STAGED", target, "SHA256", digest(target))


if __name__ == "__main__":
    main()
