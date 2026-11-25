#!/usr/bin/env python3
"""Bind a static checkpoint to the inputs validated for its synthesis run."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inputs(root: Path, out: Path) -> list[Path]:
    vivado = Path(os.environ.get('XILINX_VIVADO', '/opt/amd/xilinx/Vivado/2024.2'))
    return [root / 'rtl/static/hash_shell.sv', root / 'rtl/static/system_top.sv',
            root / 'scripts/vivado/system_bd.tcl', root / 'scripts/vivado/system.tcl',
            root / 'scripts/vivado/system_threads.tcl', root / 'scripts/vivado/system_manifest.py',
            vivado / 'data/boards/board_files/zybo-z7-20/A.0/preset.xml',
            out / 'project/system.srcs/sources_1/bd/ps_dma/ps_dma.bd']


def snapshot(root: Path, out: Path) -> dict[str, str]:
    paths = inputs(root, out)
    bd = paths[-1]
    if (root / 'scripts/vivado/system_bd.tcl').stat().st_mtime_ns > bd.stat().st_mtime_ns:
        raise ValueError('Block-design source is newer than generated BD; run build_system.sh bd, ip, synth')
    return {str(path.resolve()): digest(path) for path in paths}


def check_files(record: dict) -> None:
    for name, expected in record['inputs'].items():
        path = Path(name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f'Static input changed or missing: {path}; rebuild the static system')


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ('begin', 'finish', 'verify', 'adopt-audited'):
        raise SystemExit('Usage: system_manifest.py begin|finish|verify|adopt-audited ROOT')
    action, root_arg = sys.argv[1:]
    root = Path(root_arg).resolve()
    out = root / 'build/vivado/system'
    pending = out / 'static_inputs.pending.json'
    manifest = out / 'static_inputs.json'
    checkpoint = out / 'static_synth.dcp'
    if action == 'begin':
        manifest.unlink(missing_ok=True)
        (out / 'static_inputs.sha256').unlink(missing_ok=True)
        pending.write_text(json.dumps({'capture_mode': 'before_synthesis', 'inputs': snapshot(root, out)}, indent=2) + '\n')
        print('Captured static inputs before synthesis')
        return
    if action == 'adopt-audited':
        # One-time migration for the existing build audited during development.
        # Normal build scripts always use begin/finish and never call this mode.
        for path in (root / 'rtl/static').glob('*.sv'):
            if path.stat().st_mtime_ns > checkpoint.stat().st_mtime_ns:
                raise ValueError(f'Cannot adopt checkpoint older than RTL: {path}')
        record = {'capture_mode': 'after_build_hdl_timestamps_and_session_history_audited',
                  'inputs': snapshot(root, out)}
    elif action == 'finish':
        record = json.loads(pending.read_text())
        check_files(record)
    else:
        record = json.loads(manifest.read_text())
        check_files(record)
        if digest(checkpoint) != record['checkpoint_sha256']:
            raise ValueError('Static checkpoint no longer matches its verified input manifest')
        print('STATIC_INPUTS_PASS')
        return
    record['checkpoint_sha256'] = digest(checkpoint)
    manifest.write_text(json.dumps(record, indent=2) + '\n')
    lines = [f'{value}  {name}' for name, value in record['inputs'].items()]
    lines.append(f"{record['checkpoint_sha256']}  {checkpoint}")
    (out / 'static_inputs.sha256').write_text('\n'.join(lines) + '\n')
    pending.unlink(missing_ok=True)
    print('STATIC_INPUTS_RECORDED')


if __name__ == '__main__':
    main()
