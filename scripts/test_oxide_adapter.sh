#!/usr/bin/env bash
# Check the elastic byte adapter with an independently verified SHA3 engine.
# The unchanged Oxide VHDL core is separately checked by test_baseline.sh.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
out="$root/build/sim/oxide-elastic-adapter"
mkdir -p "$out"
python3 "$root/sim/engines/generate_vectors.py" --algorithm sha3 --output "$out/vectors.txt"
verilator --cc --exe --build -j 2 --top-module hash_rm --Mdir "$out/obj" \
  -Wall -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL \
  "$root/rtl/sha3/oxide_compare/axis_bytes_elastic.sv" \
  "$root/rtl/sha3/hash_sha3.sv" "$root/rtl/rm/sha3.sv" \
  "$root/sim/engines/test_engine.cpp" > "$out/compile.log" 2>&1
"$out/obj/Vhash_rm" "$out/vectors.txt" 1 | tee "$out/results.log"
