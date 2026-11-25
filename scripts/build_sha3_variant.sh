#!/usr/bin/env bash
# Targeted RM build; keeps the existing accepted static and boot artifacts.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
variant="${1:-compact}"
case "$variant" in
  fast|compact) "$root/scripts/test_engines.sh" "sha3_$variant"; "$root/scripts/test_integration.sh" "sha3_$variant" ;;
  oxide)
    "$root/scripts/test_baseline.sh"
    if [[ "${OXIDE_ELASTIC:-0}" == 1 ]]; then bash "$root/scripts/test_oxide_adapter.sh"; fi
    ;;
  *) echo 'Usage: build_sha3_variant.sh fast|compact|oxide' >&2; exit 2 ;;
esac
python3 "$root/scripts/vivado/system_manifest.py" verify "$root"
(cd "$root/reference/oxide" && sha256sum --check SHA256SUMS)
flow="$root/scripts/vivado/sha3_variant.tcl"
build_name="$variant"
if [[ "$variant" == compact ]]; then flow="$root/scripts/vivado/sha3_variant_compact.tcl"; fi
if [[ "$variant" == compact && "${COMPACT_SPREAD:-0}" == 1 ]]; then
  flow="$root/scripts/vivado/sha3_compact_spread.tcl"
  build_name=compact-spread
fi
if [[ "$variant" == oxide && "${OXIDE_SPREAD:-0}" == 1 ]]; then
  flow="$root/scripts/vivado/sha3_variant_spread.tcl"
  build_name=oxide-spread
fi
export_name="$variant"
if [[ "$variant" == oxide && "${OXIDE_ELASTIC:-0}" == 1 ]]; then
  flow="$root/scripts/vivado/sha3_oxide_elastic.tcl"
  export_name=oxide_elastic
  build_name=oxide-elastic
  case "${OXIDE_ELASTIC_PLACE:-high}" in
    high) ;;
    medium)
      flow="$root/scripts/vivado/sha3_oxide_elastic_medium.tcl"
      build_name=oxide-elastic-medium
      ;;
    *) echo 'OXIDE_ELASTIC_PLACE must be high or medium' >&2; exit 2 ;;
  esac
fi
if [[ "${OXIDE_ELASTIC_POSTROUTE:-0}" == 1 && "$build_name" != oxide-elastic-medium ]]; then
  echo 'Post-route recovery requires OXIDE_ELASTIC=1 OXIDE_ELASTIC_PLACE=medium' >&2
  exit 2
fi
out="$root/build/sha3-profile/$build_name"
mkdir -p "$out"
cd "$out"
# Invalidate only this flow's publication before attempting a new implementation.
rm -f full.bit full_pblock_hash_partial.bit full_pblock_hash_partial.bit.bin routed.dcp
implementation_status=0
"${VIVADO:-/opt/amd/xilinx/Vivado/2024.2/bin/vivado}" -mode batch -nojournal \
  -source "$flow" -tclargs "$root" "$variant" > console.log 2>&1 || implementation_status=$?
if [[ "${OXIDE_ELASTIC_POSTROUTE:-0}" == 1 ]]; then
  # The first route may miss timing. Retain its reports, then optimize only
  # that completed, source-verified route; all gates run again before export.
  test -f routed.dcp
  sha256sum --check sources.sha256
  optimized="$out-physopt"
  mkdir -p "$optimized"
  cp synth_utilization.rpt "$optimized/"
  out="$optimized"
  cd "$out"
  rm -f full.bit full_pblock_hash_partial.bit full_pblock_hash_partial.bit.bin routed.dcp
  "${VIVADO:-/opt/amd/xilinx/Vivado/2024.2/bin/vivado}" -mode batch -nojournal \
    -source "$root/scripts/vivado/sha3_oxide_elastic_postroute.tcl" \
    -tclargs "$root" "$variant" > console.log 2>&1
elif [[ "$implementation_status" != 0 ]]; then
  exit "$implementation_status"
fi
python3 "$root/benchmarks/sha3_profile/export_variant.py" "$export_name" --build "$out"
