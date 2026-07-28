"""
WSGI entry point for production (gunicorn, Render)
"""

import logging
import os

from src.backend.database import init_db

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

try:
    init_db()
except Exception as exc:
    logging.getLogger(__name__).warning(
        "Database init failed; API will start without persistence: %s", exc
    )

from src.backend.app import create_app

# Create app for production
config = {
    "DEBUG": os.getenv("FLASK_DEBUG", "False") == "True",
    "ENV": os.getenv("FLASK_ENV", "production"),
}

app, socketio = create_app(config)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
