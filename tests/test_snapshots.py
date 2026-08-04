"""Tests for annotated JPEG snapshots and detection crops."""

import numpy as np
import pytest

from src.vision.models import BoundingBox, Detection, VisionClass
from src.vision.snapshots import SnapshotWriter


def test_snapshot_writer_saves_annotated_frame_and_crop(tmp_path):
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    detection = Detection(
        class_name=VisionClass.PERSON,
        confidence=0.91,
        bbox=BoundingBox(20, 10, 80, 70),
    )
    event_id = "123e4567-e89b-12d3-a456-426614174000"

    saved = SnapshotWriter(tmp_path).save(frame, detection, event_id)

    assert saved.event_id == event_id
    assert saved.snapshot_path == tmp_path / f"{event_id}.jpg"
    assert saved.crop_path == tmp_path / f"{event_id}_crop.jpg"
    assert saved.snapshot_path.is_file()
    assert saved.crop_path.is_file()


def test_snapshot_writer_rejects_empty_frame(tmp_path):
    detection = Detection(
        class_name=VisionClass.CAR,
        confidence=0.82,
        bbox=BoundingBox(1, 1, 10, 10),
    )

    try:
        SnapshotWriter(tmp_path).save(None, detection, "event-1")
    except ValueError as exc:
        assert str(exc) == "Frame cannot be None"
    else:
        raise AssertionError("Expected an empty frame to be rejected")


def test_snapshot_writer_rejects_blank_event_id(tmp_path):
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    detection = Detection(
        class_name=VisionClass.TRUCK_MACHINERY,
        confidence=0.75,
        bbox=BoundingBox(1, 1, 10, 10),
    )

    try:
        SnapshotWriter(tmp_path).save(frame, detection, "  ")
    except ValueError as exc:
        assert str(exc) == "event_id cannot be blank"
    else:
        raise AssertionError("Expected a blank event_id to be rejected")


def test_snapshot_writer_clamps_bbox_to_frame_edges(tmp_path):
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    detection = Detection(
        class_name=VisionClass.CAR,
        confidence=0.88,
        bbox=BoundingBox(-5, -4, 12, 15),
    )

    event_id = "123e4567-e89b-12d3-a456-426614174001"
    saved = SnapshotWriter(tmp_path).save(frame, detection, event_id)

    import cv2

    crop = cv2.imread(str(saved.crop_path))
    assert crop.shape[:2] == (15, 12)


def test_snapshot_writer_requires_uuid_event_id(tmp_path):
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    detection = Detection(
        class_name=VisionClass.PERSON,
        confidence=0.90,
        bbox=BoundingBox(1, 1, 10, 10),
    )

    with pytest.raises(ValueError, match="UUID"):
        SnapshotWriter(tmp_path).save(frame, detection, "not-a-uuid")


def test_snapshot_writer_reports_unavailable_storage(tmp_path, monkeypatch):
    import cv2

    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    detection = Detection(
        class_name=VisionClass.PERSON,
        confidence=0.90,
        bbox=BoundingBox(1, 1, 10, 10),
    )
    monkeypatch.setattr(cv2, "imwrite", lambda *args, **kwargs: False)

    with pytest.raises(RuntimeError, match="Cannot write snapshot"):
        SnapshotWriter(tmp_path).save(
            frame,
            detection,
            "123e4567-e89b-12d3-a456-426614174002",
        )
