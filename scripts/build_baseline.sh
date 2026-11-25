#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
result_prefix="${1:-baseline}"
case "$result_prefix" in
    baseline) core_source="$project_root/reference/oxide/hdl/ip/vhd/sha3/sha3_256.vhd" ;;
    oxide_no_digest) core_source="$project_root/rtl/sha3/oxide_no_digest/sha3_256.vhd" ;;
    *) echo "Unknown core selection: $result_prefix" >&2; exit 2 ;;
esac
vivado_bin="${VIVADO:-${VIVADO_BIN:-/opt/amd/xilinx/Vivado/2024.2/bin/vivado}}"
if [[ ! -x "$vivado_bin" ]]; then
    echo "Vivado executable missing: $vivado_bin; set VIVADO_BIN." >&2
    exit 1
fi
(cd "$project_root/reference/oxide" && sha256sum --check SHA256SUMS)
mkdir -p "$project_root/results"
for buffering in false true; do
    run_dir="$project_root/build/vivado/${result_prefix}_db_$buffering"
    mkdir -p "$run_dir"
    echo "Implementing $result_prefix, DOUBLE_BUFFER=$buffering, 100 MHz"
    (
        cd "$run_dir"
        "$vivado_bin" -mode batch -nojournal -log vivado.log \
            -source "$project_root/scripts/vivado/baseline.tcl" -tclargs "$project_root" "$buffering" "$core_source" > console.log 2>&1
    ) || { tail -50 "$run_dir/console.log"; exit 1; }
    if rg -q '^(ERROR|CRITICAL WARNING):' "$run_dir/console.log"; then
        rg '^(ERROR|CRITICAL WARNING):' "$run_dir/console.log" >&2
        exit 1
    fi
    for report in synthesis_utilization synthesis_timing routed_utilization routed_timing routed_register_timing routed_drc route_status; do
        cp "$run_dir/$report.rpt" "$project_root/results/${result_prefix}_db_${buffering}_${report}.rpt"
    done
    cp "$run_dir/summary.tsv" "$project_root/results/${result_prefix}_db_${buffering}_summary.tsv"
done
python3 "$project_root/sim/baseline/summarize_implementation.py" "$project_root" "$result_prefix" "$core_source"
