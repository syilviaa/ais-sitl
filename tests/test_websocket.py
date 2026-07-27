"""SocketIO telemetry tests without a PX4 SITL instance."""

import asyncio
import json
import time

import pytest
from socketio import packet

from src.backend.app import create_app
from src.backend.services.telemetry_service import TelemetryServiceAPI


class FakeTelemetryService:
    """Minimal service double that uses the app's real SocketIO callback."""

    def __init__(self):
        self.clients = set()
        self.callback = None

    def register_client(self, client_id):
        self.clients.add(client_id)

    def unregister_client(self, client_id):
        self.clients.discard(client_id)

    def set_broadcast_callback(self, callback):
        self.callback = callback

    def emit_snapshot(self, payload):
        self.callback(payload)


@pytest.fixture
def app_and_socketio():
    app, socketio = create_app({"TESTING": True})

    def capture_eio_packet(eio_sid, eio_packet):
        """Bridge python-socketio packets to the Flask-SocketIO test client."""
        socketio.server._send_packet(
            eio_sid, packet.Packet(encoded_packet=eio_packet.data)
        )

    socketio.server._send_eio_packet = capture_eio_packet
    service = FakeTelemetryService()
    app.telemetry_service = service
    app.configure_telemetry_service(service)
    return app, socketio, service


def received_events(client, name):
    """Return received events with the requested SocketIO event name."""
    return [event for event in client.get_received() if event["name"] == name]


def test_client_receives_connected_event(app_and_socketio):
    app, socketio, _service = app_and_socketio
    client = socketio.test_client(app)
    time.sleep(0.01)
    assert received_events(client, "connected")


def test_start_telemetry_subscribes_and_receives_json_payload(
    app_and_socketio,
):
    app, socketio, service = app_and_socketio
    client = socketio.test_client(app)
    client.get_received()
    client.emit("start_telemetry")
    assert received_events(client, "telemetry_started")
    assert len(service.clients) == 1

    payload = {"timestamp": 1.0, "position": {"lat": 47.3977, "lon": 8.5455}}
    service.emit_snapshot(payload)
    events = received_events(client, "telemetry")
    assert events[0]["args"][0] == payload
    json.dumps(events[0]["args"][0], allow_nan=False)


def test_unsubscribed_client_does_not_receive_telemetry(app_and_socketio):
    app, socketio, service = app_and_socketio
    subscribed = socketio.test_client(app)
    unsubscribed = socketio.test_client(app)
    subscribed.get_received()
    unsubscribed.get_received()
    subscribed.emit("start_telemetry")
    subscribed.get_received()
    service.emit_snapshot({"timestamp": 1.0, "position": {"lat": 47.4}})
    assert received_events(subscribed, "telemetry")
    assert not received_events(unsubscribed, "telemetry")


def test_stop_telemetry_prevents_further_delivery(app_and_socketio):
    app, socketio, service = app_and_socketio
    client = socketio.test_client(app)
    client.get_received()
    client.emit("start_telemetry")
    client.get_received()
    client.emit("stop_telemetry")
    assert received_events(client, "telemetry_stopped")
    service.emit_snapshot({"timestamp": 1.0})
    assert not received_events(client, "telemetry")


def test_disconnect_removes_subscription(app_and_socketio):
    app, socketio, service = app_and_socketio
    client = socketio.test_client(app)
    client.get_received()
    client.emit("start_telemetry")
    assert len(service.clients) == 1
    client.disconnect()
    assert not service.clients


def test_missing_service_emits_pending_telemetry_started():
    app, socketio = create_app({"TESTING": True})
    client = socketio.test_client(app)
    client.get_received()
    client.emit("start_telemetry")
    started = received_events(client, "telemetry_started")
    assert started
    payload = started[0]["args"][0]
    assert payload.get("pending") is True
    assert "initialize" in payload.get("message", "").lower()


@pytest.mark.asyncio
async def test_service_broadcast_rate_is_limited_to_ten_hz():
    service = TelemetryServiceAPI()
    service.clients.add("client-1")
    payloads = []
    service.set_broadcast_callback(payloads.append)
    await service._broadcast_snapshot({"timestamp": 1.0})
    await service._broadcast_snapshot({"timestamp": 2.0})
    await asyncio.sleep(0.11)
    await service._broadcast_snapshot({"timestamp": 3.0})
    assert payloads == [{"timestamp": 1.0}, {"timestamp": 3.0}]
