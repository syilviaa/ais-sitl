"""Typed models and class mapping for CV detections."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class VisionClass(str, Enum):
    """The three classes required by CV MVP v1.0."""

    PERSON = "Person"
    CAR = "Car"
    TRUCK_MACHINERY = "Truck_Machinery"


# YOLOv8 COCO ids. The pretrained COCO model has no dedicated machinery
# class; for MVP v1.0 COCO "truck" is exposed as Truck_Machinery and the
# limitation must remain visible in the documentation.
COCO_TO_VISION_CLASS = {
    0: VisionClass.PERSON,
    2: VisionClass.CAR,
    7: VisionClass.TRUCK_MACHINERY,
}


@dataclass(frozen=True)
class BoundingBox:
    """Pixel coordinates in x1, y1, x2, y2 order."""

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self):
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("Bounding box must have positive width and height")

    @property
    def center(self):
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def to_list(self):
        return [self.x1, self.y1, self.x2, self.y2]


@dataclass(frozen=True)
class Detection:
    """One normalized detection returned by the CV module."""

    class_name: VisionClass
    confidence: float
    bbox: BoundingBox

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1")

    def to_dict(self):
        return {
            "class_name": self.class_name.value,
            "confidence": self.confidence,
            "bbox": self.bbox.to_list(),
            "bbox_center": list(self.bbox.center),
        }


@dataclass
class DetectorResult:
    """Normalized result for one frame."""

    frame_id: str
    timestamp: str
    frame_width: int
    frame_height: int
    detections: List[Detection] = field(default_factory=list)
    source_id: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "source_id": self.source_id,
            "detections": [item.to_dict() for item in self.detections],
            "metadata": dict(self.metadata),
        }
