# Fixed CV evaluation dataset

This directory intentionally does not contain generated labels. Add only
human-reviewed frames extracted from the agreed test videos.

Required coverage:

- top-down and angled camera views;
- `Person`, `Car` and `Truck_Machinery` objects;
- varied object sizes and partially occluded objects;
- a fixed train-independent test split.

Expected layout:

```text
dataset/
  images/
    frame_000001.jpg
  labels/
    frame_000001.txt
```

Each label line uses normalized YOLO coordinates:

```text
class_id x_center y_center width height
```

Canonical dataset class IDs are `0=Person`, `1=Car`, and
`2=Truck_Machinery`. Every image must have a matching label file; an empty
file means the image was reviewed and contains none of the three classes.

Run the fixed evaluation with:

```bash
python scripts/evaluate_cv_map.py \
  --images /path/to/dataset/images \
  --labels /path/to/dataset/labels \
  --model /path/to/yolov8n.pt \
  --output reports/vision/map50.json
```

The report contains AP@0.5 for every class and overall mAP@0.5. A missing
ground-truth class is reported as `null`; it must never be presented as a
successful zero-error evaluation.
