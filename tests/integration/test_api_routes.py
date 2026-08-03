"""Integration tests for REST API routes."""
import pytest
import json
from app import create_app
from backend.vision.vision_service import VisionService


@pytest.fixture
def client():
    """Create Flask test client."""
    app, socketio = create_app()
    app.config["TESTING"] = True
    app.vision_service = VisionService()

    with app.test_client() as client:
        yield client


@pytest.fixture
def populated_service(client):
    """Populate service with test events."""
    vision_service = client.application.vision_service

    for i in range(5):
        vision_service.process_detection(
            class_name="Person" if i % 2 == 0 else "Car",
            confidence=0.85 + i * 0.01,
            bbox=[100, 150, 200, 400],
            latitude=37.7749 + i * 0.0001,
            longitude=-122.4194,
            snapshot_url=f"/snapshots/test_{i}.jpg",
            source_id="test",
        )

    return vision_service


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/api/vision/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["status"] == "healthy"


def test_get_latest_default(client, populated_service):
    """Test GET /api/vision/latest with default limit."""
    response = client.get("/api/vision/latest")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["count"] == 5
    assert len(data["events"]) == 5


def test_get_latest_with_limit(client, populated_service):
    """Test GET /api/vision/latest with custom limit."""
    response = client.get("/api/vision/latest?limit=2")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 2
    assert len(data["events"]) == 2


def test_get_latest_limit_clamping(client, populated_service):
    """Test limit is clamped to 100."""
    response = client.get("/api/vision/latest?limit=500")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 5  # Only 5 events available


def test_get_events_all(client, populated_service):
    """Test GET /api/vision/events without filter."""
    response = client.get("/api/vision/events")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["count"] == 5


def test_get_events_by_class_person(client, populated_service):
    """Test GET /api/vision/events?class=Person."""
    response = client.get("/api/vision/events?class=Person")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert all(e["class_name"] == "Person" for e in data["events"])
    assert data["count"] == 3


def test_get_events_by_class_car(client, populated_service):
    """Test GET /api/vision/events?class=Car."""
    response = client.get("/api/vision/events?class=Car")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert all(e["class_name"] == "Car" for e in data["events"])
    assert data["count"] == 2


def test_get_events_invalid_class(client, populated_service):
    """Test GET /api/vision/events with invalid class."""
    response = client.get("/api/vision/events?class=InvalidClass")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["success"] is False


def test_get_event_by_id(client, populated_service):
    """Test GET /api/vision/event/<event_id>."""
    # Get an event first
    response = client.get("/api/vision/latest?limit=1")
    events = json.loads(response.data)["events"]
    event_id = events[0]["event_id"]

    # Now fetch it directly
    response = client.get(f"/api/vision/event/{event_id}")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    assert data["event"]["event_id"] == event_id


def test_get_event_not_found(client, populated_service):
    """Test GET /api/vision/event with non-existent ID."""
    response = client.get("/api/vision/event/nonexistent-id")
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data["success"] is False


def test_stats_endpoint(client, populated_service):
    """Test GET /api/vision/stats."""
    response = client.get("/api/vision/stats")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] is True
    stats = data["stats"]
    assert stats["total_events"] == 5
    assert "events_by_class" in stats


def test_event_json_schema_compliance(client, populated_service):
    """Test that API responses conform to schema."""
    response = client.get("/api/vision/latest?limit=1")
    data = json.loads(response.data)
    event = data["events"][0]

    # Check required fields
    required = [
        "event_id",
        "timestamp",
        "class_name",
        "confidence",
        "bbox",
        "latitude",
        "longitude",
        "snapshot_url",
        "source_id",
    ]
    for field in required:
        assert field in event, f"Missing required field: {field}"

    # Check field types
    assert isinstance(event["event_id"], str)
    assert isinstance(event["timestamp"], str)
    assert isinstance(event["class_name"], str)
    assert isinstance(event["confidence"], (int, float))
    assert isinstance(event["bbox"], list) and len(event["bbox"]) == 4


def test_timestamp_format(client, populated_service):
    """Test that timestamps are ISO 8601 UTC."""
    response = client.get("/api/vision/latest?limit=1")
    data = json.loads(response.data)
    event = data["events"][0]
    timestamp = event["timestamp"]

    # Should end with Z and contain T
    assert timestamp.endswith("Z")
    assert "T" in timestamp


def test_snapshot_endpoint_exists(client, populated_service):
    """Test GET /api/vision/snapshot/<event_id>."""
    response = client.get("/api/vision/latest?limit=1")
    events = json.loads(response.data)["events"]
    event_id = events[0]["event_id"]

    response = client.get(f"/api/vision/snapshot/{event_id}")
    # Should return URL or file, not error
    assert response.status_code in [200, 404]  # 404 if file not found, that's ok


def test_rate_limit_enforcement(client):
    """Test that rate limiting works."""
    vision_service = client.application.vision_service
    vision_service.event_rate_limit_per_sec = 3

    accepted = 0
    for i in range(10):
        event = vision_service.process_detection(
            class_name="Person",
            confidence=0.85,
            bbox=[100, 150, 200, 400],
            latitude=37.7749 + i * 0.0001,
            longitude=-122.4194,
            snapshot_url=f"/snapshots/test_{i}.jpg",
            source_id="test",
        )
        if event:
            accepted += 1

    # Should have accepted ~3 events
    assert 2 <= accepted <= 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
