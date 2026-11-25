#!/usr/bin/env python3
"""Reject a successful test record if any recorded source changed during the run."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("operation", choices=("begin", "finish"))
args = parser.parse_args()
paths = sorted(p for directory in ("rtl", "sim", "software", "scripts", "reference", "benchmarks")
               for p in (root / directory).rglob("*")
               if p.is_file() and "__pycache__" not in p.parts)
paths += [root / "test.sh", root / "build.sh"]
sources = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
snapshot = root / "build/verification/start_sources.json"
if args.operation == "begin":
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps(sources, indent=2) + "\n")
else:
    original = json.loads(snapshot.read_text())
    if original != sources:
        changed = [name for name in sorted(set(original) | set(sources))
                   if original.get(name) != sources.get(name)]
        raise SystemExit("Sources changed during verification; rerun after edits stop: " + ", ".join(changed))
    evidence = root / "results/verification_logs"
    evidence.mkdir(parents=True, exist_ok=True)
    names = ["baseline", "digest-variant", "oxide-adapter", "static", "gem-ingress", "software",
             "evidence-tests", "evidence-audit"]
    names += [f"engine-{name}" for name in ("sha3", "sha256", "blake2s", "sha3_wide", "sha3_serial", "sha3_fast", "sha3_compact")]
    names += [f"integration-{name}" for name in ("sha3", "sha256", "blake2s", "sha3_fast", "sha3_compact")]
    logs = {}
    for name in names:
        destination = evidence / f"{name}.log"
        shutil.copyfile(root / "build/verification" / destination.name, destination)
        logs[str(destination.relative_to(root))] = hashlib.sha256(destination.read_bytes()).hexdigest()
    result = {
        "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "result": "PASS", "sources_unchanged_during_run": True,
        "verilator": subprocess.check_output(["verilator", "--version"], text=True).strip(),
        "checks": ["Oxide baseline: both buffer modes, continuous and gapped input",
                   "Oxide no-digest variant: same test matrix",
                   "Elastic comparison adapter: independent SHA3 engine vectors and framing/reset checks",
                   "Static shell: AXI Lite, DMA framing, backpressure, errors, abort/reset/isolation",
                   "GEM ingress and BRAM replay: descriptor/ring protocol, malformed packets, stalls, replay wrap and independent AXI completion across hash abort; simulation only",
                   "Seven RTL engines: hashlib vectors, stalls, digest backpressure, protocol/reset",
                   "Five integrated shell + RTL engines: hashlib vectors, randomized DMA splits, abort/error/isolation/reset with recovery hashes",
                   "Software: TCP service/client, bounded memory, error recovery, C/Python UAPI, mocked production ioctl/manifest checks and client benchmark harness",
                   "Retained physical evidence: checksums, pinned source/license hashes, raw-sample statistics, resource reports and manifest identities; not a new board run"],
        "hardware_tested": False, "source_sha256": sources, "log_sha256": logs,
    }
    (root / "results/verification.json").write_text(json.dumps(result, indent=2) + "\n")
