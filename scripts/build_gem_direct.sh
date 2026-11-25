#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
vivado=${VIVADO:-/opt/amd/xilinx/Vivado/2024.2/bin/vivado}
mkdir -p "$root/build/gem-direct"
cd "$root"
case "${1:-all}" in
    reimplement-oxide|reimplement-sha256|reimplement-blake2s)
        exec "$vivado" -mode batch -nojournal -notrace -log "build/gem-direct/$1.vivado.log" \
            -source scripts/vivado/gem_reimplement.tcl -tclargs "$root" "${1#reimplement-}" "${GEM_PLACE_DIRECTIVE:-ExtraTimingOpt}"
        ;;
    postroute-oxide|postroute-sha256|postroute-blake2s)
        exec "$vivado" -mode batch -nojournal -notrace -log "build/gem-direct/$1.vivado.log" \
            -source scripts/vivado/gem_postroute.tcl -tclargs "$root" "${1#postroute-}" "${GEM_PHYSOPT_DIRECTIVE:-Explore}"
        ;;
    publish)
        exec "$vivado" -mode batch -nojournal -notrace -log build/gem-direct/publish.vivado.log \
            -source scripts/vivado/gem_publish.tcl -tclargs "$root"
        ;;
    oxide-fanout|finish)
        flow=gem_finish
        [[ "$1" != oxide-fanout ]] || flow=gem_oxide_fanout
        exec "$vivado" -mode batch -nojournal -notrace -log "build/gem-direct/$flow.vivado.log" \
            -source "scripts/vivado/$flow.tcl" -tclargs "$root"
        ;;
    all) ;;
    *) echo 'Usage: build_gem_direct.sh [all|oxide-fanout|finish|postroute-{oxide,sha256,blake2s}|reimplement-{oxide,sha256,blake2s}|publish]' >&2; exit 2 ;;
esac
for stage in bd ip synth; do
    "$vivado" -mode batch -nojournal -notrace -log "build/gem-direct/$stage.vivado.log" \
        -source scripts/vivado/net_system.tcl -tclargs "$root" "$stage"
done
"$vivado" -mode batch -nojournal -notrace -log build/gem-direct/implementation.vivado.log \
    -source scripts/vivado/net_implement.tcl -tclargs "$root"
