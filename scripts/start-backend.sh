#!/bin/sh
# Local backend — run from repo root: ./scripts/start-backend.sh
set -e
cd "$(dirname "$0")/.."

if [ ! -d venv ]; then
  echo "Creating venv..."
  python3 -m venv venv
  ./venv/bin/pip install -r requirements.txt
fi

echo "Starting backend at http://127.0.0.1:5000"
exec ./venv/bin/python run_backend.py
