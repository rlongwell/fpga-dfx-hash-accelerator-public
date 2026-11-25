#!/usr/bin/env python3
"""Physical acceptance of packet/replay inputs. Run after deploying the matched bundle."""
import argparse
from datetime import datetime,timezone
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'demo'))
from uart import Console


def marker_value(output,label,pattern,required=True):
    """Match a complete output record, excluding UART's wrapped command echo."""
    found=re.findall(r'(?m)^'+re.escape(label)+r':('+pattern+r')\r?$',output)
    if not found and not required:return None
    if len(found)!=1:raise ValueError(f'Expected one complete {label} record, got {len(found)}')
    return found[0]


def read_log_payload(command,path,attempts=3):
    """Read-only retry: kernel console messages may interleave with stdout.

    Accept only a whole base64 record with a valid gzip length/CRC. Never strip
    arbitrary text out of an interrupted record and call it evidence.
    """
    code='import base64,gzip;print("LOG_PAYLOAD:"+base64.b64encode(gzip.compress(open('+repr(path)+',"rb").read())).decode())'
    for attempt in range(attempts):
        result=command('python3 -c '+shlex.quote(code))
        try:
            value=marker_value(result,'LOG_PAYLOAD',r'[A-Za-z0-9+/]+={0,2}')
            return gzip.decompress(base64.b64decode(value,validate=True))
        except (ValueError,OSError,EOFError):
            if attempt+1==attempts:raise
            time.sleep(.2)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--file-1gib',type=Path,required=True)
    p.add_argument('--smoke-only',action='store_true')
    p.add_argument('--smoke-bytes',type=int,default=65537)
    p.add_argument('--smoke-core',choices=['compact','oxide','sha256','blake2s'],default='compact')
    p.add_argument('--sender-window',type=int,default=12)
    p.add_argument('--resume',action='store_true',help='continue an incomplete report, preserving completed cases and source history')
    p.add_argument('--mode',choices=['all','replay','ethernet'],default='all')
    p.add_argument('--interface',default='enp3s0')
    args=p.parse_args()
    if not 1 <= args.sender_window <= 32:p.error('--sender-window must be 1..32')
    if not 0 <= args.smoke_bytes <= 16<<20:p.error('--smoke-bytes must be 0..16777216')
    if args.resume and (args.smoke_only or args.mode!='all'):
        p.error('--resume requires the complete acceptance plan (--mode all, without --smoke-only)')
    modes=('replay','ethernet') if args.mode=='all' else (args.mode,)
    args.output.mkdir(parents=True,exist_ok=args.resume)
    out=args.output.resolve();remote='/root/hash-net-'+out.name
    pattern=bytes((i*131+(i>>8))&255 for i in range(131072))
    maximum_pattern=bytes((i*131+(i>>8))&255 for i in range(258048))
    report=dict(kind='physical-zybo-gem-and-replay',state='running',rows=[],pattern_bytes=len(pattern),
                sender_window=args.sender_window,
                started_utc=datetime.now(timezone.utc).isoformat(),
                source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in [Path(__file__).resolve(),ROOT/'software/net/gem_send.c',
                                            ROOT/'build/gem-direct/gem_send']},
                pattern_sha256=hashlib.sha256(pattern).hexdigest(),
                timing=dict(ethernet='PC first data send through FPGA digest reply, no software hash in interval',
                            replay='FPGA START through digest, core_cycles at 100 MHz; pattern loading excluded'))
    if args.resume:
        previous=json.loads((out/'results.json').read_text())
        if previous['state']=='passed':raise ValueError('This acceptance report is already complete')
        for key in ('kind','pattern_bytes','pattern_sha256','sender_window','timing'):
            if previous[key]!=report[key]:raise ValueError('Resume configuration changed: '+key)
        for key in ('software/net/gem_send.c','build/gem-direct/gem_send'):
            if previous['source_sha256'][key]!=report['source_sha256'][key]:raise ValueError('Sender changed; use a fresh acceptance report')
        history=previous.setdefault('continuations',[])
        (out/f'before-resume-{len(history)+1}.json').write_text(json.dumps(previous,indent=2)+'\n')
        history.append(dict(started_utc=report['started_utc'],source_sha256=report['source_sha256']))
        report=previous;report['state']='running';report.pop('error',None);report.pop('finished_utc',None)
    completed={r['label']:r for r in report['rows']}
    if len(completed)!=len(report['rows']):raise ValueError('Duplicate completed case labels')
    requested=set()
    refs={}
    def save():
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    def command(cmd,timeout=30):
        with (out/'uart.log').open('ab') as log,Console(log) as c:
            return c.command(cmd,timeout)
    def fetch(path):
        return read_log_payload(command,path)
    host_mac=(Path('/sys/class/net')/args.interface/'address').read_text().strip()
    identity=command('printf "BOARD_MAC:"; cat /sys/class/net/eth0/address')
    board_mac=marker_value(identity,'BOARD_MAC',r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}')
    assert len(bytes.fromhex(host_mac.replace(':','')))==6 and len(bytes.fromhex(board_mac.replace(':','')))==6
    network=dict(interface=args.interface,host_mac=host_mac,board_mac=board_mac)
    if args.resume and report['network']!=network:raise ValueError('Network identity changed; use a fresh acceptance report')
    report['network']=network
    command(('test -d ' if args.resume else 'mkdir ')+shlex.quote(remote))
    for size in (len(pattern),len(maximum_pattern)):
        if args.resume:continue
        code='from pathlib import Path;Path('+repr(remote+'/pattern-'+str(size)+'.bin')+').write_bytes(bytes((i*131+(i>>8))&255 for i in range('+str(size)+')))'
        command('python3 -c '+shlex.quote(code))
    constructors=dict(compact=hashlib.sha3_256,oxide=hashlib.sha3_256,sha256=hashlib.sha256,blake2s=hashlib.blake2s)
    def reference(core,size,source,pattern_data=pattern):
        key=(core=='oxide' and 'compact' or core,size,source,len(pattern_data))
        if key not in refs:
            h=constructors[core]()
            if source=='file':
                with args.file_1gib.open('rb') as f:
                    while block:=f.read(1<<20):h.update(block)
            else:
                for _ in range(size//len(pattern_data)):h.update(pattern_data)
                h.update(pattern_data[:size%len(pattern_data)])
            refs[key]=h.hexdigest()
        return refs[key]
    def case(mode,core,size,label,source='pattern',freeze_control=False,pattern_data=pattern):
        if label in requested:raise ValueError('Duplicate planned case: '+label)
        requested.add(label)
        expected=reference(core,size,source,pattern_data)
        canonical_label=label
        if label in completed:
            prior=completed[label]
            expected_fields=dict(mode=mode,core=core,length=size,source=source,expected=expected,verified=True,
                                 pattern_bytes=len(pattern_data) if source=='pattern' else None)
            if any(prior[k]!=v for k,v in expected_fields.items()):raise ValueError('Completed case differs from current specification: '+label)
            if freeze_control and not prior['stopped_control_proof']:raise ValueError('Missing stopped-control proof')
            return
        if args.resume:
            label += '-attempt-'+str(len(report['continuations'])+1)
        session=secrets.randbelow((1<<32)-1)+1
        board_log=remote+'/'+label+'.log';status=remote+'/'+label+'.status'
        command_args=['python3','/opt/zybo/hash/net/board_run.py',mode,'--core',core,'--length',str(size),'--session',str(session)]
        if mode=='ethernet':command_args+=['--peer-mac',host_mac]
        if mode=='replay':command_args+=['--pattern',remote+'/pattern-'+str(len(pattern_data))+'.bin']
        # BusyBox ash may already make the background job a process-group
        # leader, in which case setsid() fails with EPERM. nohup handles HUP;
        # ensure a private process group without requiring a new session.
        inner=('import os,subprocess;'
               'os.setpgid(0,0) if os.getpgrp()!=os.getpid() else None;'
               'r=subprocess.run('+repr(command_args)+');'
               'open('+repr(status)+',"w").write(str(r.returncode)+"\\n")')
        launch='nohup python3 -c '+shlex.quote(inner)+' >'+shlex.quote(board_log)+' 2>&1 </dev/null & echo JOB_PID:$!'
        response=command(launch)
        pid=int(marker_value(response,'JOB_PID',r'\d+'))
        process=None;client=None;control_pid=None;control_proof=None
        host_log=(out/(label+'-host.log')).open('w')
        try:
            if mode=='ethernet':
                if freeze_control:
                    deadline=time.monotonic()+25
                    while time.monotonic()<deadline:
                        ready=command('if grep -q '+shlex.quote('"event":"ready"')+' '+shlex.quote(board_log)+
                                      '; then printf "CONTROL_PID:"; pidof gem_board; fi')
                        value=marker_value(ready,'CONTROL_PID',r'\d+',required=False)
                        if value:
                            control_pid=int(value);break
                        time.sleep(2)
                    if control_pid is None:raise TimeoutError('GEM control process did not become ready')
                    command('kill -STOP '+str(control_pid))
                    before=command('grep State /proc/'+str(control_pid)+'/status')
                    assert 'T (stopped)' in before
                    control_proof={'pid':control_pid,'before_transfer':before}
                path=args.file_1gib
                if source!='file':
                    path=out/'packet-input.bin'
                    path.write_bytes((pattern_data*((size+len(pattern_data)-1)//len(pattern_data)))[:size])
                client_path=out/(label+'-client.json')
                process=subprocess.Popen(['sudo','-n',str(ROOT/'build/gem-direct/gem_send'),args.interface,
                                          board_mac,str(session),str(path.resolve()),str(client_path),str(args.sender_window)],
                                         stdout=host_log,stderr=subprocess.STDOUT,start_new_session=True)
                if freeze_control:
                    # The FPGA must return the digest while the only userspace
                    # hardware-control process is stopped, including its poll loop.
                    if process.wait(timeout=60):raise RuntimeError('Sender failed while control process was stopped')
                    after=command('grep State /proc/'+str(control_pid)+'/status')
                    assert 'T (stopped)' in after
                    control_proof['after_digest_received']=after
                    command('kill -CONT '+str(control_pid));control_pid=None
            deadline=time.monotonic()+215;rc=None
            while time.monotonic()<deadline:
                time.sleep(2)
                result=command('if [ -f '+shlex.quote(status)+' ]; then printf "JOB_RC:"; cat '+shlex.quote(status)+
                               '; elif kill -0 '+str(pid)+' 2>/dev/null; then echo JOB_WAIT; else echo JOB_GONE; fi')
                value=marker_value(result,'JOB_RC',r'-?\d+',required=False)
                if value is not None:rc=int(value);break
                if any(line.strip()=='JOB_GONE' for line in result.splitlines()):
                    raise RuntimeError('Board launcher exited without a status file')
                if process and process.poll() not in (None,0):
                    raise RuntimeError('Host sender failed: '+(out/(label+'-host.log')).read_text())
            if rc is None:raise TimeoutError('Board run exceeded its bounded deadline')
            log=fetch(board_log);(out/(label+'-board.log')).write_bytes(log)
            events=[json.loads(line) for line in log.decode().splitlines() if line.startswith('{')]
            if rc:raise RuntimeError('Board run failed: '+log.decode()[-3000:])
            config=next(e for e in events if e['event']=='configuration')
            result=next(e for e in events if e['event']=='result')
            restored=next(e for e in events if e['event']=='restored')
            assert config['core']==core and config['partial_load_ns']>0 and config['intermediate_algorithm_id']!=(1 if core in ('compact','oxide') else (2 if core=='sha256' else 3))
            if report['rows']:
                assert config['static_sha256']==report['rows'][0]['configuration']['static_sha256'], 'Static image changed within acceptance run'
            assert result['ok'] and result['accepted']==size and result['digest']==expected
            assert restored['core']=='compact' and restored['ps_api']
            assert restored['dma_probe']['dma_transfers']==1 and restored['dma_probe']['verified']
            if process:
                if process.wait(timeout=3):raise RuntimeError('Sender returned failure')
                client=json.loads(client_path.read_text())
                assert client['digest']==expected and client['length']==size
                addresses=next(e for e in events if e['event']=='dma_addresses')
                assert 0x80000000<=addresses['rx_pointer']<0x80000100
                assert addresses['tx_pointer']==0x80000200
            seconds=(client['transfer_ns']/1e9 if client else result['core_cycles']/1e8)
            row=dict(label=canonical_label,artifact_prefix=label,provenance_run=len(report.get('continuations',[])),mode=mode,core=core,length=size,source=source,verified=True,
                     pattern_bytes=len(pattern_data) if source=='pattern' else None,
                     expected=expected,seconds=seconds,MB_per_second=size/seconds/1e6 if seconds else 0,
                     configuration=config,board=result,client=client,stopped_control_proof=control_proof)
            report['rows'].append(row);save()
            print(json.dumps({k:row[k] for k in ('label','mode','core','length','verified','seconds','MB_per_second')}),flush=True)
        except BaseException:
            if control_pid:
                command('kill -CONT '+str(control_pid)+' 2>/dev/null || true')
            if process and process.poll() is None:
                subprocess.run(['sudo','-n','kill','-TERM','--','-'+str(process.pid)],check=False)
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    subprocess.run(['sudo','-n','kill','-KILL','--','-'+str(process.pid)],check=False)
                    process.wait(timeout=3)
            # A completed launcher can leave the restored service in its old
            # process group. Never signal that group after its leader exits.
            stop=('import os,signal;exec('+repr('try:\n if os.getpgid('+str(pid)+')=='+str(pid)+':os.killpg('+str(pid)+',signal.SIGTERM)\nexcept ProcessLookupError:pass')+')')
            command('python3 -c '+shlex.quote(stop))
            # Allow board_run's finally block to restore the driver, link and API.
            cleanup_deadline=time.monotonic()+30
            while time.monotonic()<cleanup_deadline:
                cleanup=command('if [ ! -d /run/zybo-hash-net.lock ]; then echo CLEANUP_DONE; fi')
                if any(line.strip()=='CLEANUP_DONE' for line in cleanup.splitlines()):
                    command('/opt/zybo/hash/start.sh start')
                    break
                time.sleep(3)
            try:(out/(label+'-board.log')).write_bytes(fetch(board_log))
            except Exception:pass
            raise
        finally:host_log.close()
    try:
        if args.smoke_only:
            for mode in modes:
                case(mode,args.smoke_core,args.smoke_bytes,mode+'-smoke')
        else:
            if 'replay' in modes:
                case('replay','compact',len(maximum_pattern)*4+17,'replay-maximum-pattern',pattern_data=maximum_pattern)
            if 'ethernet' in modes:
                case('ethernet','compact',1048593,'ethernet-stopped-control',freeze_control=True)
            for mode in modes:
                for core in constructors:
                    boundary=136 if core in ('compact','oxide') else 64
                    sizes=([1] if core=='oxide' else [0,1])+([55,56] if core=='sha256' else [])+[boundary-1,boundary,boundary+1,65537,1048593]
                    for size in sizes:case(mode,core,size,f'{mode}-{core}-{size}')
            assert args.file_1gib.stat().st_size==1<<30
            assert reference('compact',1<<30,'file')=='e8af7302ce25e585e530bbc336c6e3c05e7396e6b5320f86aeb33fbe193727b5'
            for mode in modes:
                for trial,core in enumerate(('oxide','compact','compact','oxide','oxide','compact'),1):
                    case(mode,core,16<<20,f'{mode}-warmup-{trial}')
                    case(mode,core,1<<30,f'{mode}-bulk-{trial}','file' if mode=='ethernet' else 'pattern')
        if {r['label'] for r in report['rows']}!=requested:
            raise ValueError('Completed cases do not match the full requested acceptance plan')
        report['state']='passed'
    except BaseException as error:
        report.update(state='failed',error=str(error));raise
    finally:
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        save()


if __name__=='__main__':main()
