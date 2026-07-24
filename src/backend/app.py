"""
AIS SITL Web Dashboard Backend

Flask application with REST API and WebSocket support for drone monitoring
and mission control.

Features:
- REST API for drone control, mission management, telemetry
- WebSocket for 10 Hz real-time telemetry streaming
- Failsafe monitoring and event logging
- Geofence validation

Status: Veha 4 (July 25-28, 2026)
Timeline: Development in progress
"""

import asyncio
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from functools import wraps

from src.backend.services import (
    DroneService,
    MissionServiceAPI,
    TelemetryServiceAPI,
    FailsafeServiceAPI,
)

logger = logging.getLogger(__name__)


def error_handler(f):
    """Decorator for error handling in API routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Route error: {e}")
            return jsonify({"error": str(e), "success": False}), 500
    return decorated_function


def create_app(config=None):
    """Create and configure Flask application."""
    app = Flask(__name__)

    # Configuration
    app.config['JSON_SORT_KEYS'] = False
    app.config['CORS_HEADERS'] = 'Content-Type'

    if config:
        app.config.update(config)

    # Enable CORS
    CORS(app)

    # Initialize WebSocket
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        ping_timeout=60,
        ping_interval=25,
    )

    # Initialize services
    app.drone_service = DroneService()
    app.mission_service = None
    app.telemetry_service = None
    app.failsafe_service = None
    app.clients = set()

    # =====================================================================
    # HEALTH CHECK
    # =====================================================================

    @app.route('/api/health', methods=['GET'])
    @error_handler
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'ok',
            'version': '0.1.0',
            'veha': 4,
            'drone_connected': app.drone_service.is_connected(),
        })

    # =====================================================================
    # DRONE ENDPOINTS
    # =====================================================================

    @app.route('/api/drone/initialize', methods=['POST'])
    @error_handler
    def drone_initialize():
        """Initialize and connect to drone."""
        try:
            asyncio.run(app.drone_service.initialize())

            # Initialize other services
            mavsdk_system = app.drone_service.drone._system if app.drone_service.drone else None
            app.mission_service = MissionServiceAPI(mavsdk_system)
            app.telemetry_service = TelemetryServiceAPI(mavsdk_system)
            app.failsafe_service = FailsafeServiceAPI(
                app.drone_service.drone,
                None  # Will init telemetry separately
            )

            return jsonify({
                "success": True,
                "message": "Drone initialized",
                "connected": True,
            })
        except Exception as e:
            logger.error(f"Initialize error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/status', methods=['GET'])
    @error_handler
    def drone_status():
        """Get current drone status."""
        status = asyncio.run(app.drone_service.get_status())
        return jsonify(status)

    @app.route('/api/drone/wait-ready', methods=['POST'])
    @error_handler
    def drone_wait_ready():
        """Wait for drone to be ready (GPS + home)."""
        timeout = request.json.get('timeout', 30) if request.json else 30
        try:
            asyncio.run(app.drone_service.wait_until_ready(timeout_s=timeout))
            return jsonify({"success": True, "message": "Drone ready"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/arm', methods=['POST'])
    @error_handler
    def drone_arm():
        """Arm motors."""
        try:
            asyncio.run(app.drone_service.arm())
            return jsonify({"success": True, "message": "Armed"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/disarm', methods=['POST'])
    @error_handler
    def drone_disarm():
        """Disarm motors."""
        try:
            asyncio.run(app.drone_service.disarm())
            return jsonify({"success": True, "message": "Disarmed"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/takeoff', methods=['POST'])
    @error_handler
    def drone_takeoff():
        """Takeoff to altitude."""
        altitude = request.json.get('altitude', 50) if request.json else 50
        try:
            asyncio.run(app.drone_service.takeoff(altitude))
            return jsonify({
                "success": True,
                "message": f"Takeoff to {altitude}m",
                "altitude": altitude,
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/land', methods=['POST'])
    @error_handler
    def drone_land():
        """Land at current position."""
        try:
            asyncio.run(app.drone_service.land())
            return jsonify({"success": True, "message": "Landing"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/hold', methods=['POST'])
    @error_handler
    def drone_hold():
        """Hold position (hover)."""
        try:
            asyncio.run(app.drone_service.hold_position())
            return jsonify({"success": True, "message": "Holding position"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/rtl', methods=['POST'])
    @error_handler
    def drone_rtl():
        """Return to launch (RTL)."""
        reason = request.json.get('reason', 'api_request') if request.json else 'api_request'
        try:
            asyncio.run(app.drone_service.return_to_launch(reason=reason))
            return jsonify({"success": True, "message": "RTL initiated", "reason": reason})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # =====================================================================
    # MISSION ENDPOINTS
    # =====================================================================

    @app.route('/api/mission/validate', methods=['POST'])
    @error_handler
    def mission_validate():
        """Validate mission waypoints."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        waypoints = request.json.get('waypoints', []) if request.json else []
        result = asyncio.run(app.mission_service.validate_mission(waypoints))
        return jsonify(result)

    @app.route('/api/mission/upload', methods=['POST'])
    @error_handler
    def mission_upload():
        """Upload mission to drone."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        waypoints = request.json.get('waypoints', []) if request.json else []
        result = asyncio.run(app.mission_service.upload_mission(waypoints))
        return jsonify(result)

    @app.route('/api/mission/start', methods=['POST'])
    @error_handler
    def mission_start():
        """Start mission execution."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        result = asyncio.run(app.mission_service.start_mission())
        return jsonify(result)

    @app.route('/api/mission/pause', methods=['POST'])
    @error_handler
    def mission_pause():
        """Pause mission."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        result = asyncio.run(app.mission_service.pause_mission())
        return jsonify(result)

    @app.route('/api/mission/resume', methods=['POST'])
    @error_handler
    def mission_resume():
        """Resume mission."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        result = asyncio.run(app.mission_service.resume_mission())
        return jsonify(result)

    @app.route('/api/mission/abort', methods=['POST'])
    @error_handler
    def mission_abort():
        """Abort mission."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        result = asyncio.run(app.mission_service.abort_mission())
        return jsonify(result)

    @app.route('/api/mission/progress', methods=['GET'])
    @error_handler
    def mission_progress():
        """Get mission progress."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        progress = asyncio.run(app.mission_service.get_progress())
        return jsonify(progress)

    @app.route('/api/mission/history', methods=['GET'])
    @error_handler
    def mission_history():
        """Get mission history."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        history = asyncio.run(app.mission_service.get_history())
        return jsonify(history)

    # =====================================================================
    # TELEMETRY ENDPOINTS
    # =====================================================================

    @app.route('/api/telemetry/latest', methods=['GET'])
    @error_handler
    def telemetry_latest():
        """Get latest telemetry."""
        if not app.telemetry_service:
            return jsonify({"error": "Telemetry service not initialized"}), 500

        latest = asyncio.run(app.telemetry_service.get_latest())
        return jsonify(latest)

    @app.route('/api/telemetry/history', methods=['GET'])
    @error_handler
    def telemetry_history():
        """Get telemetry history."""
        if not app.telemetry_service:
            return jsonify({"error": "Telemetry service not initialized"}), 500

        count = request.args.get('count', 10, type=int)
        history = asyncio.run(app.telemetry_service.get_history(count=count))
        return jsonify({"count": len(history), "data": history})

    @app.route('/api/telemetry/stats', methods=['GET'])
    @error_handler
    def telemetry_stats():
        """Get telemetry statistics."""
        if not app.telemetry_service:
            return jsonify({"error": "Telemetry service not initialized"}), 500

        stats = asyncio.run(app.telemetry_service.get_statistics())
        return jsonify(stats)

    # =====================================================================
    # FAILSAFE ENDPOINTS
    # =====================================================================

    @app.route('/api/failsafe/status', methods=['GET'])
    @error_handler
    def failsafe_status():
        """Get failsafe status."""
        if not app.failsafe_service:
            return jsonify({"error": "Failsafe service not initialized"}), 500

        status = asyncio.run(app.failsafe_service.get_status())
        return jsonify(status)

    @app.route('/api/failsafe/events', methods=['GET'])
    @error_handler
    def failsafe_events():
        """Get failsafe events."""
        if not app.failsafe_service:
            return jsonify({"error": "Failsafe service not initialized"}), 500

        limit = request.args.get('limit', 50, type=int)
        events = asyncio.run(app.failsafe_service.get_events(limit=limit))
        return jsonify(events)

    # =====================================================================
    # ERROR HANDLERS
    # =====================================================================

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found', 'success': False}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f'Internal server error: {e}')
        return jsonify({'error': 'Internal server error', 'success': False}), 500

    # =====================================================================
    # WEBSOCKET EVENTS
    # =====================================================================

    @socketio.on('connect')
    def on_connect():
        """Handle client connection."""
        client_id = request.sid
        app.clients.add(client_id)
        logger.info(f"Client connected: {client_id} (total: {len(app.clients)})")
        emit('connected', {
            'message': 'Connected to AIS SITL Dashboard',
            'client_id': client_id,
        })

    @socketio.on('disconnect')
    def on_disconnect():
        """Handle client disconnection."""
        client_id = request.sid
        app.clients.discard(client_id)
        logger.info(f"Client disconnected: {client_id} (total: {len(app.clients)})")

    @socketio.on('start_telemetry')
    def on_start_telemetry():
        """Start telemetry streaming to this client."""
        client_id = request.sid
        if app.telemetry_service:
            app.telemetry_service.register_client(client_id)
            emit('telemetry_started', {'client_id': client_id})

    @socketio.on('stop_telemetry')
    def on_stop_telemetry():
        """Stop telemetry streaming to this client."""
        client_id = request.sid
        if app.telemetry_service:
            app.telemetry_service.unregister_client(client_id)
            emit('telemetry_stopped', {'client_id': client_id})

    return app, socketio


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    app, socketio = create_app({
        'DEBUG': True,
    })

    logger.info('Starting AIS SITL Web Dashboard...')
    logger.info('Backend available at http://127.0.0.1:5000')
    logger.info('API docs: http://127.0.0.1:5000/api/docs')

    socketio.run(app, host='127.0.0.1', port=5000, debug=True)
