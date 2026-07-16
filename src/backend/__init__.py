"""AIS Backend API server module."""

from .mavlink_server import create_app

__all__ = ["create_app"]
__version__ = "0.1.0"
