#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
kernel_build="${KERNEL_BUILD:-/lib/modules/$(uname -r)/build}"
module_build="$project_root/build/linux-driver"
mkdir -p "$module_build"
cp "$project_root/software/linux/"{hash_accel.c,hash_accel.h,Makefile} "$module_build/"
make -C "$kernel_build" M="$module_build" modules "$@"
