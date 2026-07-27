#!/usr/bin/env bash
# Real PX4 SITL via official px4io image (SIH, headless, multi-arch).
#
# Do NOT map host UDP 14540 — MAVSDK must bind it. PX4 sends MAVLink to
# host.docker.internal:14540 (patched by the image entrypoint on Docker Desktop).
#
# Usage:
#   ./scripts/start-px4-sitl.sh          # start detached
#   ./scripts/start-px4-sitl.sh --fg     # foreground logs
#   ./scripts/start-px4-sitl.sh --stop
set -euo pipefail

NAME="${PX4_CONTAINER_NAME:-ais-px4-sitl}"
IMAGE="${PX4_IMAGE:-px4io/px4-sitl:latest}"
HOME_LAT="${PX4_HOME_LAT:-51.1694}"
HOME_LON="${PX4_HOME_LON:-71.4491}"
HOME_ALT="${PX4_HOME_ALT:-0}"

run_px4() {
  docker run "$@" \
    -e "PX4_HOME_LAT=${HOME_LAT}" \
    -e "PX4_HOME_LON=${HOME_LON}" \
    -e "PX4_HOME_ALT=${HOME_ALT}" \
    -p 14550:14550/udp \
    -p 14580:14580/udp \
    "$IMAGE"
}

stop_container() {
  docker rm -f "$NAME" 2>/dev/null || true
}

case "${1:-start}" in
  --stop|stop)
    stop_container
    echo "Stopped $NAME"
    exit 0
    ;;
  --fg|fg)
    stop_container
    exec run_px4 --rm --name "$NAME"
    ;;
  start|"")
    stop_container
    run_px4 -d --name "$NAME"
    echo "PX4 SITL started: $NAME ($IMAGE)"
    echo "  Home:         ${HOME_LAT}, ${HOME_LON} alt ${HOME_ALT}m (Astana training field)"
    echo "  QGC port:     UDP 14550"
    echo "  MAVSDK port:  UDP 14540 (host — do not docker-publish)"
    echo "  PX4 onboard:  UDP 14580 (mapped for client-init fallback)"
    echo ""
    echo "Verify MAVLink:"
    echo "  ./venv/bin/python scripts/mavlink_udp_probe.py --port 14540 --seconds 3"
    echo ""
    echo "After failed Initialize, restart SITL:"
    echo "  docker restart $NAME"
    ;;
  *)
    echo "Usage: $0 [start|--fg|--stop]"
    exit 1
    ;;
esac
