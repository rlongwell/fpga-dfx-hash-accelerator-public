#!/usr/bin/env python3
"""Physical-board ownership checks; keeps the running PS service untouched."""
import json
import os
from pathlib import Path
import subprocess
import sys

BASE=Path('/opt/zybo/hash')
sys.path.insert(0,str(BASE/'software'))
from hash_service import control_lock


def main():
    assert os.uname().machine.startswith('arm'), 'Run on the physical board'
    pidfile=Path('/run/zybo-hash.pid')
    initial=pidfile.read_bytes()
    pid=int(initial)
    assert str(BASE/'software/hash_service.py').encode() in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    lock=Path('/run/zybo-hash-net.lock')
    results=[]
    with control_lock():
        lock.mkdir()
        try:
            (lock/'owner').write_text(str(os.getpid())+'\n')
            commands=[
                ([str(BASE/'start.sh'),'stop'],'Ethernet/replay job'),
                ([sys.executable,'-c',"import sys;sys.path.insert(0,'/opt/zybo/hash/software');from hash_local import LocalHasher;LocalHasher()"],'Ethernet/replay job'),
                ([sys.executable,str(BASE/'net/board_run.py'),'replay','--length','1','--session','1','--pattern','/not-used'],'Another FPGA input operation'),
            ]
            for command,message in commands:
                result=subprocess.run(command,capture_output=True,text=True,timeout=5)
                assert result.returncode!=0 and message in result.stderr,(command,result)
                assert pidfile.read_bytes()==initial
                os.kill(pid,0)
                results.append(dict(command=command,rejected=True,reason=message))
        finally:
            (lock/'owner').unlink(missing_ok=True)
            lock.rmdir()
    assert pidfile.read_bytes()==initial
    print(json.dumps(dict(kind='physical-ownership-guards',passed=True,service_pid=pid,
                          service_pid_unchanged=True,checks=results)))


if __name__=='__main__':main()
