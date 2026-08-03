"""Computer vision primitives for the AIS SITL CV MVP."""

from .detector import VisionDetector
from .models import BoundingBox, Detection, DetectorResult, VisionClass

__all__ = [
    "BoundingBox",
    "Detection",
    "DetectorResult",
    "VisionClass",
    "VisionDetector",
]
