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
  --output reports/vision/benchmark.json
```

The fixed labeled dataset format and mAP command are documented in
`config/vision/evaluation/README.md`. mAP is evaluated from low-confidence
predictions (`0.001`) to build a precision-recall curve; the live event
contract still enforces the production threshold `0.65`.

Do not publish an mAP value until the human-reviewed top-down and angled test
frames contain ground truth for all three classes.
