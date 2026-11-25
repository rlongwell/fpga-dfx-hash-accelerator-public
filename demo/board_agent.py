#!/usr/bin/env python3
"""Temporary UART-launched bridge to the installed, hardware-only local API.

Installed FPGA files, boot settings and user files stay intact. Payloads live in /tmp.
Comparison mode reconfigures verified partials and restores the installed compact core.
The service is paused for exclusive local DMA access and restarted afterward.
"""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import signal

BASE = Path('/opt/zybo/hash')
MAX_FILE = 16 * 1024 * 1024
sys.path.insert(0, str(BASE / 'software'))


def emit(event, **values):
    print('@ZYBO_DEMO ' + json.dumps(dict(event=event, **values), separators=(',', ':')), flush=True)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def probe():
    model = Path('/proc/device-tree/model').read_bytes().rstrip(b'\0').decode()
    if model != 'Digilent Zybo Z7-20 DFX hash accelerator':
        raise RuntimeError('Boot the hash profile before using this demo.')
    manifest = json.loads((BASE / 'dfx_manifest.json').read_text())
    pid = int(Path('/run/zybo-hash.pid').read_text())
    args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    if str(BASE / 'software/hash_service.py').encode() not in args:
        raise RuntimeError('The installed hardware service is not running.')
    if sha('/boot/profiles/hash/system.bit') != manifest['static_sha256']:
        raise RuntimeError('Boot image does not match the installed manifest.')
    return dict(model=model, kernel=os.uname().release, service_pid=pid,
                profile='hash', static_sha256=manifest['static_sha256'],
                manifest_sha256=sha(BASE / 'dfx_manifest.json'),
                service_sha256=sha(BASE / 'software/hash_service.py'),
                client_sha256=sha(BASE / 'software/hash_client.py'),
                local_api_sha256=sha(BASE / 'software/hash_local.py'),
                profile_env_sha256=sha('/boot/profile.env'),
                dtb_sha256=sha('/boot/profiles/hash/system.dtb'),
                profile_status=subprocess.check_output(['zybo-profile.sh', 'status'], text=True).strip(),
                fpga_manager=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
                transport=os.environ.get('ZYBO_DEMO_TRANSPORT', 'usb-uart'),
                baud=115200 if os.environ.get('ZYBO_DEMO_TRANSPORT', 'usb-uart') == 'usb-uart' else None)


def run(path, algorithms):
    from hash_service import control_lock
    with control_lock():
        _run(path, algorithms)


