#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
algorithm="${1:-sha3}"
case "$algorithm" in
  sha3|sha256|blake2s) source="$project_root/rtl/$algorithm/hash_$algorithm.sv"; reference="$algorithm" ;;
  sha3_fast|sha3_compact) source="$project_root/rtl/sha3/experiments/hash_$algorithm.sv"; reference=sha3 ;;
  *) echo 'Expected sha3, sha256, blake2s, sha3_fast or sha3_compact' >&2; exit 2 ;;
esac
test_build="$project_root/build/sim/integration-$algorithm"
mkdir -p "$test_build"
python3 "$project_root/sim/engines/generate_vectors.py" --algorithm "$reference" --output "$test_build/vectors.txt"
verilator --cc --exe --build -j 2 --Wall -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL \
  --top-module hash_integration -CFLAGS -DREAL_ENGINE --Mdir "$test_build/obj" \
  "$project_root/sim/static/hash_integration.sv" "$project_root/rtl/static/hash_shell.sv" \
  "$project_root/rtl/common/axis_bytes.sv" "$source" \
  "$project_root/rtl/rm/$algorithm.sv" "$project_root/sim/static/shell_test.cpp" \
  > "$test_build/build.log" 2>&1
"$test_build/obj/Vhash_integration" "$test_build/vectors.txt" | tee "$test_build/test.log"
