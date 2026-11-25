#!/bin/sh
# Foreground controls for the background hash service. Boot selects its DT/PL.
# Persistent LAN opt-in: /etc/default/zybo-hash (root-owned shell settings).
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
if [ -r /etc/default/zybo-hash ]; then
    . /etc/default/zybo-hash
fi
base=/opt/zybo/hash
service=$base/software/hash_service.py
pidfile=/run/zybo-hash.pid
logfile=/var/log/zybo-hash.log
lock=/run/zybo-hash.lock
mkdir -p /run /var/log
if ! mkdir "$lock" 2>/dev/null; then
    echo 'Another hash service operation is in progress.' >&2
    exit 1
fi
trap 'rmdir "$lock"' 0
trap 'exit 1' 1 2 15

running() {
    [ -s "$pidfile" ] || return 1
    read -r pid < "$pidfile"
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    kill -0 "$pid" 2>/dev/null || return 1
    [ -r "/proc/$pid/cmdline" ] || return 1
    tr '\000' '\n' < "/proc/$pid/cmdline" 2>/dev/null | grep -Fxq "$service"
}

start_service() {
    if [ -d /run/zybo-hash-net.lock ]; then
        echo 'A bounded FPGA Ethernet/replay run owns the accelerator.' >&2
        return 1
    fi
    model=$(tr -d '\000' < /proc/device-tree/model)
    if [ "$model" != 'Digilent Zybo Z7-20 DFX hash accelerator' ]; then
        echo "Hash profile is not selected by this boot: $model" >&2
        return 1
    fi
    if running; then
        echo "Hash service is already running (PID $pid)."
        return 0
    fi
    rm -f "$pidfile"
    modprobe hash_accel
    if [ ! -c /dev/hash-accel ]; then
        echo 'The matching hash driver did not create /dev/hash-accel.' >&2
        return 1
    fi
    /usr/bin/python3 "$service" --manifest "$base/dfx_manifest.json" \
        --listen "${HASH_LISTEN:-127.0.0.1}" \
        --receive-mode "${HASH_RECEIVE_MODE:-direct}" >> "$logfile" 2>&1 < /dev/null &
    echo "$!" > "$pidfile"
    sleep 1
    if running; then
        echo "Hash service started (PID $pid); log: $logfile"
    else
        rm -f "$pidfile"
        echo "Hash service failed to start; see $logfile" >&2
        return 1
    fi
}

stop_service() {
    if [ -d /run/zybo-hash-net.lock ]; then
        owner=''
        if [ -s /run/zybo-hash-net.lock/owner ]; then
            read -r owner < /run/zybo-hash-net.lock/owner
        fi
        if [ -z "$owner" ] || [ "$owner" != "${HASH_NET_OWNER:-}" ]; then
            echo 'An exclusive FPGA Ethernet/replay job owns the accelerator.' >&2
            return 1
        fi
    fi
    if running; then
        kill -TERM "$pid"
        waited=0
        while running && [ "$waited" -lt 10 ]; do
            sleep 1
            waited=$((waited + 1))
        done
        if running; then
            echo "Hash service did not stop (PID $pid); driver remains loaded." >&2
            return 1
        fi
    fi
    rm -f "$pidfile"
    if [ -d /sys/module/hash_accel ]; then
        modprobe -r hash_accel
    fi
}

case "${1:-start}" in
    start) start_service ;;
    stop) stop_service ;;
    restart) stop_service; start_service ;;
    status) if running; then echo "Hash service running (PID $pid)"; else echo 'Hash service stopped'; exit 1; fi ;;
    *) echo "Usage: $0 [start|stop|restart|status]" >&2; exit 2 ;;
esac
