#!/usr/bin/env python3
"""
AIS SITL Platform - Main entry point for backend server.

Starts Flask API server for mission control and telemetry streaming.

Usage:
    python main.py              # Start server on localhost:5000
    python main.py --host 0.0.0.0 --port 5000
"""

import sys
import logging
import argparse
from src.backend import create_app


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AIS SITL Platform Backend Server"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=5000, help="Server port")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AIS SITL Platform - Backend API Server")
    logger.info("=" * 60)

    # Create Flask app
    app = create_app()

    # Start server
    logger.info(f"Starting server on {args.host}:{args.port}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        return 0
    except Exception as e:
        logger.error(f"Server error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
