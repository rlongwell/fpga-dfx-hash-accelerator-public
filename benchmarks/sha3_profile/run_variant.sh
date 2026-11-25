#!/bin/sh
# Shared-SD board runner: always restore the known-good production manifest.
set -eu
restore() {
    PYTHONPATH=/opt/zybo/hash/software python3 -c 'from hash_service import Hardware; from pathlib import Path; h=Hardware(Path("/dev/hash-accel"),Path("/opt/zybo/hash/dfx_manifest.json")); h.select("sha256"); h.select("sha3"); h.close()'
    /opt/zybo/hash/start.sh start
}
/opt/zybo/hash/start.sh stop
modprobe hash_accel
trap restore 0
python3 /root/sha3-profile-20261115-v2.py "$@"
