#!/usr/bin/env bash
# E2E Sprint MVP demo (TZ §4.2) — API checks without live SITL.
# Usage: ./scripts/e2e-sprint-demo.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:5001/api}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== AIS SITL E2E Sprint Demo ==="
echo "Backend: $BASE"

fail() { echo "FAIL: $1"; exit 1; }
ok() { echo "OK: $1"; }

# Health
curl -sf "$BASE/health" >/dev/null || fail "health unreachable"
ok "health"

# Geofence GeoJSON
GEO=$(curl -sf "$BASE/geofence/geojson")
echo "$GEO" | grep -q FeatureCollection || fail "geofence geojson"
ok "geofence geojson"

# NFZ list (loaded from GeoJSON)
COUNT=$(curl -sf "$BASE/geofence/list" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")
[[ "$COUNT" -ge 1 ]] || fail "geofence list empty (expected NFZ from GeoJSON)"
ok "geofence list ($COUNT zones)"

# Safe 4-waypoint mission (Astana training field)
WAYPOINTS='[
  {"lat":51.1680,"lon":71.4460,"altitude":50},
  {"lat":51.1688,"lon":71.4475,"altitude":60},
  {"lat":51.1692,"lon":71.4485,"altitude":60},
  {"lat":51.1680,"lon":71.4460,"altitude":0}
]'

VALID=$(curl -sf -X POST "$BASE/mission/validate" \
  -H 'Content-Type: application/json' \
  -d "{\"waypoints\":$WAYPOINTS}")
echo "$VALID" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('valid'), d" \
  || fail "mission validate"
ok "mission validate (4 WP, NFZ clear)"

# Export .plan
PLAN=$(curl -sf -X POST "$BASE/mission/export-plan" \
  -H 'Content-Type: application/json' \
  -d "{\"waypoints\":$WAYPOINTS,\"name\":\"Sprint Demo\"}")
echo "$PLAN" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('success')" \
  || fail "mission export"
ok "mission export .plan"

# Telemetry fields (stub or live)
TEL=$(curl -sf "$BASE/telemetry/latest")
python3 -c "
import json, sys
d = json.loads('''$TEL''')
for k in ('lat','lon','speed','ground_speed_m_s','vertical_speed_m_s','latency_ms'):
    assert k in d, f'missing {k}'
" || fail "telemetry schema"
ok "telemetry schema (ground/vertical speed)"

# Video status
curl -sf "$BASE/video/status" >/dev/null || fail "video status"
ok "video status"

# Unit tests (MVP compliance)
if [[ -x "$ROOT/venv/bin/pytest" ]]; then
  (cd "$ROOT" && ./venv/bin/pytest tests/test_sprint_mvp.py tests/test_geofence.py -q --tb=line) \
    || fail "pytest sprint_mvp+geofence"
  ok "pytest sprint_mvp + geofence"
fi

echo ""
echo "=== E2E API checks passed ==="
echo "Live SITL: Initialize → Upload → Start → RTL → Land via Dashboard"
