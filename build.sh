#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-system}" in
  system) exec "$project_root/scripts/build_system.sh" "${2:-all}" ;;
  sha3-variant) exec bash "$project_root/scripts/build_sha3_variant.sh" "${2:-compact}" ;;
  baseline) exec "$project_root/scripts/build_baseline.sh" ;;
  digest-variant) exec "$project_root/scripts/build_digest_variant.sh" ;;
  engines) shift; exec "$project_root/scripts/build_engines.sh" "$@" ;;
  driver) shift; exec "$project_root/scripts/build_driver.sh" "$@" ;;
  embedded) shift; exec "$project_root/scripts/build_embedded.sh" "$@" ;;
  *) echo 'Usage: ./build.sh [system [bd|ip|synth|dfx|all]|sha3-variant [fast|compact|oxide]|baseline|digest-variant|engines [names...]|driver [make args...]|embedded [stage]]' >&2; exit 2 ;;
esac
