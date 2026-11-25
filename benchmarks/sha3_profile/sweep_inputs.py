#!/usr/bin/env python3
"""Physical SHA3-256 size sweep: powers of two, repeated data, interleaved cores."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'demo'))
from uart import Console
from compare_inputs import marker_value,read_log_payload
PATTERN=bytes((i*131+(i>>8))&255 for i in range(131072))


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def references(max_power):
    h=hashlib.sha3_256();done=0;result={}
    for power in range(6,max_power+1):
        size=1<<power
        while done<size:
            offset=done%len(PATTERN);n=min(size-done,len(PATTERN)-offset)
            h.update(PATTERN[offset:offset+n]);done+=n
        result[size]=h.hexdigest()
    return result


def batches(refs,repetitions,session_base):
    result=[];session=session_base
    for mode in ('replay','ethernet'):
        for trial in range(repetitions+1):
            # Trial zero is a complete warmup round, excluded from statistics.
            order=('oxide','compact') if trial%2==0 else ('compact','oxide')
            for core in order:
                cases=[]
                for size,digest in sorted(refs.items()):
                    cases.append(dict(length=size,expected=digest,session=session));session+=1
                result.append(dict(mode=mode,core=core,trial=trial,warmup=trial==0,cases=cases))
    assert session<1<<32
    return result


def write_json(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--data',type=Path,required=True,help='generated local input files; never sent over UART')
    p.add_argument('--max-power',type=int,default=30)
    p.add_argument('--repetitions',type=int,default=7)
    p.add_argument('--interface',default='enp3s0')
    p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    if not 6<=args.max_power<=30 or not 1<=args.repetitions<=15:p.error('max-power must be 6..30; repetitions 1..15')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=args.resume)
    args.data.mkdir(parents=True,exist_ok=True)
    remote='/root/hash-sweep-'+out.name
    local_sources=[Path(__file__).resolve(),Path(__file__).resolve().with_name('sweep_board.py'),Path(__file__).resolve().with_name('compare_inputs.py'),ROOT/'software/net/gem_send.c',ROOT/'build/gem-direct/gem_send']
    hashes={str(x.relative_to(ROOT)):sha(x) for x in local_sources}
    host_mac=(Path('/sys/class/net')/args.interface/'address').read_text().strip()
    refs=references(args.max_power)
    for size in refs:
        path=args.data/(str(size)+'.bin')
        if path.exists():
            assert path.stat().st_size==size
            with path.open('rb') as f:assert hashlib.file_digest(f,'sha3_256').hexdigest()==refs[size]
            continue
        with path.open('xb') as f:
            block=PATTERN*8
            for offset in range(0,size,len(block)):f.write(block[:min(size-offset,len(block))])
    with (out/'uart.log').open('ab') as log,Console(log) as c:
        board_mac=marker_value(c.command('printf "BOARD_MAC:"; cat /sys/class/net/eth0/address'),'BOARD_MAC',r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}')
        if not args.resume:
            c.command('mkdir '+shlex.quote(remote))
            code='from pathlib import Path;Path('+repr(remote+'/pattern.bin')+').write_bytes(bytes((i*131+(i>>8))&255 for i in range(131072)))'
            c.command('python3 -c '+shlex.quote(code))
    if args.resume:
        plan=json.loads((out/'plan.json').read_text());report=json.loads((out/'results.json').read_text())
        assert report['state']!='passed'
        assert plan['source_sha256']==hashes and plan['host_mac']==host_mac and plan['board_mac']==board_mac
        assert plan['max_power']==args.max_power and plan['repetitions']==args.repetitions and plan['interface']==args.interface
        attempt=report.get('attempt',1)+1
        write_json(out/f'before-resume-{attempt}.json',report)
        report.update(state='running',attempt=attempt);report.pop('error',None)
    else:
        manifest=json.loads((ROOT/'demo/board_manifest.json').read_text())
        plan=dict(kind='physical-sha3-size-sweep-plan',algorithm='SHA3-256',clock_MHz=100,
                  max_power=args.max_power,repetitions=args.repetitions,interface=args.interface,
                  static_sha256=manifest['static_sha256'],host_mac=host_mac,board_mac=board_mac,
                  helper_sha256=sha(ROOT/'build/gem-direct/gem_board'),board_script_sha256=sha(Path(__file__).with_name('sweep_board.py')),
                  source_sha256=hashes,pattern_bytes=len(PATTERN),pattern_sha256=hashlib.sha256(PATTERN).hexdigest(),
                  sender_window=12,batches=batches(refs,args.repetitions,secrets.randbelow((1<<32)-5000)+1),
                  timing={'replay':'FPGA START-to-digest cycles / 100 MHz; pattern loading excluded',
                          'ethernet':'PC first data send through FPGA digest reply; file access and transport included'},
                  warmup='One full round per core/mode, excluded; seven measured rounds by default',
                  ordering='Ascending powers of two in each batch; core order alternates between rounds')
        write_json(out/'plan.json',plan)
        report=dict(kind='physical-sha3-size-sweep',state='running',attempt=1,started_utc=datetime.now(timezone.utc).isoformat(),
                    plan_sha256=sha(out/'plan.json'),completed_batches=[],rows=[])
        uploader=Path('/home/rl/.codex/skills/zybo-file-transfer/scripts/upload.py')
        with (out/'upload.log').open('w') as log:
            for local,name in [(Path(__file__).with_name('sweep_board.py'),'sweep_board.py'),(out/'plan.json','plan.json')]:
                subprocess.run([sys.executable,str(uploader),str(local),remote+'/'+name],check=True,stdout=log,stderr=subprocess.STDOUT)
    write_json(out/'results.json',report)
    with (out/'uart.log').open('ab') as log,Console(log) as c:
        code='import hashlib;assert hashlib.sha256(open('+repr(remote+'/plan.json')+',"rb").read()).hexdigest()=='+repr(sha(out/'plan.json'))
        c.command('python3 -c '+shlex.quote(code))
        try:
            for index,batch in enumerate(plan['batches']):
                if index in report['completed_batches']:continue
                label=f'batch-{index:02d}-attempt-{report["attempt"]}'
                destination=remote+'/'+label+'.json';status=remote+'/'+label+'.status';board_log=remote+'/'+label+'.log'
                cmd=['python3','-u',remote+'/sweep_board.py','--mode',batch['mode'],'--core',batch['core'],
                     '--batch',str(index),'--plan',remote+'/plan.json','--output',destination]
                inner=('import os,subprocess;os.setpgid(0,0) if os.getpgrp()!=os.getpid() else None;'
                       'r=subprocess.run('+repr(cmd)+');open('+repr(status)+',"w").write(str(r.returncode)+"\\n")')
                launch='nohup python3 -c '+shlex.quote(inner)+' >'+shlex.quote(board_log)+' 2>&1 </dev/null & echo JOB_PID:$!'
                pid=int(marker_value(c.command(launch),'JOB_PID',r'\d+'))
                try:
                    clients={}
                    if batch['mode']=='ethernet':
                        for case in batch['cases']:
                            size=case['length'];client=out/f'{label}-{size}-client.json'
                            with (out/f'{label}-{size}-host.log').open('w') as hostlog:
                                proc=subprocess.Popen(['sudo','-n',str(ROOT/'build/gem-direct/gem_send'),args.interface,
                                                       board_mac,str(case['session']),str((args.data/(str(size)+'.bin')).resolve()),str(client),'12'],
                                                      stdout=hostlog,stderr=subprocess.STDOUT,start_new_session=True)
                                try:
                                    if proc.wait(timeout=185):raise RuntimeError('Host sender failed: '+str(client))
                                finally:
                                    if proc.poll() is None:
                                        subprocess.run(['sudo','-n','kill','-TERM','--','-'+str(proc.pid)],check=False)
                                        proc.wait(timeout=5)
                            value=json.loads(client.read_text())
                            assert value['length']==size and value['digest']==case['expected']
                            clients[size]=value
                    deadline=time.monotonic()+180
                    while True:
                        value=marker_value(c.command('if [ -f '+shlex.quote(status)+' ]; then printf "JOB_RC:"; cat '+shlex.quote(status)+'; fi'),'JOB_RC',r'-?\d+',required=False)
                        if value is not None:break
                        if time.monotonic()>deadline:raise TimeoutError('Batch completion deadline')
                        time.sleep(10)
                    (out/(label+'-board.log')).write_bytes(read_log_payload(c.command,board_log))
                    physical=json.loads(read_log_payload(c.command,destination));write_json(out/(label+'.json'),physical)
                    assert int(value)==0 and physical['state']=='passed' and physical['static_sha256']==plan['static_sha256']
                    assert physical['helper_sha256']==plan['helper_sha256'] and physical['board_script_sha256']==plan['board_script_sha256']
                    assert physical['partial_load_ns']>0 and physical['recovery']['verified'] and physical['recovery']['dma_transfers']==1
                    assert len(physical['rows'])==len(batch['cases'])
                    new_rows=[]
                    for actual,case in zip(physical['rows'],batch['cases']):
                        assert actual['case']==case
                        measured=next(x for x in actual['events'] if x['event']=='result');size=case['length']
                        assert measured['ok'] and measured['accepted']==size and measured['digest']==case['expected']
                        client=clients.get(size)
                        if client:
                            addresses=next(x for x in actual['events'] if x['event']=='dma_addresses')
                            assert 0x80000000<=addresses['rx_pointer']<0x80000100 and addresses['tx_pointer']==0x80000200
                        seconds=client['transfer_ns']/1e9 if client else measured['core_cycles']/1e8
                        new_rows.append(dict(batch=index,artifact=label,mode=batch['mode'],core=batch['core'],trial=batch['trial'],
                                                   warmup=batch['warmup'],length=size,verified=True,expected=case['expected'],seconds=seconds,
                                                   MB_per_second=size/seconds/1e6,board=measured,client=client))
                    report['rows'].extend(new_rows)
                    report['completed_batches'].append(index);write_json(out/'results.json',report)
                    print(json.dumps(dict(batch=index,mode=batch['mode'],core=batch['core'],trial=batch['trial'],
                                          warmup=batch['warmup'],sizes=len(batch['cases']),completed_rows=len(report['rows']))),flush=True)
                except BaseException:
                    stop='import os,signal;exec('+repr('try:\n if os.getpgid('+str(pid)+')=='+str(pid)+':os.killpg('+str(pid)+',signal.SIGTERM)\nexcept ProcessLookupError:pass')+')'
                    c.command('python3 -c '+shlex.quote(stop))
                    for _ in range(15):
                        state=c.command('if [ ! -d /run/zybo-hash-net.lock ]; then echo CLEANUP_DONE; fi')
                        if 'CLEANUP_DONE' in state.splitlines():c.command('/opt/zybo/hash/start.sh start');break
                        time.sleep(2)
                    try:(out/(label+'-board.log')).write_bytes(read_log_payload(c.command,board_log))
                    except Exception:pass
                    raise
            assert len(report['rows'])==sum(len(b['cases']) for b in plan['batches'])
            report['state']='passed'
        except BaseException as error:report.update(state='failed',error=repr(error));raise
        finally:
            report['finished_utc']=datetime.now(timezone.utc).isoformat();write_json(out/'results.json',report)


if __name__=='__main__':main()
