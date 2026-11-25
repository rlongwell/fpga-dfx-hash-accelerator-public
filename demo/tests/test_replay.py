"""Reject unverified physical sweep evidence, using a retained hardware batch."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'demo'))
from replay import validate_batch

class PhysicalReplayEvidence(unittest.TestCase):
    def setUp(self):
        source=ROOT/'results/gem-direct-20261116/sweep-64B-1GiB'
        self.plan=json.loads((source/'plan.json').read_text())
        self.batch=json.loads((source/'batch-00-attempt-1.json').read_text())
        self.variants=json.loads((ROOT/'demo/core_variants.json').read_text())
    def test_accepts_retained_physical_batch(self):
        rows=validate_batch(self.batch,self.plan,0,self.variants)
        self.assertEqual(len(rows),25)
        self.assertTrue(all(r['verified'] for r in rows))
    def test_rejects_identity_recovery_digest_and_timer_corruption(self):
        edits=[lambda b:b.update(partial_sha256='wrong'),
               lambda b:b['recovery'].update(verified=False),
               lambda b:b.update(partial_load_ns=0),
               lambda b:b['rows'][0]['events'][-1].update(digest='wrong'),
               lambda b:b['rows'][0]['events'][-1].update(core_cycles=0)]
        for edit in edits:
            changed=deepcopy(self.batch);edit(changed)
            with self.assertRaises(ValueError):validate_batch(changed,self.plan,0,self.variants)

class SavedReplayJobs(unittest.TestCase):
    def test_completed_job_survives_dashboard_restart(self):
        import tempfile
        from unittest.mock import patch
        import server
        with tempfile.TemporaryDirectory() as folder, patch.object(server,'OUTPUT',Path(folder)):
            ident='1'*24
            saved={'id':ident,'kind':'replay','state':'passed','fixture':True}
            (Path(folder)/(ident+'.json')).write_text(json.dumps(saved))
            self.assertEqual(server.State().get_job(ident),saved)
    def test_invalid_path_and_incomplete_job_are_rejected(self):
        import tempfile
        from unittest.mock import patch
        import server
        with tempfile.TemporaryDirectory() as folder, patch.object(server,'OUTPUT',Path(folder)):
            state=server.State()
            with self.assertRaises(KeyError):state.get_job('../secret')
            ident='2'*24
            (Path(folder)/(ident+'.json')).write_text(json.dumps({'id':ident,'state':'running'}))
            with self.assertRaises(ValueError):state.get_job(ident)
