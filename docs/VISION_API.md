# Vision API & WebSocket (Мерей) — CV MVP

Canonical layout: everything lives under `src/backend/` (not a root `backend/`
package). Geo is in `src/backend/geo/` (already on `feat/cv-integration-clean`).

## camera_pitch_deg

| Value | Meaning |
|-------|---------|
| negative | looking down |
| **-90** | nadir |
| **0** | horizon |

Aligned with Zhanel `VisionTelemetry`. Do not send the old `+90 = nadir` convention.

## REST

Base: `/api/vision`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/latest?limit=10` | newest VisionEvents |
| GET | `/events` | history (`?class=Person\|Car\|Truck_Machinery`) |
| GET | `/event/<uuid>` | one event |
| GET | `/snapshot/<uuid>` | JPEG crop or 404 |
| GET | `/stats` | counts + runtime flags |
| GET | `/errors` | error journal (no crash) |
| GET | `/geo/report` | MAE / max error for 50/75/100 m |
| GET | `/health` | service + runtime |
| POST | `/ingest` | detector handoff / demo ingest |
| POST | `/runtime` | set camera/model/stream flags (tests) |

### VisionEvent fields

`event_id` (UUID), `timestamp` (UTC `…Z`), `class_name`, `confidence` (0.65–1),
`bbox`, `latitude`, `longitude`, `snapshot_url`, `source_id`.

JSON Schema: `config/vision/vision-event.schema.json`  
Telemetry Schema: `config/vision/telemetry.schema.json`

## WebSocket

Client emits:

- `subscribe_detections`
- `subscribe_alerts`

Server emits (≤ **10 events/s**):

- `vision_detection` — `{ event_type, timestamp, data: VisionEvent }`
- `vision_alert` — same envelope for the alerts panel

Frontend: `web/src/services/visionSocket.js` + `web/src/components/VisionAlertsPanel.vue`
(UTC time, coordinates, confidence %, snapshot open).

## Failure behaviour (day 4)

On these faults the service **logs** to `/api/vision/errors` and **does not**
create an alert / invent GPS:

- camera unavailable
- stream broken
- model not loaded
- stale telemetry (>5 s) or invalid timestamp
- missing / invalid lat-lon
- contract/schema failure
- rate limit exceeded
- missing snapshot file → HTTP 404 (journal entry)

Dashboard `/api/vision/health` stays up.

## Tests

```bash
PYTHONPATH=. pytest tests/test_geo_calculator.py tests/test_vision_service.py tests/test_vision_stress.py -q
```

## Integration note

Do **not** merge the old root-level `backend/` tree from historical
`feat/cv-merei` commits into `main`. Use this branch (`feat/cv-merei-day4`)
which targets `feat/cv-integration-clean`.
