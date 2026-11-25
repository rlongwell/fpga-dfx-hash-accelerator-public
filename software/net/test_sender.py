#!/usr/bin/env python3
"""Host protocol test on a temporary veth pair; NOT physical FPGA evidence."""
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time


def main():
    binary = Path(sys.argv[1]).resolve()
    if os.geteuid() != 0:
        raise RuntimeError('Temporary veth test requires root')
    if sys.argv[2:] != ['--isolated']:
        # A desktop network manager can change a newly created veth's MAC
        # between discovery and bind. Keep this software-only peer completely
        # outside the host's managed network namespace.
        subprocess.run(['unshare','--net',sys.executable,str(Path(__file__).resolve()),
                        str(binary),'--isolated'],check=True)
        return
    a, b = 'htxa'+str(os.getpid()), 'htxb'+str(os.getpid())
    def ip(*args):
        subprocess.run(['ip',*args],check=True)
    def mac(interface):
        return json.loads(subprocess.check_output(['ip','-j','link','show','dev',interface],text=True))[0]['address']
    ip('link','add',a,'type','veth','peer','name',b)
    try:
        ip('link','set',a,'up');ip('link','set',b,'up')
        local=bytes.fromhex(mac(a).replace(':',''))
        target=bytes.fromhex(mac(b).replace(':',''))
        with tempfile.TemporaryDirectory(prefix='hash-sender-test-') as td:
            td=Path(td)
            for window,size in [(w,s) for w in (1,4,12,16) for s in (0,1,1440,1441,1048576)]:
                data=bytes((i*131+(i>>8))&255 for i in range(size))
                source=td/'input';source.write_bytes(data)
                output=td/f'{window}-{size}.json'
                session=871300+size*32+window;done=threading.Event();errors=[];counts={'rx':0,'tx':0}
                with socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x88b5)) as sock:
                    sock.bind((b,0x88b5));sock.settimeout(.0005)
                    def emulate():
                        accepted=0;digest=hashlib.sha3_256();dropped=False;announced=False;last=time.monotonic()
                        ready_at=last+.035  # Longer than the sender's retry interval.
                        try:
                            while not done.is_set():
                                try:
                                    frame=sock.recv(2048)
                                    counts['rx']+=1
                                    if len(frame)<64 or frame[:6]!=target or frame[12:16]!=bytes.fromhex('88b50101'):
                                        continue
                                    sid,offset,n=struct.unpack_from('<IQI',frame,16)
                                    if sid!=session or n>1440 or len(frame)!=64+n:continue
                                    if size>10000 and offset==4*1440 and not dropped:
                                        dropped=True;continue
                                    if offset==accepted:
                                        assert frame[64:]==data[offset:offset+n]
                                        digest.update(frame[64:]);accepted+=n
                                except socket.timeout:
                                    pass
                                now=time.monotonic()
                                if now<ready_at:continue
                                if now-last>=.0005 or accepted==size:
                                    status=int(accepted==size)
                                    response=local+target+bytes.fromhex('88b50102')+struct.pack('<IQI',session,accepted,status)+digest.digest()
                                    sock.send(response);counts['tx']+=1;last=now
                                    if not announced:
                                        # Hardware repeats readiness while waiting for data.
                                        # A queued old ACK must not expire a newly sent window.
                                        sock.send(response);counts['tx']+=1;announced=True
                        except BaseException as e:errors.append(e)
                    worker=threading.Thread(target=emulate);worker.start()
                    try:
                        result=subprocess.run([str(binary),a,target.hex(':'),str(session),str(source),str(output),str(window)],capture_output=True,text=True,timeout=8)
                        if result.returncode:raise RuntimeError(result.stderr)
                    except subprocess.TimeoutExpired:
                        print(json.dumps(dict(timeout_bytes=size,counts=counts,expected_local=local.hex(':'),expected_peer=target.hex(':'),
                                              actual_local=mac(a),actual_peer=mac(b))),file=sys.stderr)
                        raise
                    finally:
                        done.set();worker.join(2)
                        if errors:raise errors[0]
                    if errors:raise errors[0]
                    report=json.loads(output.read_text())
                    assert report['digest']==hashlib.sha3_256(data).hexdigest()
                    assert report['length']==size
                    assert report['window_frames']==window
                    if size>10000:assert report['retries']>0
                    else:assert report['retries']==0, 'Ready delay must not trigger a data retransmission'
                    print(json.dumps(dict(test='host-veth-protocol',window=window,bytes=size,retries=report['retries'],verified=True)))
    finally:ip('link','delete',a)


if __name__=='__main__':main()
