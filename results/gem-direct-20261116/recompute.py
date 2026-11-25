#!/usr/bin/env python3
"""Recompute the recorded comparison; does not access hardware or rerun tests."""
from pathlib import Path
from statistics import median
from hashlib import sha256
from datetime import datetime,timezone
import json
root=Path(__file__).resolve().parent;data=json.loads((root/'acceptance-final/results.json').read_text())
assert data['state']=='passed' and len(data['rows'])==84
assert len({r['label'] for r in data['rows']})==84
assert all(r['verified'] and r['board']['ok'] and r['board']['digest']==r['expected'] and r['board']['accepted']==r['length'] for r in data['rows'])
assert len({r['configuration']['static_sha256'] for r in data['rows']})==1
summary={'kind':'physical-zybo-input-comparison','completed_utc':datetime.now(timezone.utc).isoformat(),'cases':len(data['rows']),'modes':{},'physical_source':'acceptance-final/results.json','source_sha256':sha256((root/'acceptance-final/results.json').read_bytes()).hexdigest(),'static_sha256':data['rows'][0]['configuration']['static_sha256'],'network':data['network']}
for mode in ('replay','ethernet'):
 groups={}
 for core in ('oxide','compact'):
  rows=[r for r in data['rows'] if r['mode']==mode and r['core']==core and '-bulk-' in r['label']]
  assert len(rows)==3 and all(r['verified'] and r['length']==1<<30 for r in rows)
  seconds=[r['seconds'] for r in rows];m=median(seconds)
  groups[core]={'samples':3,'median_seconds':m,'MB_per_second':(1<<30)/m/1e6,'seconds':seconds,'hardware_cycles':[r['board']['core_cycles'] for r in rows],'digests':sorted({r['expected'] for r in rows}),'retries':[r['client']['retries'] for r in rows] if mode=='ethernet' else None}
 assert groups['compact']['digests']==groups['oxide']['digests']
 groups['compact_speedup']=groups['oxide']['median_seconds']/groups['compact']['median_seconds']
 summary['modes'][mode]=groups
summary['stopped_control_verified']=any(r['stopped_control_proof'] and r['verified'] for r in data['rows'])
assert summary['stopped_control_verified']
summary['resources_source_sha256']=sha256((root/'implementation-bram64/summary.json').read_bytes()).hexdigest()
resources=json.loads((root/'implementation-bram64/summary.json').read_text())['configurations']
summary['hash_partition_resources']={c:resources[c]['resources']['u_hash'] for c in ('oxide','compact')}
summary['resource_reduction_percent']={k:100*(1-summary['hash_partition_resources']['compact'][k]/summary['hash_partition_resources']['oxide'][k]) for k in ('LUT','FF')}
summary['scopes']={'replay':'1 GiB of repeated 128 KiB FPGA-resident test data; FPGA START-to-digest at 100 MHz; pattern loading and software hashing excluded.','ethernet':'Same stored 1 GiB random-text file; PC first data send through FPGA digest reply; file reads and transport included; setup/DFX/reference hashing excluded.','resources':'Vivado routed hash-partition LUT/FF counts, same new static shell and clock; not whole-device percentages.'}
destination=root/'comparison-final.json'
if destination.exists():
 previous=json.loads(destination.read_text())
 summary['completed_utc']=previous['completed_utc']
 assert summary==previous, 'Recorded comparison differs from recomputed evidence'
else:
 destination.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
