"""AIS SITL Computer Vision MVP - standalone Vision API (Мерей)."""
import os

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from backend.routes.vision import vision_bp
from backend.vision.event_pipeline import VisionEventPipeline
from backend.vision.socket_handler import VisionSocketHandler
from backend.vision.vision_service import VisionService


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    CORS(app)

    vision_service = VisionService()
    socket_handler = VisionSocketHandler(rate_limit_per_sec=10)
    pipeline = VisionEventPipeline(service=vision_service, socket_handler=socket_handler)

    app.vision_service = vision_service
    app.socket_handler = socket_handler
    app.vision_socket_handler = socket_handler
    app.vision_pipeline = pipeline

    app.register_blueprint(vision_bp)
    socketio = SocketIO(app, cors_allowed_origins="*")

    @socketio.on("connect")
    def handle_connect():
        emit(
            "response",
            {"status": "connected", "message": "Connected to Vision API"},
        )

    @socketio.on("subscribe_detections")
    def handle_subscribe_detections():
        def on_detection(payload):
            emit("vision_detection", payload, broadcast=False)

        socket_handler.subscribe("vision_detection", on_detection)
        emit("response", {"status": "subscribed", "event_type": "vision_detection"})

    @socketio.on("subscribe_alerts")
    def handle_subscribe_alerts():
        def on_alert(payload):
            emit("vision_alert", payload, broadcast=False)

        socket_handler.subscribe("vision_alert", on_alert)
        emit("response", {"status": "subscribed", "event_type": "vision_alert"})

    @socketio.on("disconnect")
    def handle_disconnect():
        pass

    @app.route("/", methods=["GET"])
    def index():
        return {
            "status": "running",
            "service": "AIS SITL Computer Vision MVP",
            "version": "1.0",
            "endpoints": {
                "vision": "/api/vision",
                "health": "/api/vision/health",
                "latest": "/api/vision/latest",
                "events": "/api/vision/events",
                "errors": "/api/vision/errors",
                "geo_report": "/api/vision/geo/report",
                "stats": "/api/vision/stats",
            },
        }

    return app, socketio


if __name__ == "__main__":
    app, socketio = create_app()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
