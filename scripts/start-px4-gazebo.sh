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
# UDP видео идёт на host.docker.internal:5600 напрямую — не публикуем 5600,
# иначе Docker Desktop на Mac держит порт и gst-launch не может bind.
HOME_LAT="${PX4_HOME_LAT:-51.1694}"
HOME_LON="${PX4_HOME_LON:-71.4491}"
HOME_ALT="${PX4_HOME_ALT:-0}"
# Docker on macOS has no GPU, so the camera sensor is software-rendered. At the
# stock 1280x960@30 that drags Gazebo down to ~0.1x real time, which starves
# PX4's MAVLink heartbeat and trips the data-link failsafe mid-flight.
CAM_WIDTH="${PX4_CAM_WIDTH:-640}"
CAM_HEIGHT="${PX4_CAM_HEIGHT:-480}"
CAM_FPS="${PX4_CAM_FPS:-10}"
CAM_SDF="/opt/px4-gazebo/share/gz/models/mono_cam/model.sdf"

# Rewrite the camera sensor before Gazebo reads it: create the container,
# patch the model, then start it.
patch_camera() {
  local workdir
  workdir="$(mktemp -d)"
  if ! docker cp "${NAME}:${CAM_SDF}" "${workdir}/model.sdf" 2>/dev/null; then
    rm -rf "${workdir}"
    echo "  Камера:       не удалось патчить SDF, остаётся 1280x960@30" >&2
    return 0
  fi
  perl -0pi -e "
    s|<width>\\d+</width>|<width>${CAM_WIDTH}</width>|;
    s|<height>\\d+</height>|<height>${CAM_HEIGHT}</height>|;
    s|<update_rate>\\d+</update_rate>|<update_rate>${CAM_FPS}</update_rate>|;
  " "${workdir}/model.sdf"
  docker cp "${workdir}/model.sdf" "${NAME}:${CAM_SDF}"
  rm -rf "${workdir}"
}

create_gazebo() {
  docker create --name "$NAME" \
    --add-host=host.docker.internal:host-gateway \
    -e HEADLESS=1 \
    -e "PX4_SIM_MODEL=${MODEL}" \
    -e "PX4_GZ_WORLD=${WORLD}" \
    -e "PX4_HOME_LAT=${HOME_LAT}" \
    -e "PX4_HOME_LON=${HOME_LON}" \
    -e "PX4_HOME_ALT=${HOME_ALT}" \
    -e "PX4_VIDEO_HOST_IP=host.docker.internal" \
    -p 14550:14550/udp \
    -p 14580:14580/udp \
    "$IMAGE" >/dev/null
}

stop_container() {
  docker rm -f "$NAME" 2>/dev/null || true
}

stop_conflicts() {
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  # shellcheck source=scripts/stop-other-sitl.sh
  source "$ROOT/scripts/stop-other-sitl.sh" "$NAME"
}

case "${1:-start}" in
  --stop|stop)
    stop_container
    echo "Остановлен $NAME"
    exit 0
    ;;
  --fg|fg)
    stop_conflicts
    stop_container
    create_gazebo
    patch_camera
    exec docker start -a "$NAME"
    ;;
  start|"")
    stop_conflicts
    stop_container
    echo "Загрузка образа ${IMAGE} (≈650 MB при первом запуске)..."
    docker pull "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE"
    create_gazebo
    patch_camera
    docker start "$NAME" >/dev/null
    echo "Gazebo SITL: $NAME"
    echo "  Модель:       ${MODEL} (камера → UDP ${VIDEO_PORT} H.264/RTP)"
    echo "  Камера:       ${CAM_WIDTH}x${CAM_HEIGHT}@${CAM_FPS} (софт-рендер без GPU)"
    echo "                PX4_CAM_WIDTH/HEIGHT/FPS меняют разрешение"
    echo "  Мир:          ${WORLD}"
    if [[ "${WORLD}" == "default" ]]; then
      echo "                (пустая площадка — зато симуляция идёт ~0.76x реального времени)"
      echo "                PX4_GZ_WORLD=lawn|forest|ridge ./scripts/start-px4-gazebo.sh"
      echo "                картинка красивее, но lawn роняет скорость симуляции до ~0.36x,"
      echo "                а на медленной симуляции PX4 срывается в RTL по потере связи"
    fi
    echo "  Дом:          ${HOME_LAT}, ${HOME_LON} alt ${HOME_ALT} m"
    echo "  MAVLink:      14550 (QGC), 14580 onboard, 14540 — host/MAVSDK"
    echo "  Видео:        udp://127.0.0.1:${VIDEO_PORT} → /api/video/mjpeg"
    echo "  Видео Docker: PX4_VIDEO_HOST_IP=host.docker.internal (поток на Mac, не в контейнер)"
    if command -v gst-launch-1.0 >/dev/null; then
      echo "  GStreamer:    OK ($(command -v gst-launch-1.0))"
    else
      echo "  GStreamer:    НЕ НАЙДЕН — ./scripts/install-gstreamer.sh"
    fi
    echo ""
    echo "Дальше:"
    echo "  1. ./scripts/start-backend.sh          (перезапустите, если ставили GStreamer недавно)"
    echo "  2. Dashboard → «Подключить SITL»"
    echo "  3. Проверка: curl http://127.0.0.1:5001/api/video/status"
    ;;
  *)
    echo "Usage: $0 [start|--fg|--stop]"
    exit 1
    ;;
esac
