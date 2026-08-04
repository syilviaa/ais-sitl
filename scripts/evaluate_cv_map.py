#!/usr/bin/env python3
"""Evaluate the three AIS SITL classes with mAP@0.5."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_cv import detect_device  # noqa: E402
from src.vision.detector import UltralyticsBackend, VisionDetector  # noqa: E402
from src.vision.metrics import (  # noqa: E402
    GroundTruth,
    Prediction,
    evaluate_map50,
)
from src.vision.models import BoundingBox, VisionClass  # noqa: E402


DATASET_CLASS_IDS = {
    0: VisionClass.PERSON,
    1: VisionClass.CAR,
    2: VisionClass.TRUCK_MACHINERY,
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def parse_yolo_labels(path, image_id, image_width, image_height):
    """Read canonical class_id/x_center/y_center/width/height labels."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Label file not found: {path}")

    labels = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        parts = raw_line.split()
        if len(parts) != 5:
            raise ValueError(f"{path}:{line_number}: expected 5 values")
        class_id = int(parts[0])
        if class_id not in DATASET_CLASS_IDS:
            raise ValueError(
                f"{path}:{line_number}: unsupported class id {class_id}"
            )
        center_x, center_y, width, height = map(float, parts[1:])
        if not (
            0.0 <= center_x <= 1.0
            and 0.0 <= center_y <= 1.0
            and 0.0 < width <= 1.0
            and 0.0 < height <= 1.0
        ):
            raise ValueError(
                f"{path}:{line_number}: normalized values are out of range"
            )
        pixel_width = width * image_width
        pixel_height = height * image_height
        x1 = center_x * image_width - pixel_width / 2.0
        y1 = center_y * image_height - pixel_height / 2.0
        x2 = x1 + pixel_width
        y2 = y1 + pixel_height
        labels.append(GroundTruth(
            image_id=image_id,
            class_name=DATASET_CLASS_IDS[class_id],
            bbox=BoundingBox(x1, y1, x2, y2),
        ))
    return labels


def evaluate_dataset(images_dir, labels_dir, model_path, device="auto"):
    """Run the detector over a fixed labeled image dataset."""
    import cv2

    images_dir = Path(images_dir)
    labels_dir = Path(labels_dir)
    model_path = Path(model_path)
    if not images_dir.is_dir():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")
    if not labels_dir.is_dir():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")
    if not model_path.is_file():
        raise FileNotFoundError(f"YOLO model not found: {model_path}")

    image_paths = sorted(
        path for path in images_dir.iterdir()
        if path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not image_paths:
        raise ValueError(f"No images found in: {images_dir}")

    selected_device = detect_device(device)
    detector = VisionDetector(
        UltralyticsBackend(str(model_path), device=selected_device),
        confidence_threshold=0.001,
    )
    predictions = []
    ground_truths = []
    for image_path in image_paths:
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise ValueError(f"Unreadable image: {image_path}")
        image_height, image_width = frame.shape[:2]
        image_id = image_path.name
        ground_truths.extend(parse_yolo_labels(
            labels_dir / f"{image_path.stem}.txt",
            image_id,
            image_width,
            image_height,
        ))
        result = detector.detect(frame, source_id=image_id)
        predictions.extend(
            Prediction(
                image_id=image_id,
                class_name=detection.class_name,
                confidence=detection.confidence,
                bbox=detection.bbox,
            )
            for detection in result.detections
        )

    report = evaluate_map50(predictions, ground_truths)
    report.update({
        "timestamp": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "images_dir": str(images_dir),
        "labels_dir": str(labels_dir),
        "model": str(model_path),
        "device": selected_device,
        "image_count": len(image_paths),
        "evaluation_confidence_floor": 0.001,
    })
    return report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", help="Optional JSON report path")
    return parser


def main():
    args = build_parser().parse_args()
    report = evaluate_dataset(
        args.images,
        args.labels,
        args.model,
        args.device,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
