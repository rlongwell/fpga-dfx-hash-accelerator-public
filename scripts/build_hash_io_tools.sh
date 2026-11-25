#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out="$root/build/gem-direct"
mkdir -p "$out"
"${CC:-cc}" -O2 -Wall -Wextra -Werror -o "$out/gem_send" "$root/software/net/gem_send.c"
arm_cc=${ARM_CC:-"$root/../zybo-z7-20-inmp441-je/build/wifi/userspace/host/bin/arm-linux-gcc"}
if [[ ! -x "$arm_cc" ]]; then
    echo 'Set ARM_CC to the ARM compiler from the matching board Buildroot toolchain.' >&2
    exit 1
fi
"$arm_cc" -O2 -Wall -Wextra -Werror -o "$out/gem_board" "$root/software/net/gem_board.c"
