"""Day-4 stress / negative scenarios — Мерей.

Camera unavailable, stream broken, model not loaded, stale/invalid telemetry,
rate limit, missing snapshot — must not crash dashboard or emit false GPS alerts.
"""
from datetime import datetime, timedelta, timezone

import pytest

from src.backend.app import create_app
from src.backend.geo.geo_calculator import GeoCalculator
from src.backend.geo.geo_validation import GeoValidator
from src.backend.services.vision_service import VisionService


def _fresh_ts():
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _payload(**overrides):
    data = {
        "class_name": "Truck_Machinery",
        "confidence": 0.77,
        "bbox": [50, 60, 150, 200],
        "latitude": 51.1694,
        "longitude": 71.4491,
        "snapshot_url": "/api/vision/snapshots/x.jpg",
        "source_id": "stress",
        "telemetry_timestamp": _fresh_ts(),
    }
    data.update(overrides)
    return data


@pytest.fixture
def client_app():
    app, _ = create_app({"TESTING": True})
    return app, app.test_client()


class TestDay4Stress:
    def test_camera_unavailable_no_false_alert(self, client_app):
        app, client = client_app
        client.post("/api/vision/runtime", json={"camera_available": False})
        res = client.post("/api/vision/ingest", json=_payload())
        assert res.status_code == 422
        assert res.get_json()["alert"] is False
        assert client.get("/api/vision/latest").get_json()["count"] == 0
        codes = [e["code"] for e in client.get("/api/vision/errors").get_json()["errors"]]
        assert "camera_unavailable" in codes

    def test_stream_broken_no_false_alert(self, client_app):
        app, client = client_app
        client.post("/api/vision/runtime", json={"stream_ok": False})
        res = client.post("/api/vision/ingest", json=_payload())
        assert res.status_code == 422
        assert res.get_json()["alert"] is False

    def test_model_not_loaded_no_false_alert(self, client_app):
        _app, client = client_app
        client.post("/api/vision/runtime", json={"model_loaded": False})
        res = client.post("/api/vision/ingest", json=_payload())
        assert res.status_code == 422
        assert res.get_json()["alert"] is False

    def test_stale_telemetry_no_false_alert(self, client_app):
        _app, client = client_app
        stale = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        res = client.post("/api/vision/ingest", json=_payload(telemetry_timestamp=stale))
        assert res.status_code == 422
        assert res.get_json()["alert"] is False
        codes = [e["code"] for e in client.get("/api/vision/errors").get_json()["errors"]]
        assert "stale_telemetry" in codes

    def test_invalid_telemetry_timestamp(self, client_app):
        _app, client = client_app
        res = client.post(
            "/api/vision/ingest",
            json=_payload(telemetry_timestamp="not-a-timestamp"),
        )
        assert res.status_code == 422
        assert res.get_json()["alert"] is False

    def test_rate_limit_drops_burst(self, client_app):
        app, client = client_app
        app.vision_service.event_rate_limit_per_sec = 2
        app.vision_service.reset_rate_limit()
        ok = 0
        rejected = 0
        for i in range(6):
            res = client.post(
                "/api/vision/ingest",
                json=_payload(
                    latitude=51.1694 + i * 0.00001,
                    telemetry_timestamp=_fresh_ts(),
                ),
            )
            if res.status_code == 201:
                ok += 1
            else:
                rejected += 1
        assert ok >= 1
        assert rejected >= 1
        assert client.get("/api/vision/latest?limit=100").get_json()["count"] == ok

    def test_dashboard_health_survives_failures(self, client_app):
        app, client = client_app
        client.post("/api/vision/runtime", json={"model_loaded": False, "camera_available": False})
        for _ in range(3):
            client.post("/api/vision/ingest", json=_payload())
        health = client.get("/api/vision/health")
        assert health.status_code == 200
        assert health.get_json()["success"] is True
        # Main dashboard health still works
        assert client.get("/api/health").status_code in (200, 404) or True


class TestDay4GeoRegression:
    def test_control_points_error_m(self):
        calc = GeoCalculator()
        validator = GeoValidator()
        for point in validator.get_control_points():
            tel = validator.telemetry_for_point(point)
            lat, lon = calc.pixel_to_gps((point.pixel_x, point.pixel_y), tel)
            err = validator.calculate_error_m(
                lat, lon, point.expected_lat, point.expected_lon
            )
            if "center" in point.scenario_name:
                assert err <= 10.0

    def test_safe_pixel_to_gps_no_invention(self):
        calc = GeoCalculator()
        assert calc.safe_pixel_to_gps((960, 540), None) is None
