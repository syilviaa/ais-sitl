#!/usr/bin/env python3
"""
AIS SITL Platform - Main entry point for backend server.

Starts full REST API + Socket.IO (same as run_backend.py).

Usage:
    python main.py
    python main.py --host 0.0.0.0 --port 5000
"""

import argparse
import logging
import sys

from src.backend.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="AIS SITL Platform Backend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=5000, help="Server port")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AIS SITL Platform - Backend API + WebSocket")
    logger.info("=" * 60)
    logger.info("  GET  /api/health")
    logger.info("  WS   /socket.io/  → start_telemetry → telemetry")
    logger.info("=" * 60)

    app, socketio = create_app({"DEBUG": args.debug, "ENV": "development"})
    try:
        socketio.run(
            app,
            host=args.host,
            port=args.port,
            debug=args.debug,
            allow_unsafe_werkzeug=True,
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        return 0
    except Exception as e:
        logger.error("Server error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
