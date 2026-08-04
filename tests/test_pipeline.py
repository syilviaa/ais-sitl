"""Tests for the end-to-end frame-to-VisionEvent pipeline."""

from datetime import datetime, timezone

import numpy as np
import pytest

from src.backend.services.vision_contracts import VisionTelemetry
from src.backend.geo.geo_calculator import GeoCalculator
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


def test_pipeline_rejects_missing_telemetry_before_detection(tmp_path):
    detector = FakeDetector([])
    pipeline = VisionPipeline(
        detector=detector,
        geo_locator=FakeGeoLocator(),
        snapshot_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="Telemetry cannot be None"):
        pipeline.process_frame(
            np.zeros((100, 200, 3), dtype=np.uint8),
            None,
            "missing-telemetry.mp4",
        )


def test_pipeline_uses_real_geo_calculator(tmp_path):
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    center_detection = Detection(
        class_name=VisionClass.CAR,
        confidence=0.88,
        bbox=BoundingBox(80, 40, 120, 60),
    )
    pipeline = VisionPipeline(
        detector=FakeDetector([center_detection]),
        geo_locator=GeoCalculator(),
        snapshot_dir=tmp_path,
    )
    telemetry = valid_telemetry()

    events = pipeline.process_frame(frame, telemetry, "real-geo.mp4")

    assert len(events) == 1
    assert events[0].latitude == pytest.approx(telemetry.latitude)
    assert events[0].longitude > telemetry.longitude
    distance_m = GeoCalculator().calculate_distance_m(
        telemetry.latitude,
        telemetry.longitude,
        events[0].latitude,
        events[0].longitude,
    )
    assert distance_m == pytest.approx(75.0, abs=0.1)
    assert (tmp_path / f"{events[0].event_id}.jpg").is_file()


def test_pipeline_measures_frame_to_alert_latency(tmp_path):
    ticks = iter([10.0, 10.48])
    timestamps = iter([
        datetime(2026, 8, 3, 12, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 3, 12, 0, 0, 480000, tzinfo=timezone.utc),
    ])
    detection = Detection(
        class_name=VisionClass.PERSON,
        confidence=0.90,
        bbox=BoundingBox(80, 40, 120, 60),
    )
    pipeline = VisionPipeline(
        detector=FakeDetector([detection]),
        geo_locator=FakeGeoLocator(),
        snapshot_dir=tmp_path,
        monotonic_clock=lambda: next(ticks),
        utc_now=lambda: next(timestamps),
    )

    pipeline.process_frame(
        np.zeros((100, 200, 3), dtype=np.uint8),
        valid_telemetry(),
        "latency.mp4",
    )

    assert pipeline.last_timing == {
        "frame_received_at": "2026-08-03T12:00:00.000Z",
        "alert_created_at": "2026-08-03T12:00:00.480Z",
        "latency_ms": pytest.approx(480.0),
        "within_target": True,
    }


def test_pipeline_marks_latency_over_one_second(tmp_path):
    ticks = iter([20.0, 21.2])
    timestamps = iter([
        datetime(2026, 8, 3, 12, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 3, 12, 0, 1, 200000, tzinfo=timezone.utc),
    ])
    detection = Detection(
        class_name=VisionClass.CAR,
        confidence=0.90,
        bbox=BoundingBox(80, 40, 120, 60),
    )
    pipeline = VisionPipeline(
        detector=FakeDetector([detection]),
        geo_locator=FakeGeoLocator(),
        snapshot_dir=tmp_path,
        monotonic_clock=lambda: next(ticks),
        utc_now=lambda: next(timestamps),
    )

    pipeline.process_frame(
        np.zeros((100, 200, 3), dtype=np.uint8),
        valid_telemetry(),
        "slow-latency.mp4",
    )

    assert pipeline.last_timing["latency_ms"] == pytest.approx(1200.0)
    assert pipeline.last_timing["within_target"] is False
