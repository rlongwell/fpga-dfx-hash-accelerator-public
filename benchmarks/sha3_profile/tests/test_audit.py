"""Reject altered claims even when a JSON document remains well-formed."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from benchmarks.sha3_profile.audit_results import audit_row, relative_source


class EvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = ROOT / "results/sha3-performance-20261115/compact-postboot-physical.json"
        cls.row = json.loads(report.read_text())["algorithms"]["sha3"][0]

    def test_recorded_samples_agree(self):
        audit_row(self.row, "sha3")

    def test_inflated_throughput_is_rejected(self):
        row = copy.deepcopy(self.row)
        row["summary"]["dma"]["MB_s"] *= 2
        with self.assertRaisesRegex(ValueError, "disagrees with raw samples"):
            audit_row(row, "sha3")

    def test_missing_samples_are_rejected(self):
        row = copy.deepcopy(self.row)
        row["samples"]["local_api"].pop()
        with self.assertRaisesRegex(ValueError, "repetitions"):
            audit_row(row, "sha3")

    def test_wrong_digest_is_rejected(self):
        row = copy.deepcopy(self.row)
        row["digest"] = "00" * 32
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            audit_row(row, "sha3")

    def test_source_mapping_cannot_escape_checkout(self):
        self.assertEqual(relative_source("/home/rl/workspace/fpga-dfx-hash-accelerator/rtl/rm/sha3.sv"),
                         Path("rtl/rm/sha3.sv"))
        with self.assertRaisesRegex(ValueError, "Invalid source path"):
            relative_source("../../outside")


if __name__ == "__main__":
    unittest.main()
