#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
test_build="$project_root/build/sim/static"
mkdir -p "$test_build"
verilator --cc --exe --build -j 2 --Wall --top-module hash_shell \
  --Mdir "$test_build" "$project_root/rtl/static/hash_shell.sv" \
  "$project_root/sim/static/shell_test.cpp" > "$test_build/build.log" 2>&1
"$test_build/Vhash_shell" | tee "$test_build/test.log"
