#!/usr/bin/env bash
# PX4 SITL + Gazebo Harmonic с камерой (H.264 RTP → UDP 5600).
#
# Не пробрасывайте host UDP 14540 — его занимает MAVSDK.
#
# Usage:
#   ./scripts/start-px4-gazebo.sh          # detached
#   ./scripts/start-px4-gazebo.sh --fg
#   ./scripts/start-px4-gazebo.sh --stop
set -euo pipefail

NAME="${PX4_GAZEBO_CONTAINER:-ais-px4-gazebo}"
IMAGE="${PX4_GAZEBO_IMAGE:-px4io/px4-sitl-gazebo:latest}"
MODEL="${PX4_SIM_MODEL:-gz_x500_mono_cam}"
WORLD="${PX4_GZ_WORLD:-default}"
VIDEO_PORT="${VIDEO_UDP_PORT:-5600}"
HOME_LAT="${PX4_HOME_LAT:-51.1694}"
HOME_LON="${PX4_HOME_LON:-71.4491}"
HOME_ALT="${PX4_HOME_ALT:-0}"

run_gazebo() {
  docker run "$@" \
    -e HEADLESS=1 \
    -e "PX4_SIM_MODEL=${MODEL}" \
    -e "PX4_GZ_WORLD=${WORLD}" \
    -e "PX4_HOME_LAT=${HOME_LAT}" \
    -e "PX4_HOME_LON=${HOME_LON}" \
    -e "PX4_HOME_ALT=${HOME_ALT}" \
    -p 14550:14550/udp \
    -p 14580:14580/udp \
    -p "${VIDEO_PORT}:${VIDEO_PORT}/udp" \
    "$IMAGE"
}

stop_container() {
  docker rm -f "$NAME" 2>/dev/null || true
}

case "${1:-start}" in
  --stop|stop)
    stop_container
    echo "Остановлен $NAME"
    exit 0
    ;;
  --fg|fg)
    stop_container
    exec run_gazebo --rm --name "$NAME"
    ;;
  start|"")
    stop_container
    echo "Загрузка образа ${IMAGE} (≈650 MB при первом запуске)..."
    docker pull "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE"
    run_gazebo -d --name "$NAME"
    echo "Gazebo SITL: $NAME"
    echo "  Модель:       ${MODEL} (камера → UDP ${VIDEO_PORT} H.264/RTP)"
    echo "  Дом:          ${HOME_LAT}, ${HOME_LON} alt ${HOME_ALT} m"
    echo "  MAVLink:      14550 (QGC), 14580 onboard, 14540 — host/MAVSDK"
    echo "  Видео:        udp://127.0.0.1:${VIDEO_PORT} → /api/video/mjpeg"
    echo ""
    echo "Требуется GStreamer на Mac: brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-libav"
    echo "После Initialize: откройте dashboard — блок «Видеопоток» покажет камеру Gazebo."
    ;;
  *)
    echo "Usage: $0 [start|--fg|--stop]"
    exit 1
    ;;
esac
