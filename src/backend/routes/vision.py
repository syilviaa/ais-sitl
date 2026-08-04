"""REST API for vision events — Мерей (src/backend, no root backend/)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from src.backend.geo.geo_validation import GeoValidator

vision_bp = Blueprint("vision", __name__, url_prefix="/api/vision")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


@vision_bp.route("/latest", methods=["GET"])
def get_latest_events():
    limit = max(1, min(request.args.get("limit", 10, type=int), 100))
    events = current_app.vision_service.get_latest_events(limit)
    return jsonify(
        {"success": True, "timestamp": _utc_now(), "events": events, "count": len(events)}
    )


@vision_bp.route("/events", methods=["GET"])
def get_all_events():
    class_name = request.args.get("class")
    service = current_app.vision_service
    if class_name:
        if class_name not in ("Person", "Car", "Truck_Machinery"):
            return jsonify({"success": False, "error": f"Invalid class: {class_name}"}), 400
        events = service.get_events_by_class(class_name)
    else:
        events = [e.to_dict() for e in service.store.get_all()]
    return jsonify(
        {"success": True, "timestamp": _utc_now(), "events": events, "count": len(events)}
    )


@vision_bp.route("/event/<event_id>", methods=["GET"])
def get_event(event_id):
    event = current_app.vision_service.get_event_by_id(event_id)
    if not event:
        return jsonify({"success": False, "error": "Event not found"}), 404
    return jsonify({"success": True, "event": event})


@vision_bp.route("/stats", methods=["GET"])
def get_stats():
    return jsonify(
        {
            "success": True,
            "timestamp": _utc_now(),
            "stats": current_app.vision_service.get_stats(),
        }
    )


@vision_bp.route("/errors", methods=["GET"])
def get_errors():
    limit = max(1, min(request.args.get("limit", 50, type=int), 200))
    errors = current_app.vision_service.get_errors(limit=limit)
    return jsonify(
        {"success": True, "timestamp": _utc_now(), "errors": errors, "count": len(errors)}
    )


@vision_bp.route("/geo/report", methods=["GET"])
def geo_report():
    report = GeoValidator.run_mae_report()
    return jsonify({"success": True, "timestamp": _utc_now(), "report": report})


@vision_bp.route("/snapshot/<event_id>", methods=["GET"])
def get_snapshot(event_id):
    event = current_app.vision_service.get_event_by_id(event_id)
    if not event:
        return jsonify({"success": False, "error": "Event not found"}), 404
    snapshot_url = event.get("snapshot_url")
    if not snapshot_url:
        current_app.vision_service.log_error(
            "snapshot_unavailable", f"No snapshot_url for {event_id}"
        )
        return jsonify({"success": False, "error": "Snapshot not available"}), 404

    if snapshot_url.startswith("http://") or snapshot_url.startswith("https://"):
        return jsonify({"success": True, "snapshot_url": snapshot_url})

    # Relative API path like /api/vision/snapshots/<id>.jpg
    if snapshot_url.startswith("/api/vision/snapshots/"):
        name = snapshot_url.rsplit("/", 1)[-1]
        root = Path(__file__).resolve().parents[3]
        candidate = root / "snapshots" / name
        if candidate.is_file():
            return send_file(candidate, mimetype="image/jpeg")

    if os.path.exists(snapshot_url):
        return send_file(snapshot_url, mimetype="image/jpeg")

    current_app.vision_service.log_error(
        "snapshot_unavailable",
        f"Snapshot file missing: {snapshot_url}",
        {"event_id": event_id},
    )
    return jsonify({"success": False, "error": "Snapshot not available"}), 404


@vision_bp.route("/ingest", methods=["POST"])
def ingest_event():
    """
    Test/demo ingest of a VisionEvent (detector → service handoff).
    Does not invent GPS: latitude/longitude required.
    """
    payload = request.get_json(silent=True) or {}
    service = current_app.vision_service
    handler = getattr(current_app, "vision_socket_handler", None)

    telemetry_ts = payload.get("telemetry_timestamp")
    if telemetry_ts is not None and not service.reject_stale_or_invalid_telemetry(telemetry_ts):
        return jsonify({"success": False, "error": "stale_or_invalid_telemetry", "alert": False}), 422

    event = service.create_and_ingest(
        class_name=payload.get("class_name"),
        confidence=payload.get("confidence"),
        bbox=payload.get("bbox"),
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        snapshot_url=payload.get("snapshot_url") or "",
        source_id=payload.get("source_id") or "ingest",
        event_id=payload.get("event_id"),
        timestamp=payload.get("timestamp"),
    )
    if event is None:
        return jsonify(
            {
                "success": False,
                "alert": False,
                "error": "rejected",
                "errors": service.get_errors(limit=5),
            }
        ), 422

    data = event.to_dict()
    if handler is not None:
        handler.broadcast_detection(data)
        handler.broadcast_alert(data)
    return jsonify({"success": True, "alert": True, "event": data}), 201


@vision_bp.route("/health", methods=["GET"])
def health():
    stats = current_app.vision_service.get_stats()
    return jsonify(
        {
            "success": True,
            "status": "healthy",
            "timestamp": _utc_now(),
            "runtime": stats.get("runtime"),
        }
    )


@vision_bp.route("/runtime", methods=["POST"])
def set_runtime():
    """Diagnostic: set camera/model/stream flags for stress tests."""
    payload = request.get_json(silent=True) or {}
    current_app.vision_service.set_runtime_status(
        camera_available=payload.get("camera_available"),
        model_loaded=payload.get("model_loaded"),
        stream_ok=payload.get("stream_ok"),
    )
    return jsonify({"success": True, "stats": current_app.vision_service.get_stats()})
