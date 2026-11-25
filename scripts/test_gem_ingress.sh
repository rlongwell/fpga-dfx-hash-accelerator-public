#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out="$root/build/sim/gem-ingress"
mkdir -p "$out"
verilator --cc --exe --build -j 2 --Wall --top-module gem_ingress \
  --Mdir "$out" "$root/rtl/net/gem_ingress.sv" "$root/sim/net/ingress_test.cpp" \
  > "$out/build.log" 2>&1
"$out/Vgem_ingress" | tee "$out/test.log"
