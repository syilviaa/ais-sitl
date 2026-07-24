#!/usr/bin/env python3
"""
Start AIS SITL Web Dashboard Backend

Veha 4 - REST API + WebSocket server
Available at: http://127.0.0.1:5000
"""

import logging
import sys

from src.backend.app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Start the backend server."""
    logger.info("=" * 70)
    logger.info("🚁 AIS SITL Web Dashboard - Backend Server (Veha 4)")
    logger.info("=" * 70)

    # Create Flask app and SocketIO
    config = {
        'DEBUG': True,
        'ENV': 'development',
    }

    try:
        app, socketio = create_app(config)

        logger.info("")
        logger.info("📡 REST API Endpoints:")
        logger.info("  GET    /api/health                - Health check")
        logger.info("  POST   /api/drone/initialize       - Connect to drone")
        logger.info("  GET    /api/drone/status           - Drone status")
        logger.info("  POST   /api/drone/wait-ready       - Wait for GPS/home")
        logger.info("  POST   /api/drone/arm              - Arm motors")
        logger.info("  POST   /api/drone/disarm           - Disarm motors")
        logger.info("  POST   /api/drone/takeoff          - Takeoff")
        logger.info("  POST   /api/drone/land             - Land")
        logger.info("  POST   /api/drone/hold             - Hold position")
        logger.info("  POST   /api/drone/rtl              - Return to Launch")
        logger.info("  POST   /api/mission/validate       - Validate mission")
        logger.info("  POST   /api/mission/upload         - Upload mission")
        logger.info("  POST   /api/mission/start          - Start mission")
        logger.info("  POST   /api/mission/pause          - Pause mission")
        logger.info("  POST   /api/mission/resume         - Resume mission")
        logger.info("  POST   /api/mission/abort          - Abort mission")
        logger.info("  GET    /api/mission/progress       - Get progress")
        logger.info("  GET    /api/mission/history        - Get history")
        logger.info("  GET    /api/telemetry/latest       - Latest telemetry")
        logger.info("  GET    /api/telemetry/history      - Telemetry history")
        logger.info("  GET    /api/telemetry/stats        - Telemetry stats")
        logger.info("  GET    /api/failsafe/status        - Failsafe status")
        logger.info("  GET    /api/failsafe/events        - Failsafe events")

        logger.info("")
        logger.info("🌐 WebSocket Events:")
        logger.info("  connect              - Client connected")
        logger.info("  disconnect           - Client disconnected")
        logger.info("  start_telemetry      - Start 10 Hz stream")
        logger.info("  stop_telemetry       - Stop streaming")

        logger.info("")
        logger.info("=" * 70)
        logger.info("🚀 Starting server at http://127.0.0.1:5000")
        logger.info("=" * 70)
        logger.info("")

        # Start server
        socketio.run(
            app,
            host='127.0.0.1',
            port=5000,
            debug=True,
            use_reloader=True,
        )

    except KeyboardInterrupt:
        logger.info("\n⚠️  Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
