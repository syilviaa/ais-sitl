"""VisionService unit + API tests (Мерей)."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.backend.app import create_app
from src.backend.services.vision_service import VisionService


def _valid_payload(**overrides):
    data = {
        "class_name": "Person",
        "confidence": 0.88,
        "bbox": [100, 120, 200, 320],
        "latitude": 51.1694,
        "longitude": 71.4491,
        "snapshot_url": "/api/vision/snapshots/demo.jpg",
        "source_id": "test",
        "telemetry_timestamp": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    data.update(overrides)
    return data


@pytest.fixture
def app_client():
    app, _socketio = create_app({"TESTING": True})
    return app, app.test_client()


class TestVisionService:
    def test_ingest_ok(self):
        service = VisionService()
        event = service.create_and_ingest(**{
            k: v for k, v in _valid_payload().items() if k != "telemetry_timestamp"
        })
        assert event is not None
        assert service.get_event_by_id(event.event_id) is not None

    def test_model_not_loaded_no_alert(self):
        service = VisionService()
        service.set_runtime_status(model_loaded=False)
        event = service.create_and_ingest(
            class_name="Person",
            confidence=0.9,
            bbox=[1, 2, 10, 20],
            latitude=51.1,
            longitude=71.4,
            snapshot_url="/s.jpg",
            source_id="t",
        )
        assert event is None
        assert any(e["code"] == "model_not_loaded" for e in service.get_errors())
        assert service.store.get_all() == []

    def test_stale_telemetry(self):
        service = VisionService()
        old = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        assert service.reject_stale_or_invalid_telemetry(old) is False
        assert any(e["code"] == "stale_telemetry" for e in service.get_errors())


class TestVisionApi:
    def test_health(self, app_client):
        _app, client = app_client
        res = client.get("/api/vision/health")
        assert res.status_code == 200
        assert res.get_json()["success"] is True

    def test_ingest_and_latest(self, app_client):
        _app, client = app_client
        res = client.post("/api/vision/ingest", json=_valid_payload())
        assert res.status_code == 201
        body = res.get_json()
        assert body["alert"] is True
        latest = client.get("/api/vision/latest").get_json()
        assert latest["count"] >= 1

    def test_ingest_rejects_missing_gps(self, app_client):
        _app, client = app_client
        payload = _valid_payload()
        payload["latitude"] = None
        res = client.post("/api/vision/ingest", json=payload)
        assert res.status_code == 422
        assert res.get_json()["alert"] is False

    def test_snapshot_unavailable(self, app_client):
        app, client = app_client
        event = app.vision_service.create_and_ingest(
            class_name="Car",
            confidence=0.8,
            bbox=[10, 10, 40, 40],
            latitude=51.1,
            longitude=71.4,
            snapshot_url="/tmp/missing-cv-snapshot.jpg",
            source_id="t",
            event_id=str(uuid4()),
        )
        assert event is not None
        res = client.get(f"/api/vision/snapshot/{event.event_id}")
        assert res.status_code == 404

    def test_geo_report(self, app_client):
        _app, client = app_client
        res = client.get("/api/vision/geo/report")
        assert res.status_code == 200
        assert "mae_m" in res.get_json()["report"]

    def test_errors_endpoint(self, app_client):
        app, client = app_client
        app.vision_service.log_error("test", "hello")
        res = client.get("/api/vision/errors")
        assert res.status_code == 200
        assert res.get_json()["count"] >= 1
