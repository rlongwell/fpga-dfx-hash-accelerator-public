#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "The dashboard requires Python 3.11 or newer.")'
# Standard-library-only application: no packages or system Python changes.
exec python3 "$project_root/demo/server.py" "$@"
