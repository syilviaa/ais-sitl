"""Canonical REST and Socket.IO integration tests for CV events."""

from uuid import uuid4

import numpy as np

from src.backend.app import create_app
from src.backend.services.vision_contracts import VisionEvent
from src.backend.services.vision_event_service import (
    SlidingWindowRateLimiter,
    VisionEventService,
)
from src.vision.models import (
    BoundingBox,
    Detection,
    DetectorResult,
    VisionClass,
)
from src.vision.pipeline import VisionPipeline


def make_event(class_name="Person"):
    event_id = str(uuid4())
    return VisionEvent(
        event_id=event_id,
        timestamp="2026-08-04T10:00:00.000Z",
        class_name=class_name,
        confidence=0.85,
        bbox=(10.0, 20.0, 100.0, 200.0),
        latitude=51.1694,
        longitude=71.4491,
        snapshot_url=f"/api/vision/snapshots/{event_id}.jpg",
        source_id="day4-demo.mp4",
    )


def test_event_service_keeps_latest_events_and_class_filter():
    service = VisionEventService(max_events=2)
    person = service.add(make_event("Person"))
    car = service.add(make_event("Car"))
    truck = service.add(make_event("Truck_Machinery"))

    assert [event.event_id for event in service.latest()] == [
        truck.event_id,
        car.event_id,
    ]
    assert service.get(person.event_id) is None
    assert service.all("Car") == [car]


def test_socket_rate_limiter_allows_exactly_ten_events_per_second():
    current_time = [0.0]
    limiter = SlidingWindowRateLimiter(
        limit=10,
        clock=lambda: current_time[0],
    )

    assert all(limiter.allow() for _ in range(10))
    assert limiter.allow() is False
    current_time[0] = 1.0
    assert limiter.allow() is True


def test_vision_event_reaches_rest_and_socket_clients(tmp_path):
    app, socketio = create_app({
        "TESTING": True,
        "VISION_SNAPSHOT_DIR": str(tmp_path),
    })
    http = app.test_client()
    socket = socketio.test_client(app)
    socket.get_received()
    socket.emit("subscribe_detections")
    socket.emit("subscribe_alerts")
    socket.get_received()
    event = make_event()

    response = http.post("/api/vision/events", json=event.to_dict())

    assert response.status_code == 201
    latest = http.get("/api/vision/latest").get_json()
    assert latest["events"][0]["event_id"] == event.event_id
    received = socket.get_received()
    names = [message["name"] for message in received]
    assert "vision_detection" in names
    assert "vision_alert" in names
    assert http.get(
        f"/api/vision/snapshots/{event.event_id}.jpg"
    ).status_code == 404
    socket.disconnect()


def test_invalid_event_is_rejected_without_false_alert(tmp_path):
    app, _ = create_app({
        "TESTING": True,
        "VISION_SNAPSHOT_DIR": str(tmp_path),
    })
    http = app.test_client()
    payload = make_event().to_dict()
    payload["latitude"] = None

    response = http.post("/api/vision/events", json=payload)

    assert response.status_code == 400
    assert http.get("/api/vision/latest").get_json()["events"] == []


def test_frame_reaches_snapshot_rest_and_socket_end_to_end(tmp_path):
    detection = Detection(
        VisionClass.CAR,
        0.88,
        BoundingBox(20, 10, 80, 70),
    )

    class Detector:
        def detect(self, frame, source_id="unknown"):
            return DetectorResult(
                frame_id="frame-day4",
                timestamp="2026-08-04T10:00:00.000Z",
                frame_width=200,
                frame_height=100,
                detections=[detection],
                source_id=source_id,
            )

    class GeoLocator:
        def pixel_to_gps(self, bbox_center, telemetry):
            return 51.1694, 71.4491

    pipeline = VisionPipeline(Detector(), GeoLocator(), tmp_path)
    app, socketio = create_app({
        "TESTING": True,
        "VISION_SNAPSHOT_DIR": str(tmp_path),
    })
    http = app.test_client()
    socket = socketio.test_client(app)
    socket.get_received()
    socket.emit("subscribe_detections")
    socket.get_received()

    events = pipeline.process_frame(
        np.zeros((100, 200, 3), dtype=np.uint8),
        telemetry=object(),
        source_id="day4-e2e.mp4",
    )
    app.publish_vision_event(events[0])

    latest = http.get("/api/vision/latest").get_json()["events"][0]
    assert latest["event_id"] == events[0].event_id
    assert latest["class_name"] == "Car"
    assert http.get(events[0].snapshot_url).status_code == 200
    assert any(
        message["name"] == "vision_detection"
        for message in socket.get_received()
    )
    socket.disconnect()
