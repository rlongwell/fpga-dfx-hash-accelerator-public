"""A fresh, physical BRAM replay sweep for Hash Lab, with auditable progress."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import shlex
import sys
import time

from uart import Cancelled

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'benchmarks/sha3_profile'))
from sweep_inputs import PATTERN, references, batches
from plot_size_sweep import summarize


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n'); temp.replace(path)


def validate_batch(actual, plan, index, variants):
    batch = plan['batches'][index]
    expected = {'state': 'passed', 'batch': index, 'mode': 'replay', 'core': batch['core'],
                'static_sha256': plan['static_sha256'], 'helper_sha256': plan['helper_sha256'],
                'board_script_sha256': plan['board_script_sha256'],
                'partial_sha256': variants['variants'][batch['core']]['image']['sha256']}
    if any(actual.get(k) != v for k, v in expected.items()):
        raise ValueError('Physical batch identity or completion differs from the plan.')
    recovery = actual.get('recovery', {})
    if (actual.get('partial_load_ns', 0) <= 0 or not recovery.get('verified') or
            recovery.get('dma_transfers') != 1 or recovery.get('digest') !=
            hashlib.sha3_256(b'Size sweep PS DMA recovery').hexdigest()):
        raise ValueError('Real reconfiguration and PS/DMA recovery were not verified.')
    if len(actual.get('rows', [])) != len(batch['cases']):
        raise ValueError('Physical batch has missing samples.')
    rows = []
    for row, case in zip(actual['rows'], batch['cases']):
        if row['case'] != case: raise ValueError('Physical case differs from plan.')
        ready = [e for e in row['events'] if e.get('event') == 'ready']
        result = [e for e in row['events'] if e.get('event') == 'result']
        if len(ready) != 1 or len(result) != 1: raise ValueError('Missing or duplicate hardware result.')
        ready, measured = ready[0], result[0]
        if (ready.get('algorithm_id') != 1 or ready.get('length') != case['length'] or
                ready.get('session') != case['session'] or not measured.get('ok') or
                measured.get('accepted') != case['length'] or measured.get('digest') != case['expected'] or
                type(measured.get('core_cycles')) is not int or measured['core_cycles'] <= 0):
            raise ValueError('Hardware identity, digest, byte count or cycle count failed validation.')
        seconds = measured['core_cycles'] / 1e8
        rows.append(dict(batch=index, artifact=f'batch-{index:02d}', mode='replay', core=batch['core'],
                         trial=batch['trial'], warmup=batch['warmup'], length=case['length'], verified=True,
                         expected=case['expected'], seconds=seconds,
                         MB_per_second=case['length']/seconds/1e6, board=measured, client=None))
    return rows


def run_replay(console, job, cancel, update, event, out):
    out.mkdir(parents=True, exist_ok=False)
    board_script = ROOT / 'benchmarks/sha3_profile/sweep_board.py'
    variants = json.loads((ROOT / 'demo/core_variants.json').read_text())
    remote = '/tmp/zybo-replay-' + job['id']
    update(stage='preparing', progress=0, completed_hashes=0, total_hashes=400,
           core_counts={'oxide': 0, 'compact': 0}, hashes_per_core=200,
           timing_scope='FPGA START through digest at 100 MHz; pattern loading and reconfiguration excluded')
    refs = references(30)
    if cancel.is_set(): raise Cancelled('Cancelled before the physical sweep.')
    board_mac = console.command('cat /sys/class/net/eth0/address').strip()
    plan = dict(kind='physical-sha3-size-sweep-plan', algorithm='SHA3-256', clock_MHz=100,
                max_power=30, repetitions=7, interface='fpga-bram-replay',
                static_sha256=variants['static_sha256'], board_mac=board_mac,
                host_mac=Path('/sys/class/net/enp3s0/address').read_text().strip(),
                helper_sha256=sha(ROOT / 'build/gem-direct/gem_board'), board_script_sha256=sha(board_script),
                pattern_bytes=len(PATTERN), pattern_sha256=hashlib.sha256(PATTERN).hexdigest(),
                batches=[b for b in batches(refs, 7, secrets.randbelow((1 << 32)-5000)+1) if b['mode']=='replay'],
                warmup='One full round per core, excluded; seven measured rounds',
                ordering='Ascending sizes per batch; core order alternates between rounds',
                timing={'replay': 'FPGA START-to-digest cycles / 100 MHz; pattern loading excluded'},
                transport=job['transport'])
    save(out / 'plan.json', plan)
    report = dict(kind='physical-sha3-size-sweep', state='running', started_utc=datetime.now(timezone.utc).isoformat(),
                  plan_sha256=sha(out / 'plan.json'), completed_batches=[], rows=[])
    save(out / 'results.json', report)
    counts = {'oxide': 0, 'compact': 0}
    try:
        console.command('mkdir ' + shlex.quote(remote))
        code = ('from pathlib import Path;import hashlib;'
                'd=bytes((i*131+(i>>8))&255 for i in range(131072));'
                f'assert hashlib.sha256(d).hexdigest()=={plan["pattern_sha256"]!r};'
                f'Path({remote+"/pattern.bin"!r}).write_bytes(d)')
        console.command('python3 -c ' + shlex.quote(code))
        console.upload(out / 'plan.json', remote + '/plan.json')
        console.upload(board_script, remote + '/sweep_board.py')
        for index, batch in enumerate(plan['batches']):
            if cancel.is_set(): raise Cancelled('Cancelled between batches; compact core and service restored.')
            update(stage='sweeping', current_core=batch['core'], current_trial=batch['trial'],
                   warmup=batch['warmup'], current_size=64)
            event({'event': 'batch_started', 'batch': index, 'core': batch['core'], 'trial': batch['trial']})
            destination = remote + f'/batch-{index:02d}.json'
            args = [remote+'/sweep_board.py', '--mode', 'replay', '--core', batch['core'],
                    '--plan', remote+'/plan.json', '--batch', str(index), '--output', destination]
            # Preserve the accepted batch's finally/recovery path if SSH closes.
            wrapper = ('import runpy,signal,sys\n'
                       'def hangup(*_): raise InterruptedError("SSH disconnected")\n'
                       'signal.signal(signal.SIGHUP,hangup)\n'
                       f'sys.argv={args!r}\nrunpy.run_path(sys.argv[0],run_name="__main__")\n')
            seen = []
            def receive(line):
                if not line.startswith('{'): return
                value = json.loads(line)
                if value.get('event') != 'case': return
                position = len(seen)
                if (position >= len(batch['cases']) or value.get('batch') != index or
                        value.get('length') != batch['cases'][position]['length']):
                    raise ValueError('Unexpected physical progress event.')
                seen.append(value['length']); counts[batch['core']] += 1
                event(dict(value, core=batch['core'], trial=batch['trial'], warmup=batch['warmup']))
                update(completed_hashes=sum(counts.values()), progress=sum(counts.values())/400,
                       core_counts=dict(counts), current_size=value['length'])
            try:
                console.stream('python3 -u -c ' + shlex.quote(wrapper), receive, timeout=150)
            finally:
                # The board stores each completed case atomically; retain it on failures too.
                raw = console.command('if [ -f ' + shlex.quote(destination) + ' ]; then cat ' + shlex.quote(destination) + '; fi')
                if raw: (out / f'batch-{index:02d}.json').write_text(raw)
            if len(seen) != len(batch['cases']): raise ValueError('Incomplete physical progress stream.')
            rows = validate_batch(json.loads(raw), plan, index, variants)
            report['rows'].extend(rows); report['completed_batches'].append(index); save(out / 'results.json', report)
        report['state'] = 'passed'
        summary = summarize(report, plan)
        save(out / 'summary.json', {'kind': 'computed-from-physical-samples', 'rows': summary})
        update(stage='restoring', sweep_summary=summary, measured_hashes=350, warmup_hashes=50,
               restored_sha3=True, sweep_plan_sha256=sha(out / 'plan.json'))
    except BaseException as error:
        report.update(state='cancelled' if isinstance(error, Cancelled) else 'failed', error=repr(error))
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat(); save(out / 'results.json', report)
        update(sweep_artifacts=str(out.relative_to(ROOT)), sweep_results_sha256=sha(out / 'results.json'))
        # No SD payloads: the entire new job directory was created in temporary RAM.
        console.command('if [ ! -d /run/zybo-hash-net.lock ]; then rm -rf -- ' + shlex.quote(remote) + '; fi')
