"""REST routes for vision events — Мерей."""
from datetime import datetime, timezone
import os

from flask import Blueprint, current_app, jsonify, request, send_file

vision_bp = Blueprint("vision", __name__, url_prefix="/api/vision")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


@vision_bp.route("/latest", methods=["GET"])
def get_latest_events():
    try:
        limit = request.args.get("limit", 10, type=int)
        limit = max(1, min(limit, 100))
        events = current_app.vision_service.get_latest_events(limit)
        return jsonify(
            {
                "success": True,
                "timestamp": _utc_now(),
                "events": events,
                "count": len(events),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@vision_bp.route("/events", methods=["GET"])
def get_all_events():
    try:
        class_name = request.args.get("class", None)
        vision_service = current_app.vision_service

        if class_name:
            if class_name not in ["Person", "Car", "Truck_Machinery"]:
                return jsonify(
                    {"success": False, "error": f"Invalid class: {class_name}"}
                ), 400
            events = vision_service.get_events_by_class(class_name)
        else:
            events = [e.to_dict() for e in vision_service.store.get_all_events()]

        return jsonify(
            {
                "success": True,
                "timestamp": _utc_now(),
                "events": events,
                "count": len(events),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@vision_bp.route("/event/<event_id>", methods=["GET"])
def get_event(event_id):
    try:
        event = current_app.vision_service.get_event_by_id(event_id)
        if not event:
            return jsonify({"success": False, "error": "Event not found"}), 404
        return jsonify({"success": True, "event": event})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@vision_bp.route("/stats", methods=["GET"])
def get_stats():
    try:
        stats = current_app.vision_service.get_stats()
        return jsonify({"success": True, "timestamp": _utc_now(), "stats": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@vision_bp.route("/errors", methods=["GET"])
def get_errors():
    """Error journal — dashboard stays up; no false alerts."""
    try:
        limit = request.args.get("limit", 50, type=int)
        errors = current_app.vision_service.get_errors(limit=max(1, min(limit, 200)))
        return jsonify(
            {
                "success": True,
                "timestamp": _utc_now(),
                "errors": errors,
                "count": len(errors),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@vision_bp.route("/geo/report", methods=["GET"])
def geo_report():
    """MAE / max error report for 50/75/100 m and pitch scenarios."""
    try:
        from backend.geo.geo_validation import GeoValidator

        report = GeoValidator.run_mae_report()
        return jsonify({"success": True, "timestamp": _utc_now(), "report": report})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@vision_bp.route("/snapshot/<event_id>", methods=["GET"])
def get_snapshot(event_id):
    try:
        event = current_app.vision_service.get_event_by_id(event_id)
        if not event:
            return jsonify({"success": False, "error": "Event not found"}), 404

        snapshot_url = event.get("snapshot_url")
        if not snapshot_url:
            current_app.vision_service.log_error(
                "snapshot_unavailable",
                f"No snapshot_url for event {event_id}",
            )
            return jsonify({"success": False, "error": "Snapshot not available"}), 404

        if os.path.exists(snapshot_url):
            return send_file(snapshot_url, mimetype="image/jpeg")

        # Remote/relative URL — client may open directly; file missing is still 404 for local paths
        if snapshot_url.startswith("http://") or snapshot_url.startswith("https://"):
            return jsonify({"success": True, "snapshot_url": snapshot_url})

        current_app.vision_service.log_error(
            "snapshot_unavailable",
            f"Snapshot file missing: {snapshot_url}",
            {"event_id": event_id},
        )
        return jsonify({"success": False, "error": "Snapshot not available"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@vision_bp.route("/health", methods=["GET"])
def health():
    service = getattr(current_app, "vision_service", None)
    runtime = service.get_stats().get("runtime") if service else {}
    return jsonify(
        {
            "success": True,
            "status": "healthy",
            "timestamp": _utc_now(),
            "runtime": runtime,
        }
    )
