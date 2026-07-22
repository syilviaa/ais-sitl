"""
AIS SITL Web Dashboard Backend

Flask application with REST API and WebSocket support for drone monitoring
and mission control.

Status: Veha 4 (July 25-28, 2026)
Owner: Ready for development
"""

import asyncio
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)


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
    )

    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'ok',
            'version': '0.1.0',
            'veha': 4,
        })

    # Register blueprints (when routes are implemented)
    # from .routes import drone_routes, mission_routes, telemetry_routes
    # app.register_blueprint(drone_routes.bp)
    # app.register_blueprint(mission_routes.bp)
    # app.register_blueprint(telemetry_routes.bp)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f'Internal server error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

    # WebSocket events (when implemented)
    # @socketio.on('connect')
    # def on_connect():
    #     logger.info('Client connected')

    # @socketio.on('disconnect')
    # def on_disconnect():
    #     logger.info('Client disconnected')

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
