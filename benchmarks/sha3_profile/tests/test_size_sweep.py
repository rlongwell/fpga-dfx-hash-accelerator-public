"""Validate the physical sweep's repeatable input and balanced measurement plan."""
import hashlib
from pathlib import Path
import sys
import unittest
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sweep_inputs import PATTERN,references,batches
from plot_size_sweep import summarize


class SizeSweepPlan(unittest.TestCase):
    def test_prefix_digests_across_pattern_wrap(self):
        for size,digest in references(19).items():
            data=(PATTERN*((size+len(PATTERN)-1)//len(PATTERN)))[:size]
            self.assertEqual(digest,hashlib.sha3_256(data).hexdigest())

    def test_25_sizes_700_measured_100_warmups(self):
        refs={1<<p:'fixture' for p in range(6,31)}
        plan=batches(refs,7,123)
        self.assertEqual(sum(len(b['cases']) for b in plan if not b['warmup']),700)
        self.assertEqual(sum(len(b['cases']) for b in plan if b['warmup']),100)
        sessions=[c['session'] for b in plan for c in b['cases']]
        self.assertEqual(len(sessions),len(set(sessions)))
        for mode in ('replay','ethernet'):
            for core in ('compact','oxide'):
                for size in refs:
                    samples=[c for b in plan if b['mode']==mode and b['core']==core and not b['warmup'] for c in b['cases'] if c['length']==size]
                    self.assertEqual(len(samples),7)

    def test_core_order_alternates(self):
        plan=batches({64:'fixture'},7,1)
        for mode in ('replay','ethernet'):
            rounds=[[b['core'] for b in plan if b['mode']==mode and b['trial']==trial] for trial in range(8)]
            self.assertEqual(rounds.count(['oxide','compact']),4)
            self.assertEqual(rounds.count(['compact','oxide']),4)

    def test_session_wrap_is_rejected(self):
        with self.assertRaises(AssertionError):batches({64:'fixture'},7,(1<<32)-2)


class SweepSummary(unittest.TestCase):
    def setUp(self):
        self.plan=dict(max_power=6,repetitions=2,batches=batches({64:'digest'},2,1))
        rows=[]
        for batch in self.plan['batches']:
            seconds=100 if batch['warmup'] else (2 if batch['core']=='oxide' else 1)
            rows.append(dict(mode=batch['mode'],core=batch['core'],trial=batch['trial'],warmup=batch['warmup'],length=64,
                             verified=True,seconds=seconds,expected='digest',
                             board=dict(ok=True,accepted=64,digest='digest',core_cycles=int(seconds*1e8)),
                             client=dict(transfer_ns=int(seconds*1e9),digest='digest',length=64) if batch['mode']=='ethernet' else None))
        self.report=dict(state='passed',rows=rows)

    def test_uses_all_repetitions_and_excludes_warmup(self):
        for row in summarize(self.report,self.plan):
            self.assertEqual(row['speedup'],2)
            self.assertEqual(row['compact_median_seconds'],1)
            self.assertEqual(row['samples_per_core'],2)

    def test_missing_duplicate_and_mismatched_timer_rejected(self):
        changed=deepcopy(self.report);changed['rows'].pop()
        with self.assertRaisesRegex(ValueError,'Missing'):summarize(changed,self.plan)
        changed=deepcopy(self.report);changed['rows'].append(changed['rows'][0])
        with self.assertRaisesRegex(ValueError,'Duplicate'):summarize(changed,self.plan)
        changed=deepcopy(self.report);changed['rows'][0]['seconds']=.1
        with self.assertRaisesRegex(ValueError,'timer'):summarize(changed,self.plan)

    def test_replay_only_plan_is_supported(self):
        self.plan['batches']=[b for b in self.plan['batches'] if b['mode']=='replay']
        self.report['rows']=[r for r in self.report['rows'] if r['mode']=='replay']
        rows=summarize(self.report,self.plan)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['mode'],'replay')
        self.assertEqual(rows[0]['speedup'],2)
