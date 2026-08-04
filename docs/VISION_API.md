# Vision API (CV MVP release)

Canonical layout: `src/backend/` (+ `src/vision/` for detector/pipeline).

## camera_pitch_deg
negative = look-down, **-90 = nadir**, 0 = horizon.

## REST `/api/vision`
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/latest` | newest events |
| GET | `/events` | history (`?class=`) |
| POST | `/events` | ingest validated VisionEvent |
| GET | `/event/<uuid>` | one event |
| GET | `/snapshot/<uuid>` | JPEG / 404 |
| GET | `/errors` | non-fatal error journal |
| GET | `/health` | service health |

WebSocket: `subscribe_detections` / `subscribe_alerts` → `vision_detection` / `vision_alert` (≤10/s).

UI: `VisionOverlay`, `VisionPanel`, `VisionAlertsPanel` + `visionSocket.js`.

Docs for ML runbook: `docs/VISION_MVP.md`.
