#!/usr/bin/env bash
# Dev environment: Python 3.11 + MAVSDK + mavsdk_server (Mac ARM).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY311="${PY311:-python3.11}"
if ! command -v "$PY311" >/dev/null 2>&1; then
  echo "Python 3.11 required. Install: brew install python@3.11"
  exit 1
fi

echo "Creating venv with $("$PY311" --version)..."
rm -rf venv
"$PY311" -m venv venv
./venv/bin/pip install -U pip wheel
./venv/bin/pip install -r requirements.txt mavsdk

MAVSDK_BIN="$(./venv/bin/python -c "import mavsdk; from pathlib import Path; print(Path(mavsdk.__file__).parent / 'bin')")"
mkdir -p "$MAVSDK_BIN"

if [[ ! -f "$MAVSDK_BIN/mavsdk_server" ]]; then
  ARCH="$(uname -m)"
  MAVSDK_VER="${MAVSDK_SERVER_VERSION:-3.17.2}"
  case "$ARCH" in
    arm64)
      ASSET="mavsdk_server_macos_arm64"
      ;;
    x86_64)
      ASSET="mavsdk_server_macos_x64"
      ;;
    *)
      echo "Unsupported arch: $ARCH — set MAVSDK_SERVER_PATH manually"
      exit 1
      ;;
  esac
  URL="https://github.com/mavlink/MAVSDK/releases/download/v${MAVSDK_VER}/${ASSET}"
  echo "Downloading mavsdk_server from $URL ..."
  curl -fsSL "$URL" -o "$MAVSDK_BIN/mavsdk_server"
  chmod +x "$MAVSDK_BIN/mavsdk_server"
fi

# Homebrew fallback path (optional)
if [[ -x /opt/homebrew/bin/mavsdk_server ]]; then
  echo "Homebrew mavsdk_server also available at /opt/homebrew/bin/mavsdk_server"
fi

./venv/bin/python -c "
from src.mavsdk_import import MAVSDK_AVAILABLE, mavsdk_server_available, resolve_mavsdk_server_path
print('MAVSDK_AVAILABLE:', MAVSDK_AVAILABLE)
print('mavsdk_server:', resolve_mavsdk_server_path())
print('mavsdk_server_available:', mavsdk_server_available())
"

echo "Done. Start backend: ./scripts/start-backend.sh"
