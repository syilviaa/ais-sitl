#!/usr/bin/env bash
# Остановить другие PX4/SITL контейнеры (конфликт UDP 14550/14580).
set -euo pipefail

KEEP="${1:-}"

for c in ais-px4-sitl ais-px4-gazebo epic_sammet; do
  if [[ -n "$KEEP" && "$c" == "$KEEP" ]]; then
    continue
  fi
  if docker ps -a --format '{{.Names}}' | grep -qx "$c"; then
    echo "Останавливаю $c (освобождаю порты 14550/14580)..."
    docker rm -f "$c" >/dev/null 2>&1 || true
  fi
done
