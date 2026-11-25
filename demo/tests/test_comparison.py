"""Boundary/recovery tests only; physical evidence comes from board jobs."""
from copy import deepcopy
from contextlib import nullcontext
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_agent
import server


class ComparisonEvidence(unittest.TestCase):
    def result(self):
        config=json.loads(server.VARIANTS.read_text())
        sample=dict(status='ok',algorithm='sha3',length=64,digest=hashlib.sha3_256(bytes(64)).hexdigest(),core_cycles=100,local_hash_ns=4000,backend='fpga-dma')
        return dict(sample,core='oxide',image=config['variants']['oxide']['image'],intermediate_algorithm_id=2,manager_load_ns=1000,repeats=7,warmup=sample.copy(),samples=[dict(sample,local_hash_ns=i*1000) for i in range(1,8)],minimum_hash_ns=1000,maximum_hash_ns=7000)

    def test_all_samples_and_identity_are_validated(self):
        result=self.result()
        self.assertTrue(server.validate_comparison(result,64,result['digest'])['verified'])
        for field in ['digest','backend']:
            bad=deepcopy(result);bad['samples'][5][field]='invalid'
            with self.subTest(field=field),self.assertRaises(RuntimeError):server.validate_comparison(bad,64,result['digest'])
        for field,value in [('local_hash_ns',5000),('intermediate_algorithm_id',1),('manager_load_ns',0),('repeats',1)]:
            with self.subTest(field=field),self.assertRaises(RuntimeError):server.validate_comparison(dict(result,**{field:value}),64,result['digest'])
        bad=deepcopy(result);bad['image']['sha256']='0'*64
        with self.assertRaises(RuntimeError):server.validate_comparison(bad,64,result['digest'])


class PayloadBoundaries(unittest.TestCase):
    def test_bounded_expansion_and_exact_checksum(self):
        data=bytes(range(256))*32
        with tempfile.TemporaryDirectory() as d,mock.patch.object(board_agent,'emit'):
            p=Path(d)/'zybo-demo-test.payload';p.write_bytes(gzip.compress(data))
            decoded=board_agent.prepare_payload(p,True,len(data),hashlib.sha256(data).hexdigest())
            self.assertEqual(decoded.read_bytes(),data);decoded.unlink()
            with self.assertRaises(ValueError):board_agent.prepare_payload(p,True,64,hashlib.sha256(data).hexdigest())
            self.assertFalse(decoded.exists())
            with self.assertRaises(ValueError):board_agent.prepare_payload(p,True,len(data),'0'*64)
            self.assertFalse(decoded.exists())

    def test_never_removes_existing_decode_destination(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'zybo-demo-test.payload';p.write_bytes(gzip.compress(b'abc'))
            target=p.with_suffix('.decoded');target.write_bytes(b'keep me')
            with self.assertRaises(FileExistsError):board_agent.prepare_payload(p,True,3,hashlib.sha256(b'abc').hexdigest())
            self.assertEqual(target.read_bytes(),b'keep me')


class ComparisonRecovery(unittest.TestCase):
    def exercise(self,hash_failure=False,restore_failure=False):
        cfg=json.loads(server.VARIANTS.read_text())
        base=json.loads(server.BOARD_MANIFEST.read_text())
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'dfx_manifest.json').write_text(json.dumps(base));cp=root/'variants.json';cp.write_text(json.dumps(cfg));p=root/'payload';p.write_bytes(b'abc')
            selects=[];state={'id':1,'count':0}
            hw=SimpleNamespace(manifest=deepcopy(base),info=lambda:(65536,state['id'],1048576,0))
            def select(algorithm):
                selects.append((algorithm,deepcopy(hw.manifest)))
                if algorithm=='sha256':
                    state['count']+=1
                    if restore_failure and state['count']==3:raise RuntimeError('injected restore failure')
                    state['id']=2
                else:state['id']=1
                return 1000
            hw.select=select
            hardware=mock.MagicMock();hardware.__enter__.return_value=hardware;hardware._hardware=hw
            hardware.hash_file.return_value={'digest':'ok','local_hash_ns':1000}
            hardware.hash_bytes.return_value={'digest':'empty','local_hash_ns':200}
            if hash_failure:hardware.hash_file.side_effect=RuntimeError('injected hash failure')
            with mock.patch.object(board_agent,'BASE',root),mock.patch.object(board_agent,'sha',return_value='checked'),mock.patch.object(board_agent,'emit'),mock.patch.object(board_agent,'probe',return_value={}),mock.patch.object(board_agent.subprocess,'run') as proc,mock.patch.dict(sys.modules,{'hash_local':SimpleNamespace(LocalHasher=lambda **_:hardware),'hash_service':SimpleNamespace(firmware_path=lambda _:p,control_lock=nullcontext)}):
                patched=deepcopy(cfg)
                for variant in patched['variants'].values():variant['image']['sha256']='checked'
                base['images']['sha3']['sha256']='checked';(root/'dfx_manifest.json').write_text(json.dumps(base));cp.write_text(json.dumps(patched))
                if hash_failure or restore_failure:
                    with self.assertRaises(RuntimeError):board_agent.run_comparison(p,cp)
                else:board_agent.run_comparison(p,cp)
                starts=[c for c in proc.call_args_list if c.args[0][-1]=='start']
                self.assertEqual(bool(starts),not restore_failure)
                if not restore_failure:
                    hardware.hash_bytes.assert_called_once_with(b'',algorithm='sha3',verify=True)
                    self.assertEqual(selects[-1][1]['images']['sha3'],base['images']['sha3'])
                else:hardware.hash_bytes.assert_not_called()
                return selects

    def test_switches_away_before_both_cores_and_restore(self):
        actions=self.exercise()
        self.assertEqual([x[0] for x in actions],['sha256','sha3']*3)
        self.assertNotEqual(actions[1][1]['images']['sha3']['filename'],actions[3][1]['images']['sha3']['filename'])

    def test_hash_failure_restores_original_manifest(self):self.exercise(hash_failure=True)
    def test_restore_failure_does_not_restart_misidentified_service(self):self.exercise(restore_failure=True)


if __name__=='__main__':unittest.main()
