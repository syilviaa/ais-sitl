import pytest
from datetime import datetime
from backend.vision_contracts import VisionEvent, TelemetrySnapshot


class TestTelemetrySnapshot:
    def test_create_and_convert_to_dict(self):
        telemetry = TelemetrySnapshot(
            timestamp="2026-08-03T12:00:00Z",
            latitude=37.7749,
            longitude=-122.4194,
            altitude_m=75,
            drone_yaw_deg=45,
            camera_pitch_deg=-70,
            camera_yaw_deg=0,
            hfov_deg=62,
            vfov_deg=48,
            frame_width=1920,
            frame_height=1080,
        )
        data = telemetry.to_dict()
        assert data["latitude"] == 37.7749
        assert data["altitude_m"] == 75

    def test_from_dict(self):
        data = {
            "timestamp": "2026-08-03T12:00:00Z",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "altitude_m": 75,
            "drone_yaw_deg": 45,
            "camera_pitch_deg": -70,
            "camera_yaw_deg": 0,
            "hfov_deg": 62,
            "vfov_deg": 48,
            "frame_width": 1920,
            "frame_height": 1080,
        }
        telemetry = TelemetrySnapshot.from_dict(data)
        assert telemetry.latitude == 37.7749
        assert telemetry.altitude_m == 75


class TestVisionEvent:
    def test_create_with_factory(self):
        event = VisionEvent.create(
            class_name="Person",
            confidence=0.87,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.class_name == "Person"
        assert event.confidence == 0.87

    def test_event_id_is_uuid(self):
        event = VisionEvent.create(
            class_name="Person",
            confidence=0.87,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        uuid_parts = event.event_id.split("-")
        assert len(uuid_parts) == 5

    def test_timestamp_is_iso8601_utc(self):
        event = VisionEvent.create(
            class_name="Person",
            confidence=0.87,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        assert event.timestamp.endswith("Z")
        assert "T" in event.timestamp

    def test_to_dict_excludes_none(self):
        event = VisionEvent.create(
            class_name="Person",
            confidence=0.87,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        data = event.to_dict()
        assert "track_id" not in data or data["track_id"] is None

    def test_with_optional_fields(self):
        event = VisionEvent.create(
            class_name="Person",
            confidence=0.87,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
            processing_latency_ms=45,
            track_id="track_001",
        )
        assert event.processing_latency_ms == 45
        assert event.track_id == "track_001"

    def test_class_names_valid(self):
        for class_name in ["Person", "Car", "Truck_Machinery"]:
            event = VisionEvent.create(
                class_name=class_name,
                confidence=0.87,
                bbox=[100, 150, 200, 400],
                latitude=37.7749,
                longitude=-122.4194,
                snapshot_url="/snapshots/test.jpg",
                source_id="test",
            )
            assert event.class_name == class_name

    def test_confidence_range(self):
        event = VisionEvent.create(
            class_name="Person",
            confidence=0.65,  # Minimum acceptable confidence
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        assert event.confidence == 0.65

    def test_bbox_format(self):
        event = VisionEvent.create(
            class_name="Person",
            confidence=0.87,
            bbox=[100, 150, 200, 400],
            latitude=37.7749,
            longitude=-122.4194,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )
        assert len(event.bbox) == 4
        assert event.bbox[0] == 100
        assert event.bbox[2] == 200

    def test_from_dict(self):
        data = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2026-08-03T12:00:00Z",
            "class_name": "Person",
            "confidence": 0.87,
            "bbox": [100, 150, 200, 400],
            "latitude": 37.7749,
            "longitude": -122.4194,
            "snapshot_url": "/snapshots/test.jpg",
            "source_id": "test",
        }
        event = VisionEvent.from_dict(data)
        assert event.event_id == "550e8400-e29b-41d4-a716-446655440000"
        assert event.class_name == "Person"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
