from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
import os

vision_bp = Blueprint("vision", __name__, url_prefix="/api/vision")


@vision_bp.route("/latest", methods=["GET"])
def get_latest_events():
    """Get latest vision events."""
    try:
        limit = request.args.get("limit", 10, type=int)
        limit = max(1, min(limit, 100))  # Clamp between 1 and 100

        vision_service = current_app.vision_service
        events = vision_service.get_latest_events(limit)

        utc_now = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        return jsonify({
            "success": True,
            "timestamp": utc_now,
            "events": events,
            "count": len(events),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@vision_bp.route("/events", methods=["GET"])
def get_all_events():
    """Get all stored events with optional filtering."""
    try:
        class_name = request.args.get("class", None)
        vision_service = current_app.vision_service

        if class_name:
            if class_name not in ["Person", "Car", "Truck_Machinery"]:
                return jsonify({
                    "success": False,
                    "error": f"Invalid class: {class_name}",
                }), 400
            events = vision_service.get_events_by_class(class_name)
        else:
            events = vision_service.store.get_all_events()
            events = [e.to_dict() for e in events]

        utc_now = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        return jsonify({
            "success": True,
            "timestamp": utc_now,
            "events": events,
            "count": len(events),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@vision_bp.route("/event/<event_id>", methods=["GET"])
def get_event(event_id):
    """Get specific event by ID."""
    try:
        vision_service = current_app.vision_service
        event = vision_service.get_event_by_id(event_id)

        if not event:
            return jsonify({
                "success": False,
                "error": "Event not found",
            }), 404

        return jsonify({
            "success": True,
            "event": event,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@vision_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get vision service statistics."""
    try:
        vision_service = current_app.vision_service
        stats = vision_service.get_stats()

        return jsonify({
            "success": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stats": stats,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@vision_bp.route("/snapshot/<event_id>", methods=["GET"])
def get_snapshot(event_id):
    """Get snapshot for a specific event."""
    try:
        vision_service = current_app.vision_service
        event = vision_service.get_event_by_id(event_id)

        if not event:
            return jsonify({
                "success": False,
                "error": "Event not found",
            }), 404

        snapshot_url = event.get("snapshot_url")
        if not snapshot_url:
            return jsonify({
                "success": False,
                "error": "Snapshot not available",
            }), 404

        # If snapshot_url is a file path, serve it
        if os.path.exists(snapshot_url):
            from flask import send_file
            return send_file(snapshot_url, mimetype="image/jpeg")

        # Otherwise return URL
        return jsonify({
            "success": True,
            "snapshot_url": snapshot_url,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@vision_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "success": True,
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
