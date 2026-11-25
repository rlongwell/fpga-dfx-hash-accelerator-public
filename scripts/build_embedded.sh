#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${EMBEDDED_PYTHON:-/usr/bin/python3}" -I "$project_root/software/embedded/build.py" "$@"
