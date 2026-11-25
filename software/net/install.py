#!/usr/bin/env python3
"""Install a verified UART-staged bundle, retaining a complete local rollback.

Run on the board. This never edits profile.env, the kernel, the bootloader or
another profile. A successful installation requires a subsequent reboot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


RUNTIME = Path('/opt/zybo/hash')
PROFILE = Path('/boot/profiles/hash')


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def run(*args):
    subprocess.run(args, check=True)


def copy_atomic(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name+'.gem-new')
    if temp.exists():
        raise RuntimeError('Stale staging file: '+str(temp))
    shutil.copy2(source, temp)
    if sha(temp) != sha(source):
        raise RuntimeError('Copy verification failed: '+str(destination))
    os.replace(temp, destination)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle', type=Path)
    p.add_argument('backup', type=Path)
    p.add_argument('--expected-current-static', required=True)
    args = p.parse_args()
    bundle = args.bundle.resolve()
    backup = args.backup.resolve()
    if os.geteuid() or backup.exists():
        raise RuntimeError('Root and a fresh backup directory are required')
    if Path('/proc/device-tree/model').read_bytes().rstrip(b'\0') != b'Digilent Zybo Z7-20 DFX hash accelerator':
        raise RuntimeError('Boot the current healthy hash profile first')
    if sha(PROFILE/'system.bit') != args.expected_current_static:
        raise RuntimeError('Current boot image differs from the expected recovery image')
    if Path('/run/zybo-hash-net.lock').exists():
        raise RuntimeError('A hardware run is active')
    if not os.path.ismount('/boot'):
        raise RuntimeError('The shared boot partition is not mounted')
    saved_profile = sha('/boot/profile.env')
    inventory = json.loads((bundle/'inventory.json').read_text())
    for name, digest in inventory.items():
        path = bundle/name
        if not path.resolve().is_relative_to(bundle) or sha(path) != digest:
            raise RuntimeError('Bundle inventory mismatch: '+name)
    manifest = json.loads((bundle/'rootfs/opt/zybo/hash/dfx_manifest.json').read_text())
    if sha(bundle/'boot/profiles/hash/system.bit') != manifest['static_sha256']:
        raise RuntimeError('New full bitstream and manifest disagree')
    run('sh', '-c', 'cd "$1" && sha256sum -c SHA256SUMS', 'verify', str(PROFILE))
    backup.mkdir()
    shutil.copytree(PROFILE, backup/'profile')
    shutil.copytree(RUNTIME, backup/'runtime')
    shutil.copy2('/boot/profile.env', backup/'profile.env')
    for path in (Path('/etc/network/interfaces'), Path('/etc/default/zybo-hash')):
        if path.exists():
            shutil.copy2(path, backup/path.name)
    checksums = {str(f.relative_to(backup)): sha(f) for f in sorted(backup.rglob('*')) if f.is_file()}
    for name, digest in checksums.items():
        if name.startswith('profile/') and sha(PROFILE/name.removeprefix('profile/')) != digest:
            raise RuntimeError('Boot backup verification failed: '+name)
        if name.startswith('runtime/') and sha(RUNTIME/name.removeprefix('runtime/')) != digest:
            raise RuntimeError('Runtime backup verification failed: '+name)
    (backup/'inventory.json').write_text(json.dumps(checksums, indent=2)+'\n')
    # Firmware is versioned by both full-image and partial hashes. Never replace
    # an old firmware file; the old manifest remains usable after rollback.
    firmware = bundle/'rootfs/lib/firmware'
    for source in firmware.rglob('*'):
        if source.is_file():
            destination = Path('/lib/firmware')/source.relative_to(firmware)
            if destination.exists():
                if sha(destination) != sha(source):
                    raise RuntimeError('Firmware namespace collision: '+str(destination))
            else:
                copy_atomic(source, destination)
    rollback = backup/'rollback.py'
    rollback.write_text('''#!/usr/bin/env python3
import hashlib,json,os,pathlib,shutil,subprocess
b=pathlib.Path(__file__).resolve().parent
for name,digest in json.loads((b/'inventory.json').read_text()).items():
    assert hashlib.sha256((b/name).read_bytes()).hexdigest()==digest, 'Backup checksum mismatch: '+name
subprocess.run(['/opt/zybo/hash/start.sh','stop'],check=False)
for source,destination in [('runtime','/opt/zybo/hash'),('profile','/boot/profiles/hash')]:
    for f in (b/source).rglob('*'):
        if f.is_file():
            dest=pathlib.Path(destination)/f.relative_to(b/source)
            dest.parent.mkdir(parents=True,exist_ok=True)
            temp=dest.with_name(dest.name+'.rollback-new')
            shutil.copy2(f,temp)
            assert hashlib.sha256(temp.read_bytes()).digest()==hashlib.sha256(f.read_bytes()).digest()
            os.replace(temp,dest)
os.sync()
print('Previous hash boot pair and runtime restored. Reboot to load them.')
''')
    rollback.chmod(0o755)
    os.sync()
    run(str(RUNTIME/'start.sh'), 'stop')
    try:
        for source in (bundle/'rootfs/opt/zybo/hash').rglob('*'):
            if source.is_file():
                copy_atomic(source, RUNTIME/source.relative_to(bundle/'rootfs/opt/zybo/hash'))
        for name in ('system.bit', 'system.dtb', 'SHA256SUMS'):
            copy_atomic(bundle/'boot/profiles/hash'/name, PROFILE/name)
        run('sh', '-c', 'cd "$1" && sha256sum -c SHA256SUMS', 'verify', str(PROFILE))
        for name, digest in inventory.items():
            if name.startswith('rootfs/'):
                if sha(Path('/')/name.removeprefix('rootfs/')) != digest:
                    raise RuntimeError('Installed file mismatch: '+name)
        if sha('/boot/profile.env') != saved_profile:
            raise RuntimeError('Saved profile changed unexpectedly')
        os.sync()
    except BaseException:
        run('python3', str(rollback))
        raise
    print(json.dumps(dict(event='installed', static_sha256=manifest['static_sha256'],
                          profile_env_sha256=saved_profile, backup=str(backup),
                          rollback=str(rollback), reboot_required=True)), flush=True)


if __name__ == '__main__':
    main()
