"""Unit tests for the CV MVP detector owned by Zhanel."""

import pytest

from src.vision.detector import (
    OpenCVVideoSource,
    VisionDetector,
)
from src.vision.models import BoundingBox, VisionClass


class FakeFrame:
    """Small frame substitute; no OpenCV or NumPy required."""

    def __init__(self, height=1080, width=1920):
        self.shape = (height, width, 3)


class FakeBackend:
    """Return predefined YOLO-like detections."""

    def __init__(self, detections):
        self.detections = detections
        self.received_frames = []

    def predict(self, frame):
        self.received_frames.append(frame)
        return list(self.detections)


def raw_detection(class_id, confidence, bbox=(100, 200, 300, 600)):
    return {
        "class_id": class_id,
        "confidence": confidence,
        "bbox": list(bbox),
    }


def test_confidence_below_65_percent_is_rejected():
    backend = FakeBackend([raw_detection(0, 0.649)])
    detector = VisionDetector(backend=backend, confidence_threshold=0.65)

    result = detector.detect(FakeFrame())

    assert result.detections == []


def test_confidence_equal_to_65_percent_is_accepted():
    backend = FakeBackend([raw_detection(0, 0.650)])
    detector = VisionDetector(backend=backend, confidence_threshold=0.65)

    result = detector.detect(FakeFrame())

    assert len(result.detections) == 1
    assert result.detections[0].confidence == pytest.approx(0.65)


@pytest.mark.parametrize(
    ("coco_id", "expected_class"),
    [
        (0, VisionClass.PERSON),
        (2, VisionClass.CAR),
        (7, VisionClass.TRUCK_MACHINERY),
    ],
)
def test_required_coco_classes_are_mapped(coco_id, expected_class):
    backend = FakeBackend([raw_detection(coco_id, 0.90)])
    result = VisionDetector(backend=backend).detect(FakeFrame())

    assert result.detections[0].class_name is expected_class


def test_unrequested_coco_class_is_ignored():
    # COCO class 16 is dog and is outside CV MVP v1.0.
    backend = FakeBackend([raw_detection(16, 0.99)])

    result = VisionDetector(backend=backend).detect(FakeFrame())

    assert result.detections == []


def test_empty_backend_result_returns_empty_detection_list():
    result = VisionDetector(backend=FakeBackend([])).detect(FakeFrame())

    assert result.detections == []
    assert result.frame_width == 1920
    assert result.frame_height == 1080


def test_warmup_runs_backend_without_creating_working_result():
    frame = FakeFrame()
    backend = FakeBackend([raw_detection(0, 0.90)])
    detector = VisionDetector(backend=backend)

    result = detector.warmup(frame)

    assert result is None
    assert backend.received_frames == [frame]


def test_none_frame_is_rejected_before_backend_call():
    backend = FakeBackend([])

    with pytest.raises(ValueError, match="Frame cannot be None"):
        VisionDetector(backend=backend).detect(None)

    assert backend.received_frames == []


@pytest.mark.parametrize("shape", [None, (), (0, 1920, 3), (1080, 0, 3)])
def test_broken_frame_shape_is_rejected(shape):
    frame = FakeFrame()
    frame.shape = shape

    with pytest.raises(ValueError):
        VisionDetector(backend=FakeBackend([])).detect(frame)


@pytest.mark.parametrize(
    "bbox",
    [
        (100, 100, 100, 200),
        (100, 100, 200, 100),
        (200, 100, 100, 200),
    ],
)
def test_invalid_bounding_box_is_rejected(bbox):
    with pytest.raises(ValueError, match="positive width and height"):
        BoundingBox(*bbox)


def test_missing_local_video_source_is_rejected(tmp_path):
    missing_path = tmp_path / "missing-video.mp4"

    with pytest.raises(FileNotFoundError, match="Video source not found"):
        with OpenCVVideoSource(missing_path):
            pass


def test_bounding_box_center_and_serialization():
    backend = FakeBackend([raw_detection(2, 0.82, (100, 200, 300, 600))])

    result = VisionDetector(backend=backend).detect(
        FakeFrame(),
        source_id="local-demo.mp4",
        timestamp="2026-08-03T12:00:00Z",
    )
    payload = result.to_dict()

    assert result.detections[0].bbox.center == (200.0, 400.0)
    assert payload["source_id"] == "local-demo.mp4"
    assert payload["timestamp"] == "2026-08-03T12:00:00Z"
