#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
algorithm="${1:-sha3}"
case "$algorithm" in
  sha3) id=1; source="$root/rtl/sha3/hash_sha3.sv" ;;
  sha3_wide|sha3_serial|sha3_fast|sha3_compact) id=1; source="$root/rtl/sha3/experiments/hash_${algorithm}.sv" ;;
  sha256) id=2; source="$root/rtl/sha256/hash_sha256.sv" ;;
  blake2s) id=3; source="$root/rtl/blake2s/hash_blake2s.sv" ;;
  *) echo "Usage: $0 [sha3|sha256|blake2s|sha3_wide|sha3_serial|sha3_fast|sha3_compact]" >&2; exit 2 ;;
esac
out="$root/build/sim/$algorithm"
mkdir -p "$out"
reference="$algorithm"
[[ "$algorithm" == sha3_* ]] && reference=sha3
python3 "$root/sim/engines/generate_vectors.py" --algorithm "$reference" --output "$out/vectors.txt"
verilator --cc --exe --build -j 4 --top-module hash_rm --Mdir "$out/obj" \
  -Wall -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL \
  "$root/rtl/common/axis_bytes.sv" "$source" "$root/rtl/rm/$algorithm.sv" \
  "$root/sim/engines/test_engine.cpp" > "$out/compile.log" 2>&1 || {
    cat "$out/compile.log" >&2; exit 1;
  }
"$out/obj/Vhash_rm" "$out/vectors.txt" "$id" | tee "$out/results.log"
