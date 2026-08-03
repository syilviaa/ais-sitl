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
import json
import logging
import os
from pathlib import Path

from flask import Flask, jsonify, request, Response
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
from src.backend.services.metrics_service import MetricsService
from src.backend.services.video_service import video_relay
from src.backend import database
from src.backend.async_runner import run_async, schedule_coroutine
from src.autopilot.geofence import GeofenceValidator
from src.mavsdk_import import (
    IMPORT_ERROR,
    MAVSDK_AVAILABLE,
    MavsdkServerHint,
    mavsdk_server_available,
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
    try:
        database.init_db()
    except Exception as exc:
        logger.warning("Database unavailable; persistence disabled: %s", exc)

    session_factory = database.SessionLocal

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
    app.fleet_service.set_database(session_factory)
    app.recording_service = RecordingService()
    app.recording_service.set_database(session_factory)
    app.geofence_service = GeofenceService()
    app.geofence_service.set_database(session_factory)
    app.metrics_service = MetricsService()
    app.clients = set()
    app.pending_telemetry_clients = set()

    # CV MVP (Мерей): vision service + Socket.IO alerts — does not invent GPS
    try:
        from backend.routes.vision import vision_bp
        from backend.vision.event_pipeline import VisionEventPipeline
        from backend.vision.socket_handler import VisionSocketHandler
        from backend.vision.vision_service import VisionService

        app.vision_service = VisionService()
        app.vision_socket_handler = VisionSocketHandler(rate_limit_per_sec=10)
        app.vision_pipeline = VisionEventPipeline(
            service=app.vision_service,
            socket_handler=app.vision_socket_handler,
        )
        app.vision_clients = {"detection": set(), "alert": set()}
        app.register_blueprint(vision_bp)
        logger.info("CV vision routes registered at /api/vision")
    except Exception as exc:
        logger.warning("CV vision module not loaded: %s", exc)
        app.vision_service = None
        app.vision_socket_handler = None
        app.vision_pipeline = None
        app.vision_clients = {"detection": set(), "alert": set()}

    # Spawn the GStreamer relay before any MAVSDK/gRPC session exists: forking a
    # process that already runs gRPC threads kills mavsdk_server (heartbeat loss).
    if video_relay.gstreamer_available:
        video_relay.ensure_running()

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
        """Run telemetry collector on the shared MAVSDK event loop."""
        schedule_coroutine(service.run_forever())

    def run_failsafe_service(service):
        """Run failsafe monitor on the shared MAVSDK event loop."""
        schedule_coroutine(service.start())

    app._geofence_validator = GeofenceValidator()
    app._geofence_validator.load_nfz_zones()

    async def geofence_telemetry_guard(snapshot):
        """Hold position if drone enters an active NFZ (TZ §2.3)."""
        if snapshot is None or not app.drone_service.drone:
            return
        validator = app._geofence_validator
        if isinstance(snapshot, dict):
            lat = snapshot.get("lat")
            lon = snapshot.get("lon")
            alt = snapshot.get("alt", snapshot.get("altitude_m", 0))
        else:
            lat = getattr(snapshot, "lat", None)
            lon = getattr(snapshot, "lon", None)
            alt = getattr(snapshot, "altitude_m", getattr(snapshot, "alt", 0))
        if lat is None:
            return
        in_nfz, zone_name = validator.check_point_in_nfz(lat, lon, alt)
        if in_nfz and not getattr(app, "_geofence_hold_active", False):
            app._geofence_hold_active = True
            logger.warning("NFZ breach in %s — holding position", zone_name)
            await app.drone_service.hold_position()
        elif not in_nfz:
            app._geofence_hold_active = False

    async def recover_mavsdk_link(force: bool = False) -> bool:
        """Reconnect a dead MAVSDK link and re-point services at the new system."""
        if not await app.drone_service.ensure_link(force=force):
            return False
        drone = app.drone_service.drone
        system = getattr(drone, "_system", None) if drone else None
        if app.mission_service:
            app.mission_service.service.stop_progress_watcher()
            app.mission_service.service._system = system
        if app.telemetry_service:
            await app.telemetry_service.collector.rebind_system(system)
        logger.info("MAVSDK link recovered — services rebound")
        return True

    def is_link_lost(error: Exception) -> bool:
        text = str(error)
        return any(
            marker in text
            for marker in ("UNAVAILABLE", "Socket closed", "Connection refused")
        )

    def run_with_link_retry(make_coro, timeout: float = 120):
        """Run a MAVSDK command, retrying once across a dropped gRPC link.

        Heavy Gazebo load can delay PX4 heartbeats past MAVSDK's 3 s window,
        which tears down the gRPC streams in the middle of a command.
        """
        try:
            return run_async(make_coro(), timeout=timeout)
        except Exception as error:
            if not is_link_lost(error):
                raise
            logger.warning("MAVSDK link dropped mid-command — reconnecting")
            run_async(recover_mavsdk_link(force=True), timeout=60)
            return run_async(make_coro(), timeout=timeout)

    def bind_telemetry_source(collector, drone):
        """Feed the collector from the drone's own streams, never a second set."""
        if not drone:
            return
        if app.drone_service.demo_mode:
            collector.set_demo_drone(drone)
        else:
            collector.set_drone_source(drone)

    def finish_drone_services():
        """Wire mission, telemetry, failsafe after drone connect."""
        drone = app.drone_service.drone
        mavsdk_system = getattr(drone, "_system", None) if drone else None
        app.mission_service = MissionServiceAPI(mavsdk_system)
        if app.telemetry_service is None:
            app.telemetry_service = TelemetryServiceAPI(mavsdk_system)
            bind_telemetry_source(app.telemetry_service.collector, drone)
            app.telemetry_service.collector.on_telemetry(geofence_telemetry_guard)
            configure_telemetry_service(app.telemetry_service)
            socketio.start_background_task(
                run_telemetry_service, app.telemetry_service
            )
        else:
            bind_telemetry_source(app.telemetry_service.collector, drone)

        app.failsafe_service = FailsafeServiceAPI(
            app.drone_service.drone,
            app.telemetry_service.collector if app.telemetry_service else None,
        )
        if app.telemetry_service and app.drone_service.drone:
            if not app.drone_service.demo_mode:
                try:
                    run_async(app.failsafe_service.initialize())
                    socketio.start_background_task(
                        run_failsafe_service, app.failsafe_service
                    )
                except Exception as fs_exc:
                    logger.warning("Failsafe not started: %s", fs_exc)

        if app.telemetry_service:
            app.telemetry_service.collector._battery_sim.reset(100.0)
            for client_id in list(app.pending_telemetry_clients):
                app.telemetry_service.register_client(client_id)
            app.pending_telemetry_clients.clear()

    app.finish_drone_services = finish_drone_services

    # =====================================================================
    # HEALTH CHECK
    # =====================================================================

    @app.route('/', methods=['GET'])
    @error_handler
    def index():
        """Root endpoint with API overview."""
        return jsonify({
            'name': 'AIS SITL Platform API',
            'status': 'ok',
            'version': '0.1.0',
            'veha': 5,
            'endpoints': {
                'health': '/api/health',
                'fleet': '/api/fleet/status',
                'metrics': '/api/metrics/summary',
                'geofence': '/api/geofence/list',
            },
            'note': 'Web dashboard (Vue) is deployed separately as a static site.',
        })

    @app.route('/api/health', methods=['GET'])
    @error_handler
    def health():
        """Health check endpoint."""
        nfz_count = len(app.geofence_service.zones_cache) if app.geofence_service else 0
        return jsonify({
            'status': 'ok',
            'version': '0.1.0',
            'veha': 4,
            'drone_connected': app.drone_service.is_connected(),
            'demo_mode': app.drone_service.demo_mode,
            'mavsdk_available': MAVSDK_AVAILABLE,
            'mavsdk_error': None if MAVSDK_AVAILABLE else IMPORT_ERROR,
            'mavsdk_server_available': mavsdk_server_available(),
            'geofence_zones': nfz_count,
            'video': video_relay.status(),
        })

    @app.route('/api/sitl/status', methods=['GET'])
    @error_handler
    def sitl_status():
        """PX4 Gazebo container + MAVLink readiness (before Connect SITL)."""
        from src.sitl_status import check_sitl_ready
        return jsonify(check_sitl_ready())

    @app.route('/api/mavlink/probe', methods=['GET'])
    @error_handler
    def mavlink_probe():
        """MAVLink UDP probe (pymavlink, TZ §2)."""
        from src.mavlink_probe import probe_mavlink_udp
        port = request.args.get('port', 14550, type=int)
        timeout = request.args.get('timeout', 1.0, type=float)
        return jsonify(probe_mavlink_udp(port=port, timeout_s=timeout))

    @app.route('/api/video/status', methods=['GET'])
    @error_handler
    def video_status():
        """Gazebo camera relay status."""
        video_relay.ensure_running()
        return jsonify(video_relay.status())

    @app.route('/api/video/snapshot', methods=['GET'])
    def video_snapshot():
        """Single JPEG frame (works reliably in browser vs MJPEG stream)."""
        if not video_relay.gstreamer_available:
            return jsonify({'error': 'GStreamer не установлен'}), 503
        frame = video_relay.get_snapshot_jpeg()
        if frame is None:
            return jsonify({
                'error': 'Кадр с камеры Gazebo ещё не получен',
                'status': video_relay.status(),
            }), 503
        return Response(
            frame,
            mimetype='image/jpeg',
            headers={'Cache-Control': 'no-store'},
        )

    @app.route('/api/video/mjpeg', methods=['GET'])
    def video_mjpeg():
        """MJPEG stream from Gazebo camera (UDP H.264 → GStreamer)."""
        if not video_relay.gstreamer_available:
            return jsonify({
                'error': video_relay.status().get('error')
                or 'GStreamer не установлен',
            }), 503
        return Response(
            video_relay.mjpeg_generator(),
            mimetype='multipart/x-mixed-replace; boundary=frame',
        )

    # =====================================================================
    # DRONE ENDPOINTS
    # =====================================================================

    @app.route('/api/drone/initialize', methods=['POST'])
    @error_handler
    def drone_initialize():
        """Initialize and connect to drone."""
        data = request.get_json(silent=True) or {}
        host = data.get('host', '127.0.0.1')
        port = int(data.get('port', 14540))
        sitl_port = int(data.get('sitl_port', 14580))
        demo = bool(
            data.get('demo')
            or os.environ.get('AIS_DEMO', '').lower() in ('1', 'true', 'yes')
        )

        try:
            if demo:
                run_async(app.drone_service.initialize_demo(), timeout=15)
            else:
                if not mavsdk_server_available():
                    raise RuntimeError(MavsdkServerHint)

                from src.sitl_status import check_sitl_ready
                sitl = check_sitl_ready()
                if not sitl["ready"]:
                    hint_text = " ".join(sitl["hints"]) or (
                        "Start PX4 SITL: ./scripts/start-px4-gazebo.sh, "
                        "wait ~30s, then Connect."
                    )
                    return jsonify({
                        "success": False,
                        "error": "PX4 SITL not ready",
                        "error_type": "SitlNotReady",
                        "hint": hint_text,
                        "sitl": sitl,
                    }), 503

                run_async(
                    app.drone_service.initialize(
                        host=host,
                        port=port,
                        sitl_port=sitl_port,
                    ),
                    timeout=45,
                )

            finish_drone_services()

            return jsonify({
                "success": True,
                "message": "Demo drone initialized" if demo else "Drone initialized",
                "connected": True,
                "demo_mode": app.drone_service.demo_mode,
            })
        except Exception as e:
            logger.exception(
                "Initialize error (host=%s port=%s)", host, port
            )
            message = str(e).strip() or repr(e)
            hint = None
            lower = message.lower()
            if any(
                token in lower
                for token in ("sitl", "timed out", "connect", "mavsdk", "server")
            ):
                hint = (
                    "Run backend locally with Python 3.11, start PX4 SITL (UDP 14540), "
                    "then Connect SITL. Render/cloud backend cannot reach SITL on your laptop."
                )
            if "mavsdk server" in lower or "mavsdk_server" in lower:
                hint = MavsdkServerHint
            return jsonify({
                "success": False,
                "error": message,
                "error_type": type(e).__name__,
                "hint": hint,
            }), 500

    @app.route('/api/drone/status', methods=['GET'])
    @error_handler
    def drone_status():
        """Get current drone status."""
        status = run_async(app.drone_service.get_status())
        return jsonify(status)

    @app.route('/api/drone/wait-ready', methods=['POST'])
    @error_handler
    def drone_wait_ready():
        """Wait for drone to be ready (GPS + home)."""
        timeout = request.json.get('timeout', 30) if request.json else 30
        try:
            run_async(app.drone_service.wait_until_ready(timeout_s=timeout))
            return jsonify({"success": True, "message": "Drone ready"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/arm', methods=['POST'])
    @error_handler
    def drone_arm():
        """Arm motors."""
        try:
            run_with_link_retry(app.drone_service.arm)
            return jsonify({"success": True, "message": "Armed"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/disarm', methods=['POST'])
    @error_handler
    def drone_disarm():
        """Disarm motors."""
        try:
            run_with_link_retry(app.drone_service.disarm)
            return jsonify({"success": True, "message": "Disarmed"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/takeoff', methods=['POST'])
    @error_handler
    def drone_takeoff():
        """Takeoff to altitude."""
        altitude = request.json.get('altitude', 50) if request.json else 50
        try:
            run_with_link_retry(
                lambda: app.drone_service.takeoff(altitude),
                timeout=90 + 2 * float(altitude),
            )
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
            run_with_link_retry(app.drone_service.land, timeout=240)
            return jsonify({"success": True, "message": "Landing"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/hold', methods=['POST'])
    @error_handler
    def drone_hold():
        """Hold position (hover)."""
        try:
            run_with_link_retry(app.drone_service.hold_position)
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
            run_with_link_retry(
                lambda: app.drone_service.return_to_launch(reason=reason)
            )
            return jsonify({
                "success": True,
                "message": "RTL initiated",
                "reason": reason,
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/drone/flight-speed', methods=['POST'])
    @error_handler
    def drone_flight_speed():
        """Set cruise speed and scale takeoff/landing rates with it."""
        data = request.json or {}
        cruise = data.get('cruise_m_s', data.get('cruise', 15))
        try:
            applied = run_with_link_retry(
                lambda: app.drone_service.set_flight_speed(float(cruise))
            )
            return jsonify({
                "success": True,
                "cruise_m_s": float(cruise),
                "params": applied,
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
        result = run_async(app.mission_service.validate_mission(waypoints))
        return jsonify(result)

    @app.route('/api/mission/upload', methods=['POST'])
    @error_handler
    def mission_upload():
        """Upload mission to drone."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        payload = request.json or {}
        waypoints = payload.get('waypoints', [])
        speed = payload.get('speed')
        if speed:
            waypoints = [
                {**wp, 'speed': wp.get('speed') or float(speed)}
                for wp in waypoints
            ]
        run_async(recover_mavsdk_link(), timeout=60)
        result = run_with_link_retry(
            lambda: app.mission_service.upload_mission(waypoints)
        )
        if result.get("error_type") == "link_lost":
            if run_async(recover_mavsdk_link(force=True), timeout=60):
                result = run_async(app.mission_service.upload_mission(waypoints))
        return jsonify(result)

    @app.route('/api/mission/export-plan', methods=['POST'])
    @error_handler
    def mission_export_plan():
        """Export mission as QGroundControl .plan JSON (TZ §3.2)."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500
        data = request.json or {}
        waypoints = data.get('waypoints', [])
        name = data.get('name', 'AIS Mission')
        result = run_async(app.mission_service.export_plan(waypoints, name=name))
        return jsonify(result)

    @app.route('/api/mission/start', methods=['POST'])
    @error_handler
    def mission_start():
        """Start mission execution."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        result = run_with_link_retry(app.mission_service.start_mission)
        return jsonify(result)

    @app.route('/api/mission/pause', methods=['POST'])
    @error_handler
    def mission_pause():
        """Pause mission."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        result = run_async(app.mission_service.pause_mission())
        return jsonify(result)

    @app.route('/api/mission/resume', methods=['POST'])
    @error_handler
    def mission_resume():
        """Resume mission."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        result = run_async(app.mission_service.resume_mission())
        return jsonify(result)

    @app.route('/api/mission/abort', methods=['POST'])
    @error_handler
    def mission_abort():
        """Abort mission."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        result = run_async(app.mission_service.abort_mission())
        return jsonify(result)

    @app.route('/api/mission/progress', methods=['GET'])
    @error_handler
    def mission_progress():
        """Get mission progress."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        progress = run_async(app.mission_service.get_progress())
        return jsonify(progress)

    @app.route('/api/mission/history', methods=['GET'])
    @error_handler
    def mission_history():
        """Get mission history."""
        if not app.mission_service:
            return jsonify({"error": "Mission service not initialized"}), 500

        history = run_async(app.mission_service.get_history())
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

        latest = run_async(app.telemetry_service.get_latest())
        return jsonify(latest)

    @app.route('/api/telemetry/history', methods=['GET'])
    @error_handler
    def telemetry_history():
        """Get telemetry history."""
        if not app.telemetry_service:
            return jsonify({"error": "Telemetry service not initialized"}), 500

        count = request.args.get('count', 10, type=int)
        history = run_async(app.telemetry_service.get_history(count=count))
        return jsonify({"count": len(history), "data": history})

    @app.route('/api/telemetry/stats', methods=['GET'])
    @error_handler
    def telemetry_stats():
        """Get telemetry statistics."""
        if not app.telemetry_service:
            return jsonify({"error": "Telemetry service not initialized"}), 500

        stats = run_async(app.telemetry_service.get_statistics())
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

        status = run_async(app.failsafe_service.get_status())
        return jsonify(status)

    @app.route('/api/failsafe/events', methods=['GET'])
    @error_handler
    def failsafe_events():
        """Get failsafe events."""
        if not app.failsafe_service:
            return jsonify({"error": "Failsafe service not initialized"}), 500

        limit = request.args.get('limit', 50, type=int)
        events = run_async(app.failsafe_service.get_events(limit=limit))
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

        result = run_async(app.fleet_service.add_drone(name, host, port))
        return jsonify(result)

    @app.route('/api/fleet/remove-drone/<drone_id>', methods=['DELETE'])
    @error_handler
    def fleet_remove_drone(drone_id):
        """Remove drone from fleet."""
        result = run_async(app.fleet_service.remove_drone(drone_id))
        return jsonify(result)

    @app.route('/api/fleet/status', methods=['GET'])
    @error_handler
    def fleet_status():
        """Get status of all drones in fleet."""
        result = run_async(app.fleet_service.get_fleet_status())
        return jsonify(result)

    @app.route('/api/fleet/conflicts', methods=['GET'])
    @error_handler
    def fleet_conflicts():
        """Check for airspace conflicts."""
        result = run_async(app.fleet_service.check_conflicts())
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

        result = run_async(app.fleet_service.coordinated_takeoff(drone_names, altitude, delay))
        return jsonify(result)

    @app.route('/api/fleet/broadcast', methods=['POST'])
    @error_handler
    def fleet_broadcast():
        """Broadcast command to all drones."""
        data = request.json or {}
        command = data.get('command')

        if not command:
            return jsonify({"error": "Command required"}), 400

        result = run_async(app.fleet_service.broadcast_command(command, data))
        return jsonify(result)

    @app.route('/api/fleet/emergency-stop', methods=['POST'])
    @error_handler
    def fleet_emergency_stop():
        """Emergency stop all drones."""
        result = run_async(app.fleet_service.emergency_stop())
        return jsonify(result)

    # =====================================================================
    # RECORDING ENDPOINTS (VEHA 5 PHASE 3)
    # =====================================================================

    @app.route('/api/recording/start/<mission_id>', methods=['POST'])
    @error_handler
    def recording_start(mission_id):
        """Start recording a mission."""
        result = run_async(app.recording_service.start_recording(mission_id))
        return jsonify(result)

    @app.route('/api/recording/stop/<mission_id>', methods=['POST'])
    @error_handler
    def recording_stop(mission_id):
        """Stop recording and save mission."""
        result = run_async(app.recording_service.stop_recording(mission_id))
        return jsonify(result)

    @app.route('/api/recording/get/<mission_id>', methods=['GET'])
    @error_handler
    def recording_get(mission_id):
        """Get recording details."""
        result = run_async(app.recording_service.get_recording(mission_id))
        return jsonify(result)

    @app.route('/api/recording/list', methods=['GET'])
    @error_handler
    def recording_list():
        """List all recordings."""
        limit = request.args.get('limit', 50, type=int)
        result = run_async(app.recording_service.list_recordings(limit))
        return jsonify(result)

    @app.route('/api/recording/playback/<mission_id>', methods=['GET'])
    @error_handler
    def recording_playback(mission_id):
        """Get playback timeline for a recording."""
        speed = request.args.get('speed', 1.0, type=float)
        result = run_async(app.recording_service.get_playback_timeline(mission_id, speed))
        return jsonify(result)

    @app.route('/api/recording/delete/<mission_id>', methods=['DELETE'])
    @error_handler
    def recording_delete(mission_id):
        """Delete a recording."""
        result = run_async(app.recording_service.delete_recording(mission_id))
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

        result = run_async(app.geofence_service.create_zone(name, polygon, altitude_min, altitude_max))
        return jsonify(result)

    @app.route('/api/geofence/get/<zone_name>', methods=['GET'])
    @error_handler
    def geofence_get(zone_name):
        """Get geofence zone details."""
        result = run_async(app.geofence_service.get_zone(zone_name))
        return jsonify(result)

    @app.route('/api/geofence/geojson', methods=['GET'])
    @error_handler
    def geofence_geojson():
        """Return NFZ zones as GeoJSON for dashboard map (TZ §3.1)."""
        nfz_path = Path(__file__).resolve().parents[2] / "config" / "nfz_zones.geojson"
        try:
            with nfz_path.open(encoding="utf-8") as source:
                return jsonify(json.load(source))
        except OSError as exc:
            return jsonify({"error": str(exc), "type": "FeatureCollection", "features": []}), 404

    @app.route('/api/geofence/list', methods=['GET'])
    @error_handler
    def geofence_list():
        """List all geofence zones."""
        active_only = request.args.get('active', 'true', type=str).lower() == 'true'
        result = run_async(app.geofence_service.list_zones(active_only))
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

        result = run_async(app.geofence_service.update_zone(
            zone_name, polygon, altitude_min, altitude_max, active
        ))
        return jsonify(result)

    @app.route('/api/geofence/delete/<zone_name>', methods=['DELETE'])
    @error_handler
    def geofence_delete(zone_name):
        """Delete geofence zone."""
        result = run_async(app.geofence_service.delete_zone(zone_name))
        return jsonify(result)

    @app.route('/api/geofence/validate-mission', methods=['POST'])
    @error_handler
    def geofence_validate_mission():
        """Validate mission waypoints against geofence zones."""
        data = request.json or {}
        waypoints = data.get('waypoints', [])

        if not waypoints:
            return jsonify({"error": "Waypoints required"}), 400

        result = run_async(app.geofence_service.validate_mission(waypoints))
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

        result = run_async(app.geofence_service.check_position(drone_id, position))
        return jsonify(result)

    @app.route('/api/geofence/violations/<zone_name>', methods=['GET'])
    @error_handler
    def geofence_violations(zone_name):
        """Get violation history for a zone."""
        limit = request.args.get('limit', 100, type=int)
        result = run_async(app.geofence_service.get_violations(zone_name, limit))
        return jsonify(result)

    # =====================================================================
    # METRICS ENDPOINTS (VEHA 5 PHASE 5)
    # =====================================================================

    @app.route('/metrics', methods=['GET'])
    def metrics():
        """Export metrics in Prometheus format."""
        return app.metrics_service.get_prometheus_metrics(), 200, {'Content-Type': 'text/plain; charset=utf-8'}

    @app.route('/api/metrics/summary', methods=['GET'])
    @error_handler
    def metrics_summary():
        """Get metrics summary in JSON format."""
        summary = app.metrics_service.get_metrics_summary()
        return jsonify({
            "success": True,
            "metrics": summary,
        })

    @app.route('/api/metrics/update', methods=['POST'])
    @error_handler
    def metrics_update():
        """Manually update metrics from services."""
        try:
            # Update metrics from active services
            if app.fleet_service:
                fleet_status = run_async(app.fleet_service.get_fleet_status())
                app.metrics_service.update_fleet_metrics(fleet_status)

            if app.telemetry_service:
                telemetry_stats = run_async(app.telemetry_service.get_statistics())
                app.metrics_service.update_telemetry_metrics(telemetry_stats)

            if app.geofence_service:
                zones = run_async(app.geofence_service.list_zones())
                geofence_data = {
                    "zones_active": zones.get("count", 0),
                    "violations_total": 0,  # Would need to aggregate from zones
                }
                app.metrics_service.update_geofence_metrics(geofence_data)

            return jsonify({
                "success": True,
                "message": "Metrics updated",
                "metrics": app.metrics_service.get_metrics_summary(),
            })

        except Exception as e:
            logger.error(f"Metrics update error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

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
        app.vision_clients['detection'].discard(client_id)
        app.vision_clients['alert'].discard(client_id)
        logger.info(
            f"Client disconnected: {client_id} (total: {len(app.clients)})"
        )

    @socketio.on('start_telemetry')
    def on_start_telemetry():
        """Start telemetry streaming to this client."""
        client_id = request.sid
        if app.telemetry_service:
            app.telemetry_service.register_client(client_id)
            app.pending_telemetry_clients.discard(client_id)
            emit('telemetry_started', {'client_id': client_id})
        else:
            app.pending_telemetry_clients.add(client_id)
            emit('telemetry_started', {
                'client_id': client_id,
                'pending': True,
                'message': 'Awaiting drone initialize — click Initialize SITL',
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
            result = run_async(app.fleet_service.get_fleet_status())
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
                    result = run_async(app.fleet_service.get_fleet_status())
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

    # ---- CV vision subscriptions (Мерей) ----
    @socketio.on('subscribe_detections')
    def on_subscribe_detections():
        client_id = request.sid
        app.vision_clients['detection'].add(client_id)
        emit('response', {'status': 'subscribed', 'event_type': 'vision_detection'})

    @socketio.on('subscribe_alerts')
    def on_subscribe_alerts():
        client_id = request.sid
        app.vision_clients['alert'].add(client_id)
        emit('response', {'status': 'subscribed', 'event_type': 'vision_alert'})

    def _relay_vision(event_type, payload):
        targets = app.vision_clients.get(
            'detection' if event_type == 'vision_detection' else 'alert',
            set(),
        )
        for sid in tuple(targets):
            socketio.emit(event_type, payload, to=sid)

    if app.vision_socket_handler is not None:
        app.vision_socket_handler.subscribe(
            'vision_detection',
            lambda payload: _relay_vision('vision_detection', payload),
        )
        app.vision_socket_handler.subscribe(
            'vision_alert',
            lambda payload: _relay_vision('vision_alert', payload),
        )

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
