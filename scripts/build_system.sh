#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
stage=${1:-all}
case "$stage" in bd|ip|synth|dfx|all) ;; *) echo "Usage: $0 [bd|ip|synth|dfx|all]" >&2; exit 2;; esac
vivado=${VIVADO:-/opt/amd/xilinx/Vivado/2024.2/bin/vivado}
if [[ ! -x "$vivado" ]]; then
    vivado=$(command -v vivado || true)
fi
if [[ -z "$vivado" ]]; then echo "Vivado 2024.2 is required; set VIVADO to its executable." >&2; exit 1; fi
mkdir -p "$repo_root/build/logs" "$repo_root/build/vivado"
cd "$repo_root/build/vivado"
run_system_stage() {
    "$vivado" -mode batch -nojournal -log "$repo_root/build/logs/system_$1.vivado.log" \
        -notrace -source "$repo_root/scripts/vivado/system.tcl" -tclargs "$repo_root" "$1" \
        2>&1 | tee "$repo_root/build/logs/system_$1.log"
}
run_dfx() {
    "$vivado" -mode batch -nojournal -log "$repo_root/build/logs/dfx.vivado.log" \
        -notrace -source "$repo_root/scripts/vivado/dfx.tcl" -tclargs "$repo_root" \
        2>&1 | tee "$repo_root/build/logs/dfx.log"
}
if [[ "$stage" == all ]]; then
    run_system_stage bd
    run_system_stage ip
    run_system_stage synth
    run_dfx
elif [[ "$stage" == dfx ]]; then
    run_dfx
else
    run_system_stage "$stage"
fi
