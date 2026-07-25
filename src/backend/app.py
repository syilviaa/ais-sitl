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
from flask_socketio import SocketIO, emit
from functools import wraps

from src.backend.services import (
    DroneService,
    MissionServiceAPI,
    TelemetryServiceAPI,
    FailsafeServiceAPI,
)
from src.backend.services.fleet_service import FleetService
from src.backend.services.recording_service import RecordingService
from src.backend.services.geofence_service import GeofenceService
from src.backend.database import SessionLocal

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
    app.fleet_service = FleetService()
    app.fleet_service.set_database(SessionLocal)
    app.recording_service = RecordingService()
    app.recording_service.set_database(SessionLocal)
    app.geofence_service = GeofenceService()
    app.geofence_service.set_database(SessionLocal)
    app.clients = set()

    def broadcast_telemetry(payload):
        """Send a collector snapshot to explicitly subscribed clients only."""
        service = app.telemetry_service
        if not service:
            return
        for client_id in tuple(service.clients):
            socketio.emit('telemetry', payload, to=client_id)

    def configure_telemetry_service(service):
        """Attach the single service instance to the SocketIO broadcaster."""
        service.set_broadcast_callback(broadcast_telemetry)

    app.configure_telemetry_service = configure_telemetry_service

    def run_telemetry_service(service):
        """Run the existing async collector in one SocketIO background task."""
        asyncio.run(service.run_forever())

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
            drone = app.drone_service.drone
            mavsdk_system = drone._system if drone else None
            app.mission_service = MissionServiceAPI(mavsdk_system)
            if app.telemetry_service is None:
                app.telemetry_service = TelemetryServiceAPI(mavsdk_system)
                configure_telemetry_service(app.telemetry_service)
                socketio.start_background_task(
                    run_telemetry_service, app.telemetry_service
                )
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
        reason = (
            request.json.get('reason', 'api_request')
            if request.json else 'api_request'
        )
        try:
            asyncio.run(app.drone_service.return_to_launch(reason=reason))
            return jsonify({
                "success": True,
                "message": "RTL initiated",
                "reason": reason,
            })
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
    # FLEET ENDPOINTS (VEHA 5)
    # =====================================================================

    @app.route('/api/fleet/add-drone', methods=['POST'])
    @error_handler
    def fleet_add_drone():
        """Register a new drone in the fleet."""
        data = request.json or {}
        name = data.get('name')
        host = data.get('host', '127.0.0.1')
        port = data.get('port', 14540)

        if not name:
            return jsonify({"error": "Drone name required"}), 400

        result = asyncio.run(app.fleet_service.add_drone(name, host, port))
        return jsonify(result)

    @app.route('/api/fleet/remove-drone/<drone_id>', methods=['DELETE'])
    @error_handler
    def fleet_remove_drone(drone_id):
        """Remove drone from fleet."""
        result = asyncio.run(app.fleet_service.remove_drone(drone_id))
        return jsonify(result)

    @app.route('/api/fleet/status', methods=['GET'])
    @error_handler
    def fleet_status():
        """Get status of all drones in fleet."""
        result = asyncio.run(app.fleet_service.get_fleet_status())
        return jsonify(result)

    @app.route('/api/fleet/conflicts', methods=['GET'])
    @error_handler
    def fleet_conflicts():
        """Check for airspace conflicts."""
        result = asyncio.run(app.fleet_service.check_conflicts())
        return jsonify(result)

    @app.route('/api/fleet/coordinated-takeoff', methods=['POST'])
    @error_handler
    def fleet_coordinated_takeoff():
        """Execute coordinated takeoff for multiple drones."""
        data = request.json or {}
        drone_names = data.get('drones', [])
        altitude = data.get('altitude', 50)
        delay = data.get('delay', 1.0)

        if not drone_names:
            return jsonify({"error": "Drone list required"}), 400

        result = asyncio.run(app.fleet_service.coordinated_takeoff(drone_names, altitude, delay))
        return jsonify(result)

    @app.route('/api/fleet/broadcast', methods=['POST'])
    @error_handler
    def fleet_broadcast():
        """Broadcast command to all drones."""
        data = request.json or {}
        command = data.get('command')

        if not command:
            return jsonify({"error": "Command required"}), 400

        result = asyncio.run(app.fleet_service.broadcast_command(command, data))
        return jsonify(result)

    @app.route('/api/fleet/emergency-stop', methods=['POST'])
    @error_handler
    def fleet_emergency_stop():
        """Emergency stop all drones."""
        result = asyncio.run(app.fleet_service.emergency_stop())
        return jsonify(result)

    # =====================================================================
    # RECORDING ENDPOINTS (VEHA 5 PHASE 3)
    # =====================================================================

    @app.route('/api/recording/start/<mission_id>', methods=['POST'])
    @error_handler
    def recording_start(mission_id):
        """Start recording a mission."""
        result = asyncio.run(app.recording_service.start_recording(mission_id))
        return jsonify(result)

    @app.route('/api/recording/stop/<mission_id>', methods=['POST'])
    @error_handler
    def recording_stop(mission_id):
        """Stop recording and save mission."""
        result = asyncio.run(app.recording_service.stop_recording(mission_id))
        return jsonify(result)

    @app.route('/api/recording/get/<mission_id>', methods=['GET'])
    @error_handler
    def recording_get(mission_id):
        """Get recording details."""
        result = asyncio.run(app.recording_service.get_recording(mission_id))
        return jsonify(result)

    @app.route('/api/recording/list', methods=['GET'])
    @error_handler
    def recording_list():
        """List all recordings."""
        limit = request.args.get('limit', 50, type=int)
        result = asyncio.run(app.recording_service.list_recordings(limit))
        return jsonify(result)

    @app.route('/api/recording/playback/<mission_id>', methods=['GET'])
    @error_handler
    def recording_playback(mission_id):
        """Get playback timeline for a recording."""
        speed = request.args.get('speed', 1.0, type=float)
        result = asyncio.run(app.recording_service.get_playback_timeline(mission_id, speed))
        return jsonify(result)

    @app.route('/api/recording/delete/<mission_id>', methods=['DELETE'])
    @error_handler
    def recording_delete(mission_id):
        """Delete a recording."""
        result = asyncio.run(app.recording_service.delete_recording(mission_id))
        return jsonify(result)

    # =====================================================================
    # GEOFENCE ENDPOINTS (VEHA 5 PHASE 4)
    # =====================================================================

    @app.route('/api/geofence/create', methods=['POST'])
    @error_handler
    def geofence_create():
        """Create a new geofence zone."""
        data = request.json or {}
        name = data.get('name')
        polygon = data.get('polygon')
        altitude_min = data.get('altitude_min', 0.0)
        altitude_max = data.get('altitude_max')

        if not name or not polygon:
            return jsonify({"error": "Name and polygon required"}), 400

        result = asyncio.run(app.geofence_service.create_zone(name, polygon, altitude_min, altitude_max))
        return jsonify(result)

    @app.route('/api/geofence/get/<zone_name>', methods=['GET'])
    @error_handler
    def geofence_get(zone_name):
        """Get geofence zone details."""
        result = asyncio.run(app.geofence_service.get_zone(zone_name))
        return jsonify(result)

    @app.route('/api/geofence/list', methods=['GET'])
    @error_handler
    def geofence_list():
        """List all geofence zones."""
        active_only = request.args.get('active', 'true', type=str).lower() == 'true'
        result = asyncio.run(app.geofence_service.list_zones(active_only))
        return jsonify(result)

    @app.route('/api/geofence/update/<zone_name>', methods=['POST'])
    @error_handler
    def geofence_update(zone_name):
        """Update geofence zone."""
        data = request.json or {}
        polygon = data.get('polygon')
        altitude_min = data.get('altitude_min')
        altitude_max = data.get('altitude_max')
        active = data.get('active')

        result = asyncio.run(app.geofence_service.update_zone(
            zone_name, polygon, altitude_min, altitude_max, active
        ))
        return jsonify(result)

    @app.route('/api/geofence/delete/<zone_name>', methods=['DELETE'])
    @error_handler
    def geofence_delete(zone_name):
        """Delete geofence zone."""
        result = asyncio.run(app.geofence_service.delete_zone(zone_name))
        return jsonify(result)

    @app.route('/api/geofence/validate-mission', methods=['POST'])
    @error_handler
    def geofence_validate_mission():
        """Validate mission waypoints against geofence zones."""
        data = request.json or {}
        waypoints = data.get('waypoints', [])

        if not waypoints:
            return jsonify({"error": "Waypoints required"}), 400

        result = asyncio.run(app.geofence_service.validate_mission(waypoints))
        return jsonify(result)

    @app.route('/api/geofence/check-position', methods=['POST'])
    @error_handler
    def geofence_check_position():
        """Check drone position against geofence zones."""
        data = request.json or {}
        drone_id = data.get('drone_id')
        position = data.get('position', {})

        if not drone_id:
            return jsonify({"error": "Drone ID required"}), 400

        result = asyncio.run(app.geofence_service.check_position(drone_id, position))
        return jsonify(result)

    @app.route('/api/geofence/violations/<zone_name>', methods=['GET'])
    @error_handler
    def geofence_violations(zone_name):
        """Get violation history for a zone."""
        limit = request.args.get('limit', 100, type=int)
        result = asyncio.run(app.geofence_service.get_violations(zone_name, limit))
        return jsonify(result)

    # =====================================================================
    # ERROR HANDLERS
    # =====================================================================

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found', 'success': False}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f'Internal server error: {e}')
        return jsonify({
            'error': 'Internal server error',
            'success': False,
        }), 500

    # =====================================================================
    # WEBSOCKET EVENTS
    # =====================================================================

    def announce_connection(client_id):
        """Emit after the SocketIO connect handshake has completed."""
        socketio.sleep(0)
        socketio.emit(
            'connected',
            {
                'message': 'Connected to AIS SITL Dashboard',
                'client_id': client_id,
            },
            to=client_id,
        )

    @socketio.on('connect')
    def on_connect():
        """Handle client connection."""
        client_id = request.sid
        app.clients.add(client_id)
        logger.info(
            f"Client connected: {client_id} (total: {len(app.clients)})"
        )
        socketio.start_background_task(announce_connection, client_id)

    @socketio.on('disconnect')
    def on_disconnect():
        """Handle client disconnection."""
        client_id = request.sid
        app.clients.discard(client_id)
        if app.telemetry_service:
            app.telemetry_service.unregister_client(client_id)
        logger.info(
            f"Client disconnected: {client_id} (total: {len(app.clients)})"
        )

    @socketio.on('start_telemetry')
    def on_start_telemetry():
        """Start telemetry streaming to this client."""
        client_id = request.sid
        if app.telemetry_service:
            app.telemetry_service.register_client(client_id)
            emit('telemetry_started', {'client_id': client_id})
        else:
            emit('telemetry_error', {
                'message': 'Telemetry service is not initialized',
            })

    @socketio.on('stop_telemetry')
    def on_stop_telemetry():
        """Stop telemetry streaming to this client."""
        client_id = request.sid
        if app.telemetry_service:
            app.telemetry_service.unregister_client(client_id)
            emit('telemetry_stopped', {'client_id': client_id})

    @socketio.on('fleet_status')
    def on_fleet_status():
        """Get fleet status on demand."""
        try:
            result = asyncio.run(app.fleet_service.get_fleet_status())
            emit('fleet_status', result)
        except Exception as e:
            logger.error(f"Fleet status error: {e}")
            emit('fleet_error', {'error': str(e)})

    @socketio.on('start_fleet_monitoring')
    def on_start_fleet_monitoring():
        """Start periodic fleet status updates."""
        client_id = request.sid

        def broadcast_fleet_status():
            """Periodically broadcast fleet status to all clients."""
            while True:
                try:
                    result = asyncio.run(app.fleet_service.get_fleet_status())
                    for cid in app.clients:
                        socketio.emit('fleet_status', result, to=cid)
                    socketio.sleep(1)
                except Exception as e:
                    logger.error(f"Fleet broadcast error: {e}")
                    socketio.sleep(1)

        if not hasattr(app, '_fleet_monitoring_started'):
            app._fleet_monitoring_started = True
            socketio.start_background_task(broadcast_fleet_status)

        emit('fleet_monitoring_started', {'client_id': client_id})

    # TODO: Mission-progress and failsafe events belong to other owners.

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
