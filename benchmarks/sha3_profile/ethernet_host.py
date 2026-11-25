#!/usr/bin/env python3
"""Send the same verified 1 GiB file to the finite physical comparison server."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'software'))
from hash_client import hash_file


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    assert args.file.stat().st_size==1<<30
    with args.file.open('rb') as source:expected=hashlib.file_digest(source,'sha3_256').hexdigest()
    assert expected=='e8af7302ce25e585e530bbc336c6e3c05e7396e6b5320f86aeb33fbe193727b5'
    prefix=args.output.with_suffix('.prefix.bin')
    with args.file.open('rb') as source,prefix.open('xb') as out:out.write(source.read(16<<20))
    expected_prefix=hashlib.sha3_256(prefix.read_bytes()).hexdigest()
    report=dict(state='running',bytes=1<<30,input_sha3_256=expected,samples=[],warmups=[],
                route='10.77.78.1 enp3s0 -> 10.77.78.2 eth0',
                timing='Client after ready through digest response; includes PC file reads, Ethernet, PS and DMA/core; excludes reference hashing and pre-ready DFX')
    try:
        for mode in ('direct','prefetch'):
            for trial,core in enumerate(('oxide','compact','compact','oxide','oxide','compact'),1):
                for kind,path,digest in (('warmup',prefix,expected_prefix),('sample',args.file,expected)):
                    for retry in range(60):
                        try:result=hash_file('10.77.78.2',path,'sha3',port=9238);break
                        except ConnectionRefusedError:
                            if retry==59:raise
                            time.sleep(.5)
                    assert result['digest']==digest and result['core']==core and result['receive_mode']==mode
                    assert result['observed_intermediate_id']==2 and result['partial_load_ns']>0
                    row=dict(result,trial=trial,verified=True)
                    report['samples' if kind=='sample' else 'warmups'].append(row)
                    args.output.write_text(json.dumps(report,indent=2)+'\n')
                    if kind=='sample':print(mode,core,trial,round(result['client_transfer_and_result_ns']/1e9,6),round(result['client_transfer_and_result_MB_s'],3),flush=True)
        report['state']='passed';report['summary']={}
        for mode in ('direct','prefetch'):
            report['summary'][mode]={}
            for core in ('oxide','compact'):
                rows=[r for r in report['samples'] if r['receive_mode']==mode and r['core']==core]
                values=[r['client_transfer_and_result_ns']/1e9 for r in rows];median=statistics.median(values)
                report['summary'][mode][core]=dict(seconds=median,MB_per_second=(1<<30)/median/1e6,
                                                 range_seconds=[min(values),max(values)],samples=len(values))
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report['summary'],indent=2),flush=True)
    finally:prefix.unlink(missing_ok=True)


if __name__=='__main__':main()
