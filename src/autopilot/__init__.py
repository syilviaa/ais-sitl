"""AIS Autopilot module for flight control."""

try:
    from .plane import Drone, Plane
    __all__ = ["Drone", "Plane"]
except ImportError:
    # MAVSDK not available in production
    Drone = None
    Plane = None
    __all__ = []

__version__ = "0.1.0"
