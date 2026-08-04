"""REST endpoints for recent CV events and their JPEG snapshots."""

from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file

from src.backend.services.vision_contracts import (
    VisionContractError,
    VisionEvent,
)


vision_bp = Blueprint("vision", __name__, url_prefix="/api/vision")
VISION_CLASSES = {"Person", "Car", "Truck_Machinery"}


def _utc_now():
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _events_response(events):
    payload = [event.to_dict() for event in events]
    return jsonify({
        "success": True,
        "timestamp": _utc_now(),
        "events": payload,
        "count": len(payload),
    })


@vision_bp.get("/latest")
def latest():
    limit = request.args.get("limit", 10, type=int)
    return _events_response(current_app.vision_service.latest(limit))


@vision_bp.get("/events")
def events():
    class_name = request.args.get("class")
    if class_name is not None and class_name not in VISION_CLASSES:
        return jsonify({"success": False, "error": "Invalid class"}), 400
    return _events_response(current_app.vision_service.all(class_name))


@vision_bp.post("/events")
def create_event():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "JSON object required"}), 400
    try:
        event = VisionEvent(
            event_id=payload.get("event_id"),
            timestamp=payload.get("timestamp"),
            class_name=payload.get("class_name"),
            confidence=payload.get("confidence"),
            bbox=tuple(payload.get("bbox", ())),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            snapshot_url=payload.get("snapshot_url"),
            source_id=payload.get("source_id"),
            processing_latency_ms=payload.get("processing_latency_ms"),
        )
        current_app.publish_vision_event(event)
    except (VisionContractError, TypeError, ValueError) as exc:
        current_app.vision_service.log_error("invalid_event", str(exc))
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "event": event.to_dict()}), 201


@vision_bp.get("/events/<event_id>")
def event_by_id(event_id):
    event = current_app.vision_service.get(event_id)
    if event is None:
        return jsonify({"success": False, "error": "Event not found"}), 404
    return jsonify({"success": True, "event": event.to_dict()})


@vision_bp.get("/errors")
def errors():
    limit = request.args.get("limit", 50, type=int)
    items = current_app.vision_service.errors(limit)
    return jsonify({"success": True, "errors": items, "count": len(items)})


@vision_bp.get("/health")
def health():
    frame_meta = {}
    store = getattr(current_app, "annotated_frame_store", None)
    if store is not None:
        frame_meta = store.meta()
    return jsonify({
        "success": True,
        "status": "healthy",
        "timestamp": _utc_now(),
        "stats": current_app.vision_service.stats(),
        "annotated_stream": frame_meta,
    })


@vision_bp.post("/annotated-frame")
def upload_annotated_frame():
    """Accept one JPEG annotated frame from the CV pipeline."""
    store = getattr(current_app, "annotated_frame_store", None)
    if store is None:
        return jsonify({"success": False, "error": "Annotated store missing"}), 500
    data = request.get_data(cache=False)
    if not data:
        return jsonify({"success": False, "error": "JPEG body required"}), 400
    try:
        frame_count = store.update(data)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "frame_count": frame_count}), 201


@vision_bp.get("/mjpeg")
def annotated_mjpeg():
    """Live MJPEG of the latest CV-annotated frames (boxes on video)."""
    store = getattr(current_app, "annotated_frame_store", None)
    if store is None:
        return jsonify({"success": False, "error": "Annotated store missing"}), 500
    boundary = b"frame"
    return Response(
        store.mjpeg_generator(boundary=boundary),
        mimetype=f"multipart/x-mixed-replace; boundary={boundary.decode('ascii')}",
    )


@vision_bp.get("/annotated/latest.jpg")
def annotated_latest_jpeg():
    store = getattr(current_app, "annotated_frame_store", None)
    if store is None:
        return jsonify({"success": False, "error": "Annotated store missing"}), 500
    jpeg = store.get()
    if jpeg is None:
        return jsonify({"success": False, "error": "No annotated frame yet"}), 404
    return Response(jpeg, mimetype="image/jpeg")


def _snapshot_response(event_id):
    event = current_app.vision_service.get(event_id)
    if event is None:
        return jsonify({"success": False, "error": "Event not found"}), 404
    snapshot_dir = Path(current_app.config["VISION_SNAPSHOT_DIR"]).resolve()
    snapshot_path = (snapshot_dir / f"{event_id}.jpg").resolve()
    if snapshot_path.parent != snapshot_dir or not snapshot_path.is_file():
        current_app.vision_service.log_error(
            "snapshot_unavailable",
            f"Snapshot missing for event {event_id}",
        )
        return jsonify({"success": False, "error": "Snapshot not available"}), 404
    return send_file(snapshot_path, mimetype="image/jpeg")


@vision_bp.get("/snapshots/<event_id>.jpg")
def snapshot(event_id):
    return _snapshot_response(event_id)


@vision_bp.get("/snapshot/<event_id>")
def snapshot_compat(event_id):
    return _snapshot_response(event_id)
