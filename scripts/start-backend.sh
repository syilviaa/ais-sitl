#!/usr/bin/env bash
# Start AIS SITL backend (Python 3.11 recommended)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d venv ]] || [[ ! -f venv/bin/python ]]; then
  chmod +x scripts/setup-dev.sh
  ./scripts/setup-dev.sh
fi

# Warn if not Python 3.11
PY_VER="$(./venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PY_VER" != "3.11" ]]; then
  echo "Warning: venv uses Python $PY_VER (3.11 recommended). Run ./scripts/setup-dev.sh"
fi

exec ./venv/bin/python run_backend.py
