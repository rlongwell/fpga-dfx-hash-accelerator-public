#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
vivado="${VIVADO:-/opt/amd/xilinx/Vivado/2024.2/bin/vivado}"
mkdir -p "$root/build"
if (($#==0)); then set -- sha3 sha256 blake2s sha3_wide sha3_serial sha3_fast sha3_compact; fi
for engine in "$@"; do
  case "$engine" in sha3|sha256|blake2s|sha3_wide|sha3_serial|sha3_fast|sha3_compact) ;; *) echo "Unknown engine: $engine" >&2; exit 2;; esac
  python3 "$root/benchmarks/engine_results.py" --capture "$engine"
  "$root/scripts/test_engines.sh" "$engine" > "$root/build/${engine}_pre_synthesis_test.log"
  out="$root/build/engines/$engine"
  results="$root/results/engines/$engine"
  mkdir -p "$out" "$results"
  (
    cd "$out"
    "$vivado" -mode batch -nojournal -log vivado.log -source "$root/scripts/vivado/engine.tcl" \
      -tclargs "$root" "$engine" > stdout.log 2>&1 || { tail -n 60 stdout.log >&2; exit 1; }
  )
  cp "$out/summary.tsv" "$out/routed_utilization.rpt" "$out/routed_timing.rpt" \
     "$out/routed_register_timing.rpt" "$out/route_status.rpt" "$out/routed_drc.rpt" \
     "$out/synthesis_utilization.rpt" "$out/synthesis_timing.rpt" \
     "$out/congestion.rpt" "$out/sources_sha256.json" "$results/"
  cp "$root/build/sim/$engine/results.log" "$results/simulation.log"
  echo "Measured $engine: $results/summary.tsv"
done
python3 "$root/benchmarks/engine_results.py"
