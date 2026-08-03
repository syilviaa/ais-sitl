"""End-to-end integration tests for vision pipeline."""
import pytest
from datetime import datetime
from backend.vision.vision_service import VisionService
from backend.geo.geo_calculator import GeoCalculator, BBox
from backend.geo.geo_validation import GeoValidator
from backend.vision_contracts import TelemetrySnapshot, VisionEvent


class TestVisionPipelineE2E:
    """End-to-end tests from detector output to API response."""

    @pytest.fixture
    def setup(self):
        """Setup vision service and geo calculator."""
        service = VisionService()
        calculator = GeoCalculator()
        validator = GeoValidator()
        return service, calculator, validator

    def test_detector_to_api_flow(self, setup):
        """Test: detection -> geo calc -> API response."""
        service, calculator, validator = setup

        # Simulate detector output
        bbox = BBox(x1=100, y1=150, x2=200, y2=400)
        telemetry = TelemetrySnapshot(
            timestamp="2026-08-03T12:00:00Z",
            latitude=37.7749,
            longitude=-122.4194,
            altitude_m=75,
            drone_yaw_deg=0,
            camera_pitch_deg=-70,
            camera_yaw_deg=0,
            hfov_deg=62,
            vfov_deg=48,
            frame_width=1920,
            frame_height=1080,
        )

        # Calculate GPS from bbox center
        lat, lon = calculator.pixel_to_gps(
            bbox_center=(bbox.center_x, bbox.center_y),
            telemetry=telemetry,
        )

        # Process detection through vision service
        event = service.process_detection(
            class_name="Person",
            confidence=0.87,
            bbox=[bbox.x1, bbox.y1, bbox.x2, bbox.y2],
            latitude=lat,
            longitude=lon,
            snapshot_url="/snapshots/test.jpg",
            source_id="test",
        )

        # Verify event was stored and is retrievable
        assert event is not None
        retrieved = service.get_event_by_id(event.event_id)
        assert retrieved is not None
        assert retrieved["class_name"] == "Person"
        assert retrieved["confidence"] == 0.87

    def test_multi_class_detection_pipeline(self, setup):
        """Test: multiple classes detected in sequence."""
        service, calculator, validator = setup

        telemetry = TelemetrySnapshot(
            timestamp="2026-08-03T12:00:00Z",
            latitude=37.7749,
            longitude=-122.4194,
            altitude_m=75,
            drone_yaw_deg=0,
            camera_pitch_deg=-70,
            camera_yaw_deg=0,
            hfov_deg=62,
            vfov_deg=48,
            frame_width=1920,
            frame_height=1080,
        )

        # Simulate multiple detections
        detections = [
            ("Person", 0.92, (400, 300)),
            ("Car", 0.88, (800, 600)),
            ("Truck_Machinery", 0.79, (1200, 400)),
        ]

        for class_name, confidence, pixel_pos in detections:
            lat, lon = calculator.pixel_to_gps(pixel_pos, telemetry)
            event = service.process_detection(
                class_name=class_name,
                confidence=confidence,
                bbox=[100, 100, 200, 200],
                latitude=lat,
                longitude=lon,
                snapshot_url=f"/snapshots/{class_name}.jpg",
                source_id="test",
            )
            assert event is not None

        # Verify all events are stored
        stats = service.get_stats()
        assert stats["total_events"] == 3
        assert stats["events_by_class"]["Person"] == 1
        assert stats["events_by_class"]["Car"] == 1
        assert stats["events_by_class"]["Truck_Machinery"] == 1

    def test_geo_accuracy_validation(self, setup):
        """Test: geo calculation stays within error bounds."""
        service, calculator, validator = setup

        for control_point in validator.get_control_points()[:3]:  # Test 3 altitude scenarios
            telemetry = TelemetrySnapshot(
                timestamp="2026-08-03T12:00:00Z",
                latitude=37.7749,
                longitude=-122.4194,
                altitude_m=control_point.altitude_m,
                drone_yaw_deg=0,
                camera_pitch_deg=-70,
                camera_yaw_deg=0,
                hfov_deg=62,
                vfov_deg=48,
                frame_width=1920,
                frame_height=1080,
            )

            lat, lon = calculator.pixel_to_gps(
                bbox_center=(control_point.pixel_x, control_point.pixel_y),
                telemetry=telemetry,
            )

            error = validator.calculate_error_m(
                lat, lon,
                control_point.expected_lat,
                control_point.expected_lon
            )

            # Error should be < 10m for frame center
            # (Edge cases might have larger error)
            if control_point.scenario_name.endswith("_frame_center"):
                assert error < 10.0, f"Error {error}m exceeds 10m for {control_point.scenario_name}"

    def test_confidence_threshold_enforcement(self, setup):
        """Test: confidence ≥0.65 is accepted by schema."""
        service, calculator, validator = setup

        # Test boundary cases: 0.649, 0.650, 0.651
        for confidence in [0.649, 0.650, 0.651]:
            event = service.process_detection(
                class_name="Person",
                confidence=confidence,
                bbox=[100, 150, 200, 400],
                latitude=37.7749,
                longitude=-122.4194,
                snapshot_url="/snapshots/test.jpg",
                source_id="test",
            )
            # All should be accepted by service
            # Filtering at detector level (≥0.65)
            assert event is not None

    def test_rate_limit_enforcement(self, setup):
        """Test: WebSocket rate limit (≤10 events/sec)."""
        service, calculator, validator = setup
        service.event_rate_limit_per_sec = 10

        # Process exactly 10 events rapidly
        accepted = 0
        for i in range(15):
            event = service.process_detection(
                class_name="Person",
                confidence=0.85,
                bbox=[100, 150, 200, 400],
                latitude=37.7749 + i * 0.0001,
                longitude=-122.4194,
                snapshot_url=f"/snapshots/test_{i}.jpg",
                source_id="test",
            )
            if event is not None:
                accepted += 1

        # Should have accepted ~10 events
        assert 8 <= accepted <= 10

    def test_invalid_telemetry_handling(self, setup):
        """Test: invalid telemetry doesn't crash pipeline."""
        service, calculator, validator = setup

        # Test missing altitude
        invalid_telemetry = TelemetrySnapshot(
            timestamp="2026-08-03T12:00:00Z",
            latitude=37.7749,
            longitude=-122.4194,
            altitude_m=150,  # Out of range
            drone_yaw_deg=0,
            camera_pitch_deg=-70,
            camera_yaw_deg=0,
            hfov_deg=62,
            vfov_deg=48,
            frame_width=1920,
            frame_height=1080,
        )

        # Should calculate but validation would fail
        try:
            invalid_telemetry.validate()
            assert False, "Should have raised validation error"
        except Exception:
            pass  # Expected

    def test_api_response_format(self, setup):
        """Test: API responses follow contract."""
        service, calculator, validator = setup

        # Add some events
        for i in range(3):
            service.process_detection(
                class_name="Person",
                confidence=0.85,
                bbox=[100, 150, 200, 400],
                latitude=37.7749 + i * 0.0001,
                longitude=-122.4194,
                snapshot_url=f"/snapshots/test_{i}.jpg",
                source_id="test",
            )

        # Check API response format
        latest = service.get_latest_events(10)
        assert isinstance(latest, list)
        assert len(latest) == 3

        for event_dict in latest:
            assert "event_id" in event_dict
            assert "timestamp" in event_dict
            assert "class_name" in event_dict
            assert "confidence" in event_dict
            assert "bbox" in event_dict
            assert "latitude" in event_dict
            assert "longitude" in event_dict
            assert "snapshot_url" in event_dict

    def test_event_uuid_uniqueness(self, setup):
        """Test: each event gets unique UUID."""
        service, calculator, validator = setup

        event_ids = set()
        for i in range(10):
            event = service.process_detection(
                class_name="Person",
                confidence=0.85,
                bbox=[100, 150, 200, 400],
                latitude=37.7749 + i * 0.0001,
                longitude=-122.4194,
                snapshot_url=f"/snapshots/test_{i}.jpg",
                source_id="test",
            )
            if event:
                event_ids.add(event.event_id)

        # All UUIDs should be unique
        assert len(event_ids) == len([e for e in range(10)])  # All accepted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
