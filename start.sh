#!/bin/sh
set -e

PORT="${PORT:-10000}"

exec gunicorn \
  --workers "${GUNICORN_WORKERS:-3}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --worker-class gthread \
  --bind "0.0.0.0:${PORT}" \
  --timeout 120 \
  wsgi:app
