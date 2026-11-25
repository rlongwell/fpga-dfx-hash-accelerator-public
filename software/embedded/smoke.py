#!/usr/bin/env python3
"""Execute the cross-built ARM Python and ioctl-layout check with QEMU user mode.

This exercises userspace instructions and host-kernel sockets/mmap, not the ARM
kernel, driver, DMA, Ethernet hardware or PCAP.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/embedded"
TARGET = BUILD / "rootfs/target"
QEMU = BUILD / "tools/qemu/usr/bin/qemu-arm-static"
QEMU_SOURCE = {
    "url": "https://security.ubuntu.com/ubuntu/pool/universe/q/qemu/qemu-user-static_8.2.2+ds-0ubuntu1.18_amd64.deb",
    "version": "1:8.2.2+ds-0ubuntu1.18",
    "sha256": "5bb397f66063efa349f6fd5cb3b68cd96f29edd0994e4ba5115cf0859a716bf0",
}


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    package = BUILD / "downloads/qemu-user-static.deb"
    if not package.exists():
        urllib.request.urlretrieve(QEMU_SOURCE["url"], package)
    if digest(package) != QEMU_SOURCE["sha256"]:
        raise RuntimeError("QEMU package checksum mismatch")
    if not QEMU.exists():
        subprocess.run(["dpkg-deb", "-x", package, BUILD / "tools/qemu"], check=True)
    source = BUILD / "uapi_arm.c"
    source.write_text('''#include <stdio.h>
#include "hash_accel.h"
int main(void) {
printf("%zu %zu %zu %lu %lu %lu %lu %lu %lu\\n",
sizeof(struct hash_info), sizeof(struct hash_result), sizeof(struct hash_switch),
(unsigned long)HASH_INFO, (unsigned long)HASH_START, (unsigned long)HASH_TRANSFER,
(unsigned long)HASH_RESULT, (unsigned long)HASH_SWITCH, (unsigned long)HASH_ABORT);
}
''')
    pins = json.loads((ROOT / "software/embedded/sources.json").read_text())
    compiler = BUILD / "tools" / pins["toolchain"]["directory"] / "bin/arm-linux-gcc"
    executable = BUILD / "uapi_arm"
    subprocess.run([compiler, "-Wall", "-Werror", "-I", ROOT / "software/linux",
                    source, "-o", executable], check=True)
    output = subprocess.check_output([QEMU, "-cpu", "cortex-a9", "-L", TARGET, executable], text=True)
    import sys
    sys.path.insert(0, str(ROOT / "software"))
    from hash_service import INFO, START, TRANSFER, RESULT, SWITCH, ABORT
    expected = [16, 48, 144, INFO, START, TRANSFER, RESULT, SWITCH, ABORT]
    if list(map(int, output.split())) != expected:
        raise RuntimeError("ARM C/Python ioctl layouts disagree")
    code = r'''
import fcntl, hashlib, json, mmap, platform, socket, ssl, struct, sys, unittest
assert sys.version_info >= (3, 11)
with mmap.mmap(-1, 4096) as buffer:
    buffer[:3] = b"abc"
    assert bytes(buffer[:3]) == b"abc"
assert hashlib.sha3_256(b"abc").hexdigest() == "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532"
assert hashlib.sha256(b"abc").hexdigest() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
assert hashlib.blake2s(b"abc").hexdigest() == "508c5e8c327c14e2e1a72ba34eeb452f37458b209ed63a294d999b4c86675982"
from tests.test_service import ProtocolTests
names = ["test_files_split_across_many_dma_buffers", "test_short_file_aborts_and_next_request_can_run",
         "test_invalid_requests", "test_configuration_failure_prevents_ready"]
result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(ProtocolTests(name) for name in names))
assert result.wasSuccessful()
print(json.dumps({"python": platform.python_version(), "machine": platform.machine(),
                  "openssl": ssl.OPENSSL_VERSION, "protocol_test_groups": len(names),
                  "hashes": ["sha3_256", "sha256", "blake2s"],
                  "imports": ["fcntl", "mmap", "socket", "ssl", "struct"],
                  "ioctl_execution": False, "hardware_tested": False}))
'''
    environment = dict(os.environ, PYTHONHOME=str(TARGET / "usr"),
                       PYTHONPATH=str(ROOT / "software"))
    started = time.time()
    completed = subprocess.run([QEMU, "-cpu", "cortex-a9", "-L", TARGET, TARGET / "usr/bin/python3", "-c", code],
                               env=environment, text=True, capture_output=True, check=True)
    (BUILD / "logs/qemu-userspace.log").write_text(completed.stdout + completed.stderr)
    result = json.loads(completed.stdout.splitlines()[-1])
    result.update(scope="ARM userspace under QEMU; host Linux syscalls, no emulated Zybo hardware",
                  qemu=QEMU_SOURCE, emulated_cpu="cortex-a9", uapi_values=expected, elapsed_seconds=time.time()-started,
                  source_sha256={str(path.relative_to(ROOT)): digest(path) for path in
                                 (Path(__file__), ROOT / "software/hash_service.py",
                                  ROOT / "software/tests/test_service.py", ROOT / "software/linux/hash_accel.h")},
                  binary_sha256={str(path.relative_to(ROOT)): digest(path)
                                 for path in (QEMU, executable, TARGET / "usr/bin/python3")})
    (ROOT / "results/embedded_userspace_test.json").write_text(json.dumps(result, indent=2)+"\n")
    print(completed.stdout)


if __name__ == "__main__":
    main()
