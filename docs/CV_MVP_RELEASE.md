# CV MVP release branch

**Branch:** `feat/cv-mvp-release` → merge into `main`

## Frontend (reference UI)
Astana compact dashboard:
- Header: Бат / mode / Моторы / Failsafe / API / WS
- Map + NFZ
- Управление / Миссия / **Видео** (VisionOverlay + Camera/Detector/Stream) / Журнал
- CV alerts under video statuses

Matches the Astana training-field UI with CV statuses under the video pane.

## Backend
- `src/backend/*` + `src/vision/*` + `src/backend/geo/*`
- REST `/api/vision`, Socket.IO alerts ≤10/s
- Gazebo video: UDP `5600` → `/api/video/mjpeg` on port **5001** (macOS)

## Smoke
```bash
PYTHONPATH=. pytest tests/test_geo_calculator.py tests/test_vision_api.py tests/test_vision_event.py -q
PYTHONPATH=. python3 run_backend.py
cd web && npm run dev
```
