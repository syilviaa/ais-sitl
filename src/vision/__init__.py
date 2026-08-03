"""Computer vision primitives for the AIS SITL CV MVP."""

from .detector import VisionDetector
from .models import BoundingBox, Detection, DetectorResult, VisionClass
from .pipeline import VisionPipeline
from .snapshots import SnapshotPaths, SnapshotWriter

__all__ = [
    "BoundingBox",
    "Detection",
    "DetectorResult",
    "VisionClass",
    "VisionDetector",
    "VisionPipeline",
    "SnapshotPaths",
    "SnapshotWriter",
]
