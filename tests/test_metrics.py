"""Tests for reproducible CV mAP@0.5 evaluation."""

import pytest

from src.vision.metrics import GroundTruth, Prediction, evaluate_map50, iou
from src.vision.models import BoundingBox, VisionClass
from scripts.evaluate_cv_map import parse_yolo_labels


def box(x1, y1, x2, y2):
    return BoundingBox(x1, y1, x2, y2)


def test_iou_for_identical_and_disjoint_boxes():
    assert iou(box(0, 0, 10, 10), box(0, 0, 10, 10)) == pytest.approx(1.0)
    assert iou(box(0, 0, 10, 10), box(20, 20, 30, 30)) == 0.0


def test_map50_reports_each_class_and_overall_score():
    truths = [
        GroundTruth("top.jpg", VisionClass.PERSON, box(0, 0, 10, 10)),
        GroundTruth("angle.jpg", VisionClass.CAR, box(20, 20, 40, 40)),
        GroundTruth(
            "angle.jpg",
            VisionClass.TRUCK_MACHINERY,
            box(50, 50, 80, 80),
        ),
    ]
    predictions = [
        Prediction("top.jpg", VisionClass.PERSON, 0.9, box(0, 0, 10, 10)),
        Prediction("angle.jpg", VisionClass.CAR, 0.8, box(20, 20, 40, 40)),
        Prediction(
            "angle.jpg",
            VisionClass.TRUCK_MACHINERY,
            0.7,
            box(0, 0, 10, 10),
        ),
    ]

    report = evaluate_map50(predictions, truths)

    assert report["per_class"]["Person"]["ap50"] == pytest.approx(1.0)
    assert report["per_class"]["Car"]["ap50"] == pytest.approx(1.0)
    assert report["per_class"]["Truck_Machinery"]["ap50"] == 0.0
    assert report["map50"] == pytest.approx(2 / 3)


def test_class_without_ground_truth_is_not_hidden_in_report():
    report = evaluate_map50(
        [],
        [GroundTruth("top.jpg", VisionClass.PERSON, box(0, 0, 10, 10))],
    )

    assert report["per_class"]["Car"]["ap50"] is None
    assert report["per_class"]["Truck_Machinery"]["ap50"] is None
    assert report["map50"] == 0.0


def test_parse_yolo_labels_converts_normalized_center_box(tmp_path):
    label_file = tmp_path / "top.txt"
    label_file.write_text("0 0.5 0.5 0.2 0.4\n", encoding="utf-8")

    labels = parse_yolo_labels(label_file, "top.jpg", 200, 100)

    assert labels == [
        GroundTruth(
            "top.jpg",
            VisionClass.PERSON,
            box(80, 30, 120, 70),
        )
    ]


def test_parse_yolo_labels_rejects_unknown_class(tmp_path):
    label_file = tmp_path / "bad.txt"
    label_file.write_text("3 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="class id 3"):
        parse_yolo_labels(label_file, "bad.jpg", 100, 100)
