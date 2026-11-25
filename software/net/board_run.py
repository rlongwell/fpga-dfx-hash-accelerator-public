#!/usr/bin/env python3
"""Exclusive, bounded Ethernet/replay run; restores the normal PS hash service."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

BASE = Path('/opt/zybo/hash')
sys.path.insert(0, str(BASE/'software'))
from hash_service import Hardware, firmware_path, control_lock
from hash_local import LocalHasher


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def reset_hardware(ethernet):
    # Only called after validating the running DT and while holding exclusive ownership.
    run(str(BASE/'net/gem_board'), 'reset-ethernet' if ethernet else 'reset-replay', timeout=5)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['ethernet', 'replay'])
    p.add_argument('--core', choices=['compact', 'oxide', 'sha256', 'blake2s'], default='compact')
    p.add_argument('--length', type=int, required=True)
    p.add_argument('--session', type=lambda v: int(v, 0), required=True)
    p.add_argument('--pattern', type=Path)
    p.add_argument('--peer-mac', help='PC interface MAC, required for Ethernet mode')
    args = p.parse_args()
    if not 0 <= args.length < 1 << 61 or not 0 < args.session < 1 << 32:
        raise ValueError('Length/session outside supported range')
    if args.mode == 'replay' and (not args.pattern or not args.pattern.is_file()):
        raise ValueError('Replay requires a pattern file')
    if args.mode == 'ethernet' and not args.peer_mac:
        p.error('Ethernet mode requires --peer-mac')
    manifest = json.loads((BASE/'dfx_manifest.json').read_text())
    variants = json.loads((BASE/'net/core_variants.json').read_text())
    boot_hash = Path('/proc/device-tree/core-forge,static-sha256').read_bytes().rstrip(b'\0').decode()
    if boot_hash != manifest['static_sha256'] or boot_hash != variants['static_sha256']:
        raise RuntimeError('Running static image and installed partial set do not match')
    if sha('/boot/profiles/hash/system.bit') != boot_hash:
        raise RuntimeError('Boot bitstream checksum mismatch')
    compat = Path('/proc/device-tree/axi/hash-ingress@80000000/compatible').read_bytes()
    if compat != b'core-forge,gem-hash-ingress-1.0\0':
        raise RuntimeError('Direct ingress DT interface is missing')
    image = variants['variants'][args.core]['image'] if args.core in ('compact','oxide') else manifest['images'][args.core]
    if sha(firmware_path(image['filename'])) != image['sha256']:
        raise RuntimeError('Selected partial checksum mismatch')
    ethernet = args.mode == 'ethernet'
    power = Path('/sys/class/net/eth0/device/power/control')
    previous_power = power.read_text().strip()
    local_mac = Path('/sys/class/net/eth0/address').read_text().strip()
    phy = int(Path('/sys/class/net/eth0/phydev').resolve().name.rsplit(':',1)[1],16)
    if ethernet:
        deadline = time.monotonic()+10
        while time.monotonic()<deadline and Path('/sys/class/net/eth0/carrier').read_text().strip() != '1':
            time.sleep(.05)
    if ethernet and (Path('/sys/class/net/eth0/speed').read_text().strip() != '1000' or
                     Path('/sys/class/net/eth0/duplex').read_text().strip() != 'full'):
        raise RuntimeError('This test requires an established 1000/full Ethernet link')
    lock = Path('/run/zybo-hash-net.lock')
    lock.mkdir()  # Atomic exclusivity; do not steal another job's lock.
    stopped = False
    reset_needed = False
    network_down = False
    try:
        (lock/'owner').write_text(str(os.getpid())+'\n')
        run(str(BASE/'start.sh'), 'stop',env={**os.environ,'HASH_NET_OWNER':str(os.getpid())})
        stopped = True
        run('modprobe', 'hash_accel')
        h = Hardware(Path('/dev/hash-accel'), BASE/'dfx_manifest.json')
        try:
            # Force a real switch even though compact and Oxide both report ID 1.
            h.select('sha256' if args.core in ('compact','oxide') else 'sha3')
            intermediate_id = h.info()[1]
            h.manifest = deepcopy(manifest)
            algorithm = 'sha3' if args.core in ('compact','oxide') else args.core
            h.manifest['images'][algorithm] = image
            load_ns = h.select(algorithm)
            if h.info()[1] != image['algorithm_id'] or load_ns <= 0:
                raise RuntimeError('Physical core selection failed')
        finally:
            h.close()
        run('modprobe', '-r', 'hash_accel')
        reset_needed = True
        if ethernet:
            power.write_text('on\n')
            run('ip', 'link', 'set', 'eth0', 'down')
            network_down = True
        print(json.dumps(dict(event='configuration', core=args.core, mode=args.mode,
                              static_sha256=boot_hash, partial_sha256=image['sha256'],
                              helper_sha256=sha(BASE/'net/gem_board'),wrapper_sha256=sha(__file__),
                              partial_load_ns=load_ns, intermediate_algorithm_id=intermediate_id)), flush=True)
        run(str(BASE/'net/gem_board'), args.mode, str(args.length), str(args.session),
            str(args.pattern) if args.pattern else '-', args.peer_mac or '00:00:00:00:00:00',
            local_mac, str(phy), timeout=200)
    finally:
        try:
            if reset_needed:
                reset_hardware(ethernet and network_down)
            if network_down:
                run('ip', 'link', 'set', 'eth0', 'up')
            if ethernet:
                power.write_text(previous_power+'\n')
            if stopped:
                run('modprobe', 'hash_accel')
                h = Hardware(Path('/dev/hash-accel'), BASE/'dfx_manifest.json')
                try:
                    h.select('sha256')
                    h.select('sha3')
                    h.start(0)
                    if h.result()['digest'] != hashlib.sha3_256(b'').hexdigest():
                        raise RuntimeError('Compact-core recovery failed')
                finally:
                    h.close()
                with LocalHasher(manifest=BASE/'dfx_manifest.json') as api:
                    dma_probe = api.hash_bytes(b'PS DMA path recovered', 'sha3', verify=True)
                if dma_probe['dma_transfers'] != 1:
                    raise RuntimeError('Normal PS DMA recovery was not exercised')
                (lock/'owner').unlink()
                lock.rmdir()
                run(str(BASE/'start.sh'), 'start')
                print(json.dumps(dict(event='restored', core='compact', ps_api=True,
                                      dma_probe=dma_probe)),flush=True)
        finally:
            if lock.exists():
                (lock/'owner').unlink(missing_ok=True)
                lock.rmdir()


if __name__ == '__main__':
    def interrupted(*_):
        raise InterruptedError('Board run interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    with control_lock():
        main()
