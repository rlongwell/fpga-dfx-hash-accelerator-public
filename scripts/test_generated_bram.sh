#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
vivado=${VIVADO_HOME:-/opt/amd/xilinx/Vivado/2024.2}
netlist=${1:-"$root/build/gem-direct/system/project/system.gen/sources_1/bd/ps_dma/ip/ps_dma_net_memory_0/ps_dma_net_memory_0_sim_netlist.vhdl"}
out=${2:-"$root/build/sim/generated-bram"}
defines=()
[[ ${3:-64} != 32 ]] || defines=(-d LEGACY_BRAM_A32)
netlist=$(realpath "$netlist")
mkdir -p "$out"
cd "$out"
"$vivado/bin/xvhdl" "$netlist" > compile.log 2>&1
"$vivado/bin/xvlog" --sv "${defines[@]}" "$root/sim/net/bram_lane_test.sv" >> compile.log 2>&1
"$vivado/bin/xvlog" "$vivado/data/verilog/src/glbl.v" >> compile.log 2>&1
"$vivado/bin/xelab" bram_lane_test glbl -L unisims_ver -L unimacro_ver -L secureip \
    --snapshot bram_lanes -timescale 1ns/1ps > elaborate.log 2>&1
"$vivado/bin/xsim" bram_lanes --runall > run.log 2>&1
cat run.log
grep -q '^GENERATED_BRAM_LANES_PASS ' run.log
