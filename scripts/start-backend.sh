#!/usr/bin/env bash
# Start AIS SITL backend (Python 3.11 recommended)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d venv ]]; then
  python3.11 -m venv venv 2>/dev/null || python3 -m venv venv
  ./venv/bin/pip install -r requirements.txt mavsdk
fi

exec ./venv/bin/python run_backend.py
