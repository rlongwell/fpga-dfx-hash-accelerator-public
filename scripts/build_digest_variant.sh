#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/.." && pwd)"
"$script_dir/build_baseline.sh" oxide_no_digest
python3 "$project_root/sim/baseline/compare_digest_variant.py" "$project_root"
