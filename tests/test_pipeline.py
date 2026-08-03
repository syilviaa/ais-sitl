"""Tests for the end-to-end frame-to-VisionEvent pipeline."""

import numpy as np

from src.backend.services.vision_contracts import VisionTelemetry
from src.vision.models import (
    BoundingBox,
    Detection,
    DetectorResult,
    VisionClass,
)
from src.vision.pipeline import VisionPipeline


class FakeDetector:
    def __init__(self, detections):
        self.detections = detections

    def detect(self, frame, source_id="unknown"):
        return DetectorResult(
            frame_id="frame-1",
            timestamp="2026-08-02T09:00:00Z",
            frame_width=200,
            frame_height=100,
            source_id=source_id,
            detections=list(self.detections),
        )


class FakeGeoLocator:
    def __init__(self):
        self.calls = []

    def pixel_to_gps(self, bbox_center, telemetry):
        self.calls.append((bbox_center, telemetry))
        return 51.1695, 71.4492


def valid_telemetry():
    return VisionTelemetry.from_dict({
        "timestamp": "2026-08-02T09:00:00Z",
        "latitude": 51.1694,
        "longitude": 71.4491,
        "altitude_m": 75,
        "drone_yaw_deg": 90,
        "camera_pitch_deg": -45,
        "camera_yaw_deg": 0,
        "hfov_deg": 90,
        "vfov_deg": 60,
        "frame_width": 200,
        "frame_height": 100,
    })


def test_pipeline_creates_event_snapshot_and_crop(tmp_path):
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    detection = Detection(
        class_name=VisionClass.PERSON,
        confidence=0.91,
        bbox=BoundingBox(20, 10, 80, 70),
    )
    geo_locator = FakeGeoLocator()
    pipeline = VisionPipeline(
        detector=FakeDetector([detection]),
        geo_locator=geo_locator,
        snapshot_dir=tmp_path,
        snapshot_url_prefix="/api/vision/snapshots",
    )

    events = pipeline.process_frame(frame, valid_telemetry(), "demo.mp4")

    assert len(events) == 1
    event = events[0]
    assert event.class_name == "Person"
    assert event.latitude == 51.1695
    assert event.longitude == 71.4492
    assert event.source_id == "demo.mp4"
    assert event.timestamp == "2026-08-02T09:00:00Z"
    assert event.snapshot_url == (
        f"/api/vision/snapshots/{event.event_id}.jpg"
    )
    assert geo_locator.calls == [((50.0, 40.0), valid_telemetry())]
    assert (tmp_path / f"{event.event_id}.jpg").is_file()
    assert (tmp_path / f"{event.event_id}_crop.jpg").is_file()


def test_pipeline_returns_no_events_for_empty_detection(tmp_path):
    pipeline = VisionPipeline(
        detector=FakeDetector([]),
        geo_locator=FakeGeoLocator(),
        snapshot_dir=tmp_path,
        snapshot_url_prefix="/api/vision/snapshots",
    )

    events = pipeline.process_frame(
        np.zeros((100, 200, 3), dtype=np.uint8),
        valid_telemetry(),
        "empty.mp4",
    )

    assert events == []
    assert list(tmp_path.iterdir()) == []
