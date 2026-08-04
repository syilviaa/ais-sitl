# CV MVP release branch

**Branch:** `feat/cv-mvp-release`  
**Target:** `main`

## What’s included
- Stable dashboard from `main` (Astana UI, video relay, SITL fixes)
- Full CV stack from `feat/cv-zhanel-day4`:
  - detector / pipeline / snapshots / metrics
  - `src/backend/geo` (Pixel-to-GPS)
  - vision REST + Socket.IO
  - Overlay, Panel, Alerts UI
- Merge conflict resolution for `app.py` / `App.vue` (video + CV together)
- Snapshot dir defaults to local `./snapshots` (override with `VISION_SNAPSHOT_DIR`)

## Do not merge into this PR
- Old `feat/cv-merei` with root-level `backend/` package

## Smoke
```bash
PYTHONPATH=. pytest tests/test_geo_calculator.py tests/test_vision_api.py tests/test_vision_event.py -q
PYTHONPATH=. python run_backend.py
cd web && npm run dev
```
