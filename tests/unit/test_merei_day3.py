"""Day 2–3 tests: geo MAE, missing telemetry, schema, failures, no false GPS."""
import pytest

from backend.geo.geo_calculator import GeoCalculator
from backend.geo.geo_validation import GeoValidator
from backend.vision.event_pipeline import VisionEventPipeline
from backend.vision.vision_service import VisionService
from backend.vision_contracts import TelemetrySnapshot, VisionEvent


def _telemetry(**overrides):
    data = dict(
        timestamp="2026-08-03T12:00:00Z",
        latitude=37.7749,
        longitude=-122.4194,
        altitude_m=75,
        drone_yaw_deg=0,
        camera_pitch_deg=-90,
        camera_yaw_deg=0,
        hfov_deg=62,
        vfov_deg=48,
        frame_width=1920,
        frame_height=1080,
    )
    data.update(overrides)
    return TelemetrySnapshot(**data)


class TestGeoMaeReport:
    def test_mae_report_structure(self):
        report = GeoValidator.run_mae_report()
        assert "mae_m" in report
        assert "max_error_m" in report
        assert "center_mae_m" in report
        assert len(report["scenarios"]) >= 9  # 3 alts × 3 pitches centers + edges
        altitudes = {s["altitude_m"] for s in report["scenarios"]}
        assert {50.0, 75.0, 100.0} <= altitudes

    def test_center_points_within_10m(self):
        report = GeoValidator.run_mae_report()
        assert report["pass_center_max_10m"] is True
        assert report["center_mae_m"] <= 10.0


class TestGeoRejectsBadTelemetry:
    def test_altitude_out_of_range(self):
        calc = GeoCalculator()
        with pytest.raises(ValueError):
            calc.pixel_to_gps((960, 540), _telemetry(altitude_m=20))

    def test_safe_returns_none_on_missing(self):
        calc = GeoCalculator()
        assert calc.safe_pixel_to_gps((960, 540), None) is None

    def test_safe_returns_none_on_bad_altitude(self):
        calc = GeoCalculator()
        assert calc.safe_pixel_to_gps((960, 540), _telemetry(altitude_m=200)) is None


class TestPipelineNoFalseGps:
    def test_missing_telemetry_no_event(self):
        service = VisionService()
        pipeline = VisionEventPipeline(service=service)
        event = pipeline.process(
            class_name="Person",
            confidence=0.9,
            bbox=[100, 100, 200, 300],
            telemetry=None,
            snapshot_url="/snapshots/x.jpg",
            source_id="test",
        )
        assert event is None
        assert service.store.get_all_events() == []
        assert any(e["code"] == "missing_telemetry" for e in service.get_errors())

    def test_invalid_altitude_no_event(self):
        service = VisionService()
        pipeline = VisionEventPipeline(service=service)
        event = pipeline.process(
            class_name="Car",
            confidence=0.8,
            bbox=[100, 100, 200, 300],
            telemetry=_telemetry(altitude_m=10),
            snapshot_url="/snapshots/x.jpg",
            source_id="test",
        )
        assert event is None
        assert service.store.get_all_events() == []

    def test_valid_pipeline_creates_schema_ok_event(self):
        service = VisionService()
        pipeline = VisionEventPipeline(service=service)
        event = pipeline.process(
            class_name="Person",
            confidence=0.88,
            bbox=[860, 440, 1060, 640],
            telemetry=_telemetry(),
            snapshot_url="/snapshots/ok.jpg",
            source_id="local_file",
        )
        assert event is not None
        event.validate()
        assert event.timestamp.endswith("Z")
        assert event.latitude is not None


class TestVisionServiceFailures:
    def test_model_not_loaded(self):
        service = VisionService()
        service.set_runtime_status(model_loaded=False)
        result = service.process_detection(
            class_name="Person",
            confidence=0.9,
            bbox=[1, 2, 3, 4],
            latitude=37.77,
            longitude=-122.41,
            snapshot_url="/s.jpg",
            source_id="t",
        )
        assert result is None
        assert any(e["code"] == "model_not_loaded" for e in service.get_errors())

    def test_camera_unavailable(self):
        service = VisionService()
        service.set_runtime_status(camera_available=False)
        result = service.process_detection(
            class_name="Person",
            confidence=0.9,
            bbox=[1, 2, 3, 4],
            latitude=37.77,
            longitude=-122.41,
            snapshot_url="/s.jpg",
            source_id="t",
        )
        assert result is None
        assert any(e["code"] == "camera_unavailable" for e in service.get_errors())

    def test_missing_gps_rejected(self):
        service = VisionService()
        result = service.process_detection(
            class_name="Person",
            confidence=0.9,
            bbox=[1, 2, 3, 4],
            latitude=None,
            longitude=None,
            snapshot_url="/s.jpg",
            source_id="t",
        )
        assert result is None
        assert any(e["code"] == "missing_gps" for e in service.get_errors())

    def test_schema_rejects_bad_class(self):
        service = VisionService()
        result = service.process_detection(
            class_name="Bird",
            confidence=0.9,
            bbox=[1, 2, 3, 4],
            latitude=37.77,
            longitude=-122.41,
            snapshot_url="/s.jpg",
            source_id="t",
        )
        assert result is None
        assert any(e["code"] == "schema_invalid" for e in service.get_errors())


class TestSnapshotUnavailableApi:
    def test_snapshot_404(self):
        from app import create_app

        app, _socketio = create_app()
        client = app.test_client()

        event = VisionEvent.create(
            class_name="Person",
            confidence=0.9,
            bbox=[1, 2, 3, 4],
            latitude=37.77,
            longitude=-122.41,
            snapshot_url="/tmp/does-not-exist-cv-mvp.jpg",
            source_id="t",
        )
        app.vision_service.store.add_event(event)

        res = client.get(f"/api/vision/snapshot/{event.event_id}")
        assert res.status_code == 404
        body = res.get_json()
        assert body["success"] is False

    def test_errors_endpoint(self):
        from app import create_app

        app, _socketio = create_app()
        client = app.test_client()
        app.vision_service.log_error("test", "hello")
        res = client.get("/api/vision/errors")
        assert res.status_code == 200
        assert res.get_json()["count"] >= 1

    def test_geo_report_endpoint(self):
        from app import create_app

        app, _socketio = create_app()
        client = app.test_client()
        res = client.get("/api/vision/geo/report")
        assert res.status_code == 200
        report = res.get_json()["report"]
        assert "mae_m" in report
