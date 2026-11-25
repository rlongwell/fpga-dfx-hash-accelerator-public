#!/usr/bin/env python3
"""Validate the on-board 1 GiB text comparison and summarize actual samples."""
import argparse
import json
from pathlib import Path
import statistics

SIZE = 1 << 30


def analyze(report, variants):
    assert report['state'] == 'passed'
    assert report['generation']['bytes'] == report['reference']['bytes'] == SIZE
    assert report['generation']['sha256'] == report['reference']['sha256']
    assert report['profile_env_before'] == report['profile_env_after']
    assert report['restored_compact']['verified'] and report['restored_compact']['partial_load_ns'] > 0
    assert report['restored_compact']['digest'] == 'a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a'
    assert 'running' in report['service_status'].lower()
    assert len(report['samples']) == len(report['warmups']) == 6
    rows = {}
    for index, (sample, warmup) in enumerate(zip(report['samples'],report['warmups'])):
        core = report['order'][index]
        assert sample['core'] == warmup['core'] == core
        assert sample['trial'] == warmup['trial'] == index+1
        assert sample['image'] == variants['variants'][core]['image']
        assert sample['partial_load_ns'] > 0 and sample['intermediate_algorithm_id'] == 2
        assert sample['algorithm_id'] == 1 and sample['backend'] == 'fpga-dma'
        assert sample['length'] == SIZE and sample['dma_transfers'] == 1024
        assert sample['core_cycles'] > 0 and sample['verified']
        assert not sample['reference_hashing_in_timed_region']
        assert sample['digest'] == report['reference']['sha3_256']
        assert warmup['length'] == 16 << 20 and warmup['dma_transfers'] == 16
        assert warmup['digest'] == report['reference']['warmup_prefix_sha3_256']
        assert sample['file_read_ns'] > 0 and sample['dma_calls_ns'] > 0 and sample['other_local_api_ns'] >= 0
        assert sample['local_hash_ns'] == sample['file_read_ns']+sample['dma_calls_ns']+sample['other_local_api_ns']
    for core in ('oxide','compact'):
        samples = [s for s in report['samples'] if s['core']==core]
        assert len(samples) == 3
        times = [s['local_hash_ns']/1e9 for s in samples]
        median = statistics.median(times)
        rows[core] = dict(file_seconds=median,range_seconds=[min(times),max(times)],
                          MB_per_second=SIZE/median/1e6,
                          dma_call_seconds=statistics.median(s['dma_calls_ns'] for s in samples)/1e9,
                          file_read_seconds=statistics.median(s['file_read_ns'] for s in samples)/1e9,
                          all_digests_verified=True,samples=3)
    rows['file_throughput_ratio'] = rows['oxide']['file_seconds']/rows['compact']['file_seconds']
    rows['dma_call_ratio'] = rows['oxide']['dma_call_seconds']/rows['compact']['dma_call_seconds']
    rows['file_time_ranges_overlap'] = max(rows['oxide']['range_seconds'][0],rows['compact']['range_seconds'][0]) <= min(rows['oxide']['range_seconds'][1],rows['compact']['range_seconds'][1])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--variants', type=Path, default=Path(__file__).resolve().parents[2]/'demo/core_variants.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(json.loads(args.report.read_text()),json.loads(args.variants.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
