#!/usr/bin/env bash
# GStreamer для ретрансляции камеры Gazebo (H.264 UDP → MJPEG в браузере).
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Ubuntu: sudo apt install gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav"
  exit 0
fi
if command -v gst-launch-1.0 >/dev/null; then
  echo "GStreamer уже установлен: $(which gst-launch-1.0)"
  exit 0
fi
echo "Установка GStreamer через Homebrew..."
brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-libav
echo "Готово: $(which gst-launch-1.0)"
