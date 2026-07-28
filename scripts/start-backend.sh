#!/usr/bin/env bash
# Start AIS SITL backend (Python 3.11 recommended)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

if [[ ! -d venv ]] || [[ ! -f venv/bin/python ]]; then
  chmod +x scripts/setup-dev.sh
  ./scripts/setup-dev.sh
fi

# macOS: AirPlay Receiver binds :5000 — use 5001 unless PORT is set
if [[ -z "${PORT:-}" ]] && [[ "$(uname -s)" == "Darwin" ]]; then
  export PORT=5001
fi
PORT="${PORT:-5000}"

# Free stale mavsdk_server (orphaned after failed connect / reloader)
if command -v pgrep >/dev/null 2>&1; then
  STALE_MAVSDK="$(pgrep -f '[m]avsdk_server' 2>/dev/null || true)"
  if [[ -n "${STALE_MAVSDK}" ]] && ! pgrep -f "${ROOT}/venv/bin/python run_backend.py" >/dev/null 2>&1; then
    echo "Stopping stale mavsdk_server..."
    pkill -f '[m]avsdk_server' 2>/dev/null || true
    sleep 1
  fi
fi

# Stop stale backend from a previous run (same project)
if pgrep -f "${ROOT}/venv/bin/python run_backend.py" >/dev/null 2>&1; then
  echo "Stopping previous backend..."
  pkill -f "${ROOT}/venv/bin/python run_backend.py" 2>/dev/null || true
  sleep 1
fi

# Free the listen port (another Flask/reloader may still hold it)
if command -v lsof >/dev/null 2>&1; then
  PORT_PIDS="$(lsof -ti ":${PORT}" 2>/dev/null || true)"
  if [[ -n "${PORT_PIDS}" ]]; then
    echo "Freeing port ${PORT}..."
    # shellcheck disable=SC2086
    kill -9 ${PORT_PIDS} 2>/dev/null || true
    sleep 1
  fi
fi

# Warn if not Python 3.11
PY_VER="$(./venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PY_VER" != "3.11" ]]; then
  echo "Warning: venv uses Python $PY_VER (3.11 recommended). Run ./scripts/setup-dev.sh"
fi

echo "Backend URL: http://127.0.0.1:${PORT}"
if [[ "$(uname -s)" == "Darwin" ]] && [[ "$PORT" == "5001" ]]; then
  echo "Tip: macOS AirPlay uses port 5000 — we default to 5001."
fi

exec ./venv/bin/python run_backend.py
