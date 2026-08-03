"""AIS SITL Computer Vision MVP - Backend API and WebSocket Server."""
import os
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit, on
from backend.vision.vision_service import VisionService
from backend.vision.socket_handler import VisionSocketHandler
from backend.routes.vision import vision_bp


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # Enable CORS
    CORS(app)

    # Initialize services
    vision_service = VisionService()
    socket_handler = VisionSocketHandler(rate_limit_per_sec=10)

    # Store services in app context
    app.vision_service = vision_service
    app.socket_handler = socket_handler

    # Register blueprints
    app.register_blueprint(vision_bp)

    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")

    @socketio.on("connect")
    def handle_connect():
        """Handle WebSocket connection."""
        print(f"Client connected: {socketio.server.environ.get('REMOTE_ADDR')}")
        emit("response", {
            "status": "connected",
            "message": "Connected to Vision API"
        })

    @socketio.on("subscribe_detections")
    def handle_subscribe_detections():
        """Subscribe to detection events."""
        def on_detection(payload):
            emit("vision_detection", payload, broadcast=False)

        socket_handler.subscribe("vision_detection", on_detection)
        emit("response", {"status": "subscribed", "event_type": "vision_detection"})

    @socketio.on("subscribe_alerts")
    def handle_subscribe_alerts():
        """Subscribe to alert events."""
        def on_alert(payload):
            emit("vision_alert", payload, broadcast=False)

        socket_handler.subscribe("vision_alert", on_alert)
        emit("response", {"status": "subscribed", "event_type": "vision_alert"})

    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle WebSocket disconnection."""
        print("Client disconnected")

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
                "stats": "/api/vision/stats",
            }
        }

    return app, socketio


if __name__ == "__main__":
    app, socketio = create_app()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
