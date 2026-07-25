"""
WSGI entry point for production (gunicorn, Render)
"""

import os
from src.backend.app import create_app

# Create app for production
config = {
    'DEBUG': os.getenv('FLASK_DEBUG', 'False') == 'True',
    'ENV': os.getenv('FLASK_ENV', 'production'),
}

app, socketio = create_app(config)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000, debug=False)
