# AIS SITL CV MVP

## Runtime contract

The detector accepts a local video file or an RTSP stream and keeps only
three canonical classes at confidence `>=0.65`:

- COCO `person` -> `Person`;
- COCO `car` -> `Car`;
- COCO `truck` -> `Truck_Machinery`.

The pretrained COCO model has no dedicated machinery class. Therefore
`Truck_Machinery` currently means detected trucks and is not a reliable
classifier for excavators, cranes, or other specialist machinery.

Install the optional runtime in an isolated environment:

```bash
python3.11 -m venv .venv-cv
source .venv-cv/bin/activate
python -m pip install -r requirements-cv.txt
```

`OpenCVVideoSource` accepts normal filesystem paths and `rtsp://` or
`rtsps://` URLs. The MVP is RGB-only: it does not consume depth, thermal,
segmentation, or DEM data.

## Dashboard

`VisionOverlay.vue` draws scalable bounding boxes, the canonical class, and
confidence percentage over a 1920x1080 stream. `VisionPanel.vue` exposes
camera, model and stream state plus FPS and frame-to-alert latency. An empty
stream URL shows an explicit placeholder instead of pretending that video is
connected.

## Latency

`VisionPipeline.last_timing` records UTC `frame_received_at`, UTC
`alert_created_at`, elapsed milliseconds from a monotonic clock, and whether
the one-second target was met. On the local 1080p smoke test, the first cold
CPU inference took about 1046 ms; the next two frames took 76.0 and 74.4 ms.
The model should therefore be loaded and warmed before live frames are
accepted. Cold-start latency must remain visible in reports.
The captured smoke result is stored in
`config/vision/day3-latency-smoke.json`.

## FPS and mAP@0.5

Measure inference FPS without playback sleeps:

```bash
python scripts/benchmark_cv.py \
  --source /path/to/1080p.mp4 \
  --model /path/to/yolov8n.pt \
  --max-frames 100 \
  --warmup-frames 1 \
  --output reports/vision/benchmark.json
```

The warm-up frames are run before the timer and never become working events.
The fixed Day 4 CPU smoke result is stored in
`config/vision/day4-benchmark.json` (`19.86 FPS` for 20 1080p frames after
one cold warm-up frame).

The fixed labeled dataset format and mAP command are documented in
`config/vision/evaluation/README.md`. mAP is evaluated from low-confidence
predictions (`0.001`) to build a precision-recall curve; the live event
contract still enforces the production threshold `0.65`.

Do not publish an mAP value until the human-reviewed top-down and angled test
frames contain ground truth for all three classes.

## Complete local demonstration

Open three terminals in the repository. On macOS the backend uses port 5001
because AirPlay commonly occupies port 5000.

Terminal 1 — backend REST and Socket.IO:

```bash
source .venv-cv/bin/activate
python run_backend.py
```

Terminal 2 — Vue Dashboard:

```bash
npm --prefix web install
npm --prefix web run dev
```

Open `http://localhost:5173` in a browser. The video pane defaults to the
CV-annotated MJPEG stream at `/api/vision/mjpeg` (boxes on frames).

Terminal 3 — TZ acceptance / local pipeline:

```bash
python scripts/run_tz_acceptance.py \
  --source /path/to/drone.mp4 \
  --model /path/to/yolov8n.pt \
  --backend-url http://127.0.0.1:5001 \
  --output-video /tmp/ais-cv-models/tz_fpv_boxed.mp4
```

Or the lighter publisher:

```bash
python scripts/run_cv_pipeline.py \
  --source /path/to/drone.mp4 \
  --model /path/to/yolov8n.pt \
  --telemetry config/vision/fixtures/telemetry_valid.json \
  --backend-url http://127.0.0.1:5001 \
  --device cpu \
  --max-frames 20
```

For RTSP, replace only `--source` with the provided `rtsp://...` URL. The
pipeline warms the model with the first readable frame, processes subsequent
frames, writes snapshots to `/private/tmp/ais-sitl-vision-snapshots`, and
publishes canonical events to `/api/vision/events`.

Verify the backend manually:

```bash
curl "http://127.0.0.1:5001/api/vision/latest?limit=2"
curl "http://127.0.0.1:5001/api/vision/health"
```

The fixed Day 4 local E2E smoke result is stored in
`config/vision/day4-e2e-smoke.json`: two working frames produced eight events,
the latest REST request returned HTTP 200, event posts returned HTTP 201, and
the measured frame-to-alert latency was 88.11 ms.

## Vision API and Socket.IO

- `GET /api/vision/latest?limit=10` — newest events first;
- `GET /api/vision/events?class=Person` — event history/filter;
- `POST /api/vision/events` — publish a validated `VisionEvent`;
- `GET /api/vision/events/<uuid>` — one event;
- `GET /api/vision/snapshots/<uuid>.jpg` — JPEG snapshot;
- `GET /api/vision/errors` — non-fatal error journal;
- `GET /api/vision/health` — service status and counts;
- Socket.IO `vision_detection` and `vision_alert` — at most 10 events/s.

The Dashboard remains usable when the vision backend, model, camera, telemetry,
or snapshot is unavailable. Events without valid GPS are rejected instead of
showing invented coordinates.
