#!/usr/bin/env python3
"""Finite physical comparison of direct/prefetched TCP input and both SHA3 cores."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

BASE = Path('/opt/zybo/hash')
sys.path.insert(0,str(BASE/'software'))
from hash_service import Hardware, firmware_path, handle_connection


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()


class RecordedHardware(Hardware):
    def start(self,length):
        self.dma_ns=0; self.transfers=0; self.last=None
        super().start(length)

    def transfer(self,length):
        start=time.perf_counter_ns();super().transfer(length)
        self.dma_ns+=time.perf_counter_ns()-start;self.transfers+=1

    def result(self):
        result=super().result()
        result.update(core=self.core,image_sha256=self.image_sha256,
                      dma_calls_ns=self.dma_ns,dma_transfers=self.transfers,
                      observed_intermediate_id=2,partial_load_ns=self.partial_load_ns)
        self.last=result
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variants',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise RuntimeError('Output already exists')
    base=json.loads((BASE/'dfx_manifest.json').read_text());config=json.loads(args.variants.read_text())
    assert Path('/proc/device-tree/model').read_bytes().rstrip(b'\0')==b'Digilent Zybo Z7-20 DFX hash accelerator'
    assert all(config[k]==base[k] for k in ('abi','part','static_sha256'))
    assert sha('/boot/profiles/hash/system.bit')==base['static_sha256']
    assert config['variants']['compact']['image']==base['images']['sha3']
    for variant in config['variants'].values():
        assert sha(firmware_path(variant['image']['filename']))==variant['image']['sha256']
    report=dict(state='running',kernel=subprocess.check_output(['uname','-r'],text=True).strip(),
                static_sha256=base['static_sha256'],profile_env_before=sha('/boot/profile.env'),
                service_sha256=sha(BASE/'software/hash_service.py'),
                receiver_sha256=sha(BASE/'software/hash_receive.py'),
                runner_sha256=sha(__file__),variants_sha256=sha(args.variants),
                link={k:Path('/sys/class/net/eth0/'+k).read_text().strip() for k in ('speed','duplex','mtu')},
                samples=[],warmups=[])

    def save():
        args.output.write_text(json.dumps(report,indent=2)+'\n')

    starter=str(BASE/'start.sh');safe=True
    try:
        subprocess.run([starter,'stop'],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['modprobe','hash_accel'],check=True)
        hardware=RecordedHardware(Path('/dev/hash-accel'),BASE/'dfx_manifest.json')
        try:
            with socket.create_server(('10.77.78.2',9238),backlog=1) as listener:
                listener.settimeout(120)
                for mode in ('direct','prefetch'):
                    for trial,core in enumerate(('oxide','compact','compact','oxide','oxide','compact'),1):
                        safe=False;hardware.manifest=deepcopy(base);hardware.select('sha256')
                        assert hardware.info()[1]==2
                        image=config['variants'][core]['image'];hardware.manifest['images']['sha3']=image
                        hardware.partial_load_ns=hardware.select('sha3')
                        assert hardware.partial_load_ns>0 and hardware.info()[1]==1
                        hardware.core=core;hardware.image_sha256=image['sha256']
                        print(json.dumps(dict(event='ready',mode=mode,core=core,trial=trial)),flush=True)
                        for kind,size in (('warmup',16<<20),('sample',1<<30)):
                            connection,peer=listener.accept()
                            with connection:
                                if peer[0]!='10.77.78.1':raise RuntimeError('Unexpected peer')
                                hardware.last=None
                                handle_connection(connection,hardware,timeout=60,receive_mode=mode)
                            result=hardware.last
                            if not result or result.get('status')!='ok' or result.get('length')!=size:
                                raise RuntimeError('Failed or unexpected request')
                            expected=('d25f807b3a05c52124033e901e84c352fea652c952f001cdfa85f06ebfc33169'
                                      if kind=='warmup' else 'e8af7302ce25e585e530bbc336c6e3c05e7396e6b5320f86aeb33fbe193727b5')
                            if result['digest']!=expected:raise RuntimeError('Hardware digest mismatch')
                            row=dict(result,trial=trial,peer=peer[0],kind=kind,verified=True)
                            report['samples' if kind=='sample' else 'warmups'].append(row);save()
                            print(json.dumps(dict(event='complete',**row)),flush=True)
        finally:
            try:
                hardware.manifest=deepcopy(base);hardware.select('sha256');load=hardware.select('sha3')
                hardware.start(0);restored=hardware.result()
                assert load>0 and restored['digest']==hashlib.sha3_256(b'').hexdigest()
                report['restored_compact']=dict(digest=restored['digest'],partial_load_ns=load)
                safe=True
            finally:hardware.close()
        report['state']='passed'
    except BaseException as error:
        report.update(state='failed',error=str(error));raise
    finally:
        if safe:subprocess.run([starter,'start'],check=True,stdout=subprocess.DEVNULL)
        else:report['service_left_stopped_for_recovery']=True
        report['profile_env_after']=sha('/boot/profile.env');save()
        print(json.dumps(dict(event='finished',state=report['state'],output=str(args.output))),flush=True)


if __name__=='__main__':
    def interrupted(*_):raise TimeoutError('Ethernet comparison interrupted or timed out')
    signal.signal(signal.SIGALRM,interrupted);signal.signal(signal.SIGTERM,interrupted)
    signal.alarm(900)
    main()
