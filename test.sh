#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"
mkdir -p build/verification
rm -f results/verification.json
python3 scripts/verification_record.py begin
scripts/test_baseline.sh > build/verification/baseline.log 2>&1
scripts/test_digest_variant.sh > build/verification/digest-variant.log 2>&1
scripts/test_oxide_adapter.sh > build/verification/oxide-adapter.log 2>&1
scripts/test_static.sh | tee build/verification/static.log
scripts/test_gem_ingress.sh | tee build/verification/gem-ingress.log
for algorithm in sha3 sha256 blake2s sha3_wide sha3_serial sha3_fast sha3_compact; do
    scripts/test_engines.sh "$algorithm" > "build/verification/engine-$algorithm.log" 2>&1
    tail -n 1 "build/verification/engine-$algorithm.log"
done
for algorithm in sha3 sha256 blake2s sha3_fast sha3_compact; do
    scripts/test_integration.sh "$algorithm" | tee "build/verification/integration-$algorithm.log"
done
scripts/test_software.sh 2>&1 | tee build/verification/software.log
python3 -m unittest discover -s benchmarks/sha3_profile/tests -v > build/verification/evidence-tests.log 2>&1
python3 benchmarks/sha3_profile/audit_results.py | tee build/verification/evidence-audit.log
python3 scripts/verification_record.py finish
echo 'All offline verification passed. See results/verification.json.'