def _run(path, algorithms):
    from hash_local import LocalHasher
    starter = str(BASE / 'start.sh')
    try:
        subprocess.run([starter, 'stop'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['modprobe', 'hash_accel'], check=True)
        with LocalHasher(manifest=BASE / 'dfx_manifest.json') as hardware:
            try:
                for algorithm in algorithms:
                    emit('hashing', algorithm=algorithm)
                    result = hardware.hash_file(path, algorithm=algorithm, verify=False)
                    emit('result', result=result)
            finally:
                # Restore the demo's documented compact SHA3 idle configuration.
                emit('restoring', algorithm='sha3')
                result = hardware.hash_bytes(b'', algorithm='sha3', verify=True)
                emit('restored', result=result)
    finally:
        subprocess.run([starter, 'start'], check=True, stdout=subprocess.DEVNULL)
    emit('board', board=probe())


def run_comparison(path, config_path):
    from hash_service import control_lock
    with control_lock():
        _run_comparison(path, config_path)


def _run_comparison(path, config_path):
    """Force each SHA3 image through another algorithm; IDs alone are shared."""
    from hash_local import LocalHasher
    from hash_service import firmware_path
    base = json.loads((BASE / 'dfx_manifest.json').read_text())
    config = json.loads(config_path.read_text())
    for key in ('abi', 'part', 'static_sha256'):
        if config[key] != base[key]:
            raise ValueError('Comparison manifest does not match the running static image')
    if config['repeats'] != 7 or config['warmup'] != 1 or set(config['variants']) != {'oxide', 'compact'}:
        raise ValueError('Unexpected comparison plan')
    if config['variants']['compact']['image'] != base['images']['sha3']:
        raise ValueError('Comparison compact image differs from the installed default')
    for variant in config['variants'].values():
        image = variant['image']
        if image['algorithm_id'] != 1 or sha(firmware_path(image['filename'])) != image['sha256']:
            raise ValueError('Comparison partial image identity mismatch')
    if not path.stat().st_size:
        raise ValueError('The pinned Quartz core cannot encode an empty input')
    starter = str(BASE / 'start.sh')
    safe_to_restart = True
    try:
        subprocess.run([starter, 'stop'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['modprobe', 'hash_accel'], check=True)
        with LocalHasher(manifest=BASE / 'dfx_manifest.json') as hardware:
            try:
                for core in ('oxide', 'compact'):
                    safe_to_restart = False
                    variant = config['variants'][core]
                    hw = hardware._hardware
                    emit('loading', algorithm='sha3', core=core, core_label=variant['label'])
                    hw.manifest = deepcopy(base)
                    hw.select('sha256')
                    if hw.info()[1] != 2:
                        raise RuntimeError('Intermediate SHA-256 configuration was not observed')
                    hw.manifest['images']['sha3'] = variant['image']
                    load_ns = hw.select('sha3')
                    if not load_ns or hw.info()[1] != 1:
                        raise RuntimeError('Expected a fresh SHA3 partial load')
                    emit('hashing', algorithm='sha3', core=core, core_label=variant['label'])
                    warmup = hardware.hash_file(path, algorithm='sha3', verify=False)
                    samples = [hardware.hash_file(path, algorithm='sha3', verify=False) for _ in range(7)]
                    if any(s['digest'] != warmup['digest'] for s in samples):
                        raise RuntimeError('Repeated physical digests disagree')
                    result = dict(sorted(samples, key=lambda s:s['local_hash_ns'])[3],
                                  core=core, core_label=variant['label'], image=variant['image'],
                                  intermediate_algorithm_id=2, manager_load_ns=load_ns,
                                  repeats=7, warmup=warmup, samples=samples,
                                  minimum_hash_ns=min(s['local_hash_ns'] for s in samples),
                                  maximum_hash_ns=max(s['local_hash_ns'] for s in samples))
                    emit('result', result=result)
            finally:
                emit('restoring', algorithm='sha3')
                hardware._hardware.manifest = deepcopy(base)
                hardware._hardware.select('sha256')
                load_ns = hardware._hardware.select('sha3')
                result = hardware.hash_bytes(b'', algorithm='sha3', verify=True)
                result['manager_load_ns'] = load_ns
                emit('restored', result=result)
                safe_to_restart = True
    finally:
        if safe_to_restart:
            subprocess.run([starter, 'start'], check=True, stdout=subprocess.DEVNULL)
        else:
            raise RuntimeError('Compact restoration failed; hash service remains stopped for recovery')
    emit('board', board=probe())


def prepare_payload(path, compressed, expected_size, expected_sha256):
    """Decode a bounded RAM payload and verify the exact original bytes."""
    if type(expected_size) is not int or not 0 <= expected_size <= MAX_FILE:
        raise ValueError('Invalid decoded payload length')
    target = path.with_suffix('.decoded') if compressed else path
    if compressed:
        created = False
        try:
            with target.open('xb') as dst:
                created = True
                with gzip.open(path, 'rb') as src:
                    count = 0
                    while block := src.read(min(65536, expected_size - count + 1)):
                        count += len(block)
                        if count > expected_size:
                            raise ValueError('Decoded payload exceeds its declared length')
                        dst.write(block)
        except BaseException:
            if created:
                target.unlink(missing_ok=True)
            raise
    if target.stat().st_size != expected_size or sha(target) != expected_sha256:
        if compressed:
            target.unlink(missing_ok=True)
        raise ValueError('Decoded payload checksum or length mismatch')
    emit('payload_verified', size=expected_size, sha256=expected_sha256, compressed=compressed)
    return target


def main():
    def interrupted(*_):
        raise InterruptedError('Demo interrupted; restoring the hash service.')
    signal.signal(signal.SIGHUP, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--file', type=Path)
    parser.add_argument('--algorithms', nargs='+', choices=['sha3', 'sha256', 'blake2s'])
    parser.add_argument('--compare', type=Path)
    parser.add_argument('--compressed', action='store_true')
    parser.add_argument('--expected-size', type=int)
    parser.add_argument('--input-sha256')
    args = parser.parse_args()
    decoded = None
    try:
        emit('board', board=probe())
        if not args.probe:
            if not args.file or not args.algorithms:
                raise ValueError('A payload and algorithms are required.')
            if args.file.parent != Path('/tmp') or not args.file.name.startswith('zybo-demo-'):
                raise ValueError('Payload must be a demo-owned temporary file.')
            if not args.file.is_file() or args.file.is_symlink() or args.file.stat().st_size > MAX_FILE:
                raise ValueError('Invalid or oversized demo payload.')
            decoded = prepare_payload(args.file, args.compressed, args.expected_size, args.input_sha256)
            if args.compare:
                if args.compare.parent != Path('/tmp') or not args.compare.name.startswith('zybo-demo-'):
                    raise ValueError('Comparison config must be a demo-owned temporary file')
                run_comparison(decoded, args.compare)
            else:
                run(decoded, args.algorithms)
        emit('done')
    except Exception as error:
        emit('error', message=str(error))
        return 1
    finally:
        if decoded and decoded != args.file:
            decoded.unlink(missing_ok=True)
        if args.file and args.file.parent == Path('/tmp') and args.file.name.startswith('zybo-demo-'):
            args.file.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
