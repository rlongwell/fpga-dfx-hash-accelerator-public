#!/usr/bin/env python3
"""One bounded physical size-sweep batch; deploy through the USB UART.

Reuses the accepted gem_board executable. No installed runtime or RTL edits.
Each C invocation loads/checks RAM outside its hardware START-to-digest timer.
"""
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

BASE=Path('/opt/zybo/hash')
sys.path.insert(0,str(BASE/'software'))
from hash_service import Hardware,control_lock,firmware_path
from hash_local import LocalHasher


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def run(*args,**kwargs):return subprocess.run(args,check=True,**kwargs)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('replay','ethernet'),required=True)
    p.add_argument('--core',choices=('compact','oxide'),required=True)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--batch',type=int,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    plan=json.loads(args.plan.read_text());batch=plan['batches'][args.batch]
    assert batch['mode']==args.mode and batch['core']==args.core
    assert 1<=len(batch['cases'])<=25
    assert all(64<=x['length']<=1<<30 and x['length']&(x['length']-1)==0 for x in batch['cases'])
    assert not args.output.exists()
    manifest=json.loads((BASE/'dfx_manifest.json').read_text())
    variants=json.loads((BASE/'net/core_variants.json').read_text())
    boot=Path('/proc/device-tree/core-forge,static-sha256').read_bytes().rstrip(b'\0').decode()
    assert boot==manifest['static_sha256']==variants['static_sha256']==plan['static_sha256']
    assert sha('/boot/profiles/hash/system.bit')==boot
    assert Path('/proc/device-tree/axi/hash-ingress@80000000/compatible').read_bytes()==b'core-forge,gem-hash-ingress-1.0\0'
    image=variants['variants'][args.core]['image']
    assert sha(firmware_path(image['filename']))==image['sha256']
    assert sha(BASE/'net/gem_board')==plan['helper_sha256']
    assert sha(__file__)==plan['board_script_sha256']
    pattern=args.plan.parent/'pattern.bin'
    assert sha(pattern)==plan['pattern_sha256']
    assert Path('/sys/class/net/eth0/address').read_text().strip()==plan['board_mac']
    ethernet=args.mode=='ethernet'
    power=Path('/sys/class/net/eth0/device/power/control');previous_power=power.read_text().strip()
    phy=int(Path('/sys/class/net/eth0/phydev').resolve().name.rsplit(':',1)[1],16)
    if ethernet:
        deadline=time.monotonic()+10
        while time.monotonic()<deadline and Path('/sys/class/net/eth0/carrier').read_text().strip()!='1':time.sleep(.05)
        assert Path('/sys/class/net/eth0/speed').read_text().strip()=='1000'
        assert Path('/sys/class/net/eth0/duplex').read_text().strip()=='full'
    lock=Path('/run/zybo-hash-net.lock');lock.mkdir()
    stopped=False;reset=False;network_down=False
    report=dict(kind='physical-size-sweep-batch',batch=args.batch,mode=args.mode,core=args.core,
                static_sha256=boot,partial_sha256=image['sha256'],helper_sha256=sha(BASE/'net/gem_board'),
                board_script_sha256=sha(__file__),rows=[],state='running')
    def save():
        temporary=args.output.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(args.output)
    try:
        (lock/'owner').write_text(str(os.getpid())+'\n')
        run(str(BASE/'start.sh'),'stop',env={**os.environ,'HASH_NET_OWNER':str(os.getpid())})
        stopped=True
        run('modprobe','hash_accel')
        h=Hardware(Path('/dev/hash-accel'),BASE/'dfx_manifest.json')
        try:
            h.select('sha256');assert h.info()[1]==2
            h.manifest=deepcopy(manifest);h.manifest['images']['sha3']=image
            report['partial_load_ns']=h.select('sha3');assert report['partial_load_ns']>0 and h.info()[1]==1
        finally:h.close()
        run('modprobe','-r','hash_accel');reset=True
        if ethernet:
            power.write_text('on\n');run('ip','link','set','eth0','down');network_down=True
        save()
        for case in batch['cases']:
            result=run(str(BASE/'net/gem_board'),args.mode,str(case['length']),str(case['session']),
                       str(pattern) if not ethernet else '-',plan['host_mac'],plan['board_mac'],str(phy),
                       capture_output=True,text=True,timeout=200)
            events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            ready=next(x for x in events if x['event']=='ready')
            measured=next(x for x in events if x['event']=='result')
            assert ready['algorithm_id']==1 and ready['session']==case['session'] and ready['length']==case['length']
            assert measured['ok'] and measured['accepted']==case['length'] and measured['digest']==case['expected']
            report['rows'].append(dict(case=case,events=events,stdout=result.stdout,stderr=result.stderr));save()
            print(json.dumps(dict(event='case',batch=args.batch,length=case['length'],cycles=measured['core_cycles'])),flush=True)
        report['state']='passed'
    except BaseException as error:
        report.update(state='failed',error=repr(error))
        if isinstance(error,subprocess.CalledProcessError):
            report.update(failed_stdout=error.stdout,failed_stderr=error.stderr)
        raise
    finally:
        try:
            if reset:run(str(BASE/'net/gem_board'),'reset-ethernet' if network_down else 'reset-replay',timeout=5)
            if network_down:run('ip','link','set','eth0','up')
            if ethernet:power.write_text(previous_power+'\n')
            if stopped:
                run('modprobe','hash_accel');h=Hardware(Path('/dev/hash-accel'),BASE/'dfx_manifest.json')
                try:h.select('sha256');h.select('sha3')
                finally:h.close()
                with LocalHasher(manifest=BASE/'dfx_manifest.json') as api:
                    report['recovery']=api.hash_bytes(b'Size sweep PS DMA recovery','sha3',verify=True)
                assert report['recovery']['verified'] and report['recovery']['dma_transfers']==1
                (lock/'owner').unlink();lock.rmdir();run(str(BASE/'start.sh'),'start')
        except BaseException as error:
            report.update(state='failed',cleanup_error=repr(error));raise
        finally:
            if lock.exists():(lock/'owner').unlink(missing_ok=True);lock.rmdir()
            save()


if __name__=='__main__':
    def interrupted(*_):raise InterruptedError('Sweep interrupted')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    with control_lock():main()
