"""Tests for Zhanel's CV telemetry input and JSON contracts."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.backend.services.vision_contracts import (
    VisionContractError,
    VisionTelemetry,
    load_schema,
)
from src.backend.services.vision_telemetry_service import (
    VisionTelemetryService,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "config" / "vision" / "fixtures"


def load_fixture(name):
    with (FIXTURES / name).open(encoding="utf-8") as stream:
        return json.load(stream)


@pytest.fixture
def valid_payload():
    return load_fixture("telemetry_valid.json")


def test_valid_payload_is_parsed_and_retained(valid_payload):
    service = VisionTelemetryService()

    telemetry = service.ingest(valid_payload)

    assert telemetry.latitude == pytest.approx(51.1694)
    assert telemetry.longitude == pytest.approx(71.4491)
    assert telemetry.altitude_m == pytest.approx(75.0)
    assert telemetry.frame_width == 1920
    assert telemetry.frame_height == 1080
    assert service.latest() == telemetry
    assert service.history() == [telemetry]


def test_non_object_payload_is_rejected():
    with pytest.raises(VisionContractError, match="must be an object"):
        VisionTelemetry.from_dict([])


@pytest.mark.parametrize(
    "missing_field",
    [
        "timestamp",
        "latitude",
        "longitude",
        "altitude_m",
        "drone_yaw_deg",
        "camera_pitch_deg",
        "camera_yaw_deg",
        "hfov_deg",
        "vfov_deg",
    ],
)
def test_missing_required_field_is_rejected(valid_payload, missing_field):
    valid_payload.pop(missing_field)

    with pytest.raises(VisionContractError):
        VisionTelemetry.from_dict(valid_payload)


@pytest.mark.parametrize(
    ("altitude", "is_valid"),
    [(49, False), (50, True), (100, True), (101, False)],
)
def test_altitude_boundaries(valid_payload, altitude, is_valid):
    valid_payload["altitude_m"] = altitude

    if is_valid:
        assert VisionTelemetry.from_dict(valid_payload).altitude_m == altitude
    else:
        with pytest.raises(VisionContractError, match="altitude_m"):
            VisionTelemetry.from_dict(valid_payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitude", -90.1),
        ("latitude", 90.1),
        ("longitude", -180.1),
        ("longitude", 180.1),
    ],
)
def test_invalid_coordinates_are_rejected(valid_payload, field, value):
    valid_payload[field] = value

    with pytest.raises(VisionContractError, match=field):
        VisionTelemetry.from_dict(valid_payload)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-08-03T12:00:00",
        "2026-08-03T12:00:00+06:00",
        "not-a-timestamp",
        None,
    ],
)
def test_timestamp_must_be_valid_utc(valid_payload, timestamp):
    valid_payload["timestamp"] = timestamp

    with pytest.raises(VisionContractError, match="timestamp"):
        VisionTelemetry.from_dict(valid_payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hfov_deg", 0),
        ("hfov_deg", 180),
        ("vfov_deg", -1),
        ("vfov_deg", 181),
    ],
)
def test_invalid_fov_is_rejected(valid_payload, field, value):
    valid_payload[field] = value

    with pytest.raises(VisionContractError, match="FOV"):
        VisionTelemetry.from_dict(valid_payload)


def test_history_respects_configured_limit(valid_payload):
    service = VisionTelemetryService(history_size=2)
    first = dict(valid_payload, timestamp="2026-08-03T12:00:00Z")
    second = dict(valid_payload, timestamp="2026-08-03T12:00:01Z")
    third = dict(valid_payload, timestamp="2026-08-03T12:00:02Z")

    service.ingest(first)
    service.ingest(second)
    service.ingest(third)

    assert [item.timestamp for item in service.history()] == [
        "2026-08-03T12:00:01Z",
        "2026-08-03T12:00:02Z",
    ]


def test_history_size_must_be_positive():
    with pytest.raises(ValueError, match="history_size"):
        VisionTelemetryService(history_size=0)
