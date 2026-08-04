# CV evaluation dataset (MVP smoke)

Images + YOLO-format labels for Person(0) / Car(1) / Truck_Machinery(2).

```bash
PYTHONPATH=. python scripts/evaluate_cv_map.py \
  --images config/vision/evaluation/images \
  --labels config/vision/evaluation/labels \
  --model /path/to/yolov8n.pt \
  --output config/vision/evaluation/map50.json
```

Acceptance gate from TZ: **mAP@0.5 ≥ 0.75**.

Current smoke set is a small reviewed static-photo set (street / car / bus).
Replace with human-labeled top-down + angled drone frames before publishing
a formal mAP claim.
