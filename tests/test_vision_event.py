"""Tests for backend serialization of one geolocated CV detection."""

from datetime import datetime
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.backend.services.vision_contracts import (
    VisionContractError,
    VisionEvent,
    load_schema,
)
from src.vision.models import BoundingBox, Detection, VisionClass


@pytest.fixture
def person_detection():
    return Detection(
        class_name=VisionClass.PERSON,
        confidence=0.82,
        bbox=BoundingBox(100, 200, 260, 520),
    )


def test_vision_event_serializes_detection_and_location(person_detection):
    event = VisionEvent.from_detection(
        person_detection,
        latitude=51.1695,
        longitude=71.4492,
        snapshot_url="/api/vision/snapshots/event.jpg",
        source_id="local-demo.mp4",
        event_id="d8c7716d-bf56-4f57-a88c-4cb0ba2c8846",
        timestamp="2026-08-02T09:00:00Z",
    )

    assert event.to_dict() == {
        "event_id": "d8c7716d-bf56-4f57-a88c-4cb0ba2c8846",
        "timestamp": "2026-08-02T09:00:00Z",
        "class_name": "Person",
        "confidence": 0.82,
        "bbox": [100, 200, 260, 520],
        "latitude": 51.1695,
        "longitude": 71.4492,
        "snapshot_url": "/api/vision/snapshots/event.jpg",
        "source_id": "local-demo.mp4",
    }


def test_vision_event_generates_uuid_and_utc_timestamp(person_detection):
    event = VisionEvent.from_detection(
        person_detection,
        latitude=51.1695,
        longitude=71.4492,
        snapshot_url="/api/vision/snapshots/generated.jpg",
        source_id="camera-1",
    )

    assert str(UUID(event.event_id)) == event.event_id
    assert event.timestamp.endswith("Z")
    datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))


def test_vision_event_rejects_confidence_below_contract_threshold():
    detection = Detection(
        class_name=VisionClass.CAR,
        confidence=0.64,
        bbox=BoundingBox(10, 10, 20, 20),
    )

    with pytest.raises(VisionContractError, match="confidence"):
        VisionEvent.from_detection(
            detection,
            latitude=51.0,
            longitude=71.0,
            snapshot_url="/snapshot.jpg",
            source_id="camera-1",
        )


def test_serialized_event_matches_json_schema(person_detection):
    event = VisionEvent.from_detection(
        person_detection,
        latitude=51.1695,
        longitude=71.4492,
        snapshot_url="/api/vision/snapshots/event.jpg",
        source_id="camera-1",
    )
    validator = Draft202012Validator(
        load_schema("vision-event.schema.json"),
        format_checker=FormatChecker(),
    )

    assert list(validator.iter_errors(event.to_dict())) == []


def test_vision_event_rejects_non_finite_bbox():
    detection = Detection(
        class_name=VisionClass.PERSON,
        confidence=0.90,
        bbox=BoundingBox(float("nan"), 10, 20, 30),
    )

    with pytest.raises(VisionContractError, match="finite"):
        VisionEvent.from_detection(
            detection,
            latitude=51.0,
            longitude=71.0,
            snapshot_url="/snapshot.jpg",
            source_id="camera-1",
        )
