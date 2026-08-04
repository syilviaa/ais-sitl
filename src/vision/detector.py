"""YOLO-backed detector for local files and RTSP streams.

Heavy CV dependencies are imported only when the real adapters are used.
Unit tests can inject a lightweight backend and video source.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Protocol
from uuid import uuid4

from .models import (
    COCO_TO_VISION_CLASS,
    BoundingBox,
    Detection,
    DetectorResult,
)


class DetectorBackend(Protocol):
    """Backend contract used by VisionDetector."""

    def predict(self, frame) -> Iterable[dict]:
        """Return dicts with class_id, confidence and bbox."""


class UltralyticsBackend:
    """Lazy adapter around an Ultralytics YOLO model."""

    def __init__(self, model_path="yolov8n.pt", device=None):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "CV dependencies are missing. Install requirements-cv.txt"
            ) from exc
        self.model = YOLO(model_path)
        self.device = device

    def predict(self, frame):
        results = self.model.predict(
            source=frame,
            verbose=False,
            device=self.device,
        )
        if not results:
            return []
        detections = []
        for box in results[0].boxes:
            detections.append({
                "class_id": int(box.cls[0].item()),
                "confidence": float(box.conf[0].item()),
                "bbox": [float(value) for value in box.xyxy[0].tolist()],
            })
        return detections


class OpenCVVideoSource:
    """Frame iterator supporting a local file or an RTSP URL."""

    def __init__(self, source):
        self.source = str(source)
        self._capture = None

    def __enter__(self):
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "OpenCV is missing. Install requirements-cv.txt"
            ) from exc
        is_rtsp = self.source.lower().startswith(("rtsp://", "rtsps://"))
        if not is_rtsp and not Path(self.source).is_file():
            raise FileNotFoundError(f"Video source not found: {self.source}")
        self._capture = cv2.VideoCapture(self.source)
        if not self._capture.isOpened():
            self._capture.release()
            self._capture = None
            raise RuntimeError(f"Cannot open video source: {self.source}")
        return self

    def __iter__(self):
        if self._capture is None:
            raise RuntimeError("Video source must be opened with a context manager")
        while True:
            ok, frame = self._capture.read()
            if not ok:
                return
            yield frame

    def __exit__(self, exc_type, exc, traceback):
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class VisionDetector:
    """Normalize and filter detections for the three MVP classes."""

    def __init__(self, backend: Optional[DetectorBackend] = None,
                 confidence_threshold: float = 0.65):
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        self.backend = backend or UltralyticsBackend()
        self.confidence_threshold = confidence_threshold

    def detect(self, frame, source_id="unknown", timestamp=None):
        if frame is None:
            raise ValueError("Frame cannot be None")
        shape = getattr(frame, "shape", None)
        if not shape or len(shape) < 2:
            raise ValueError("Frame must expose height and width in shape")
        height, width = int(shape[0]), int(shape[1])
        if height <= 0 or width <= 0:
            raise ValueError("Frame dimensions must be positive")

        normalized = []
        for raw in self.backend.predict(frame):
            class_name = COCO_TO_VISION_CLASS.get(int(raw["class_id"]))
            confidence = float(raw["confidence"])
            if class_name is None or confidence < self.confidence_threshold:
                continue
            box = BoundingBox(*[float(value) for value in raw["bbox"]])
            normalized.append(Detection(class_name, confidence, box))

        captured_at = timestamp or datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        return DetectorResult(
            frame_id=str(uuid4()),
            timestamp=captured_at,
            frame_width=width,
            frame_height=height,
            source_id=source_id,
            detections=normalized,
        )

    def warmup(self, frame):
        """Prime the inference backend without producing a working result."""
        if frame is None:
            raise ValueError("Frame cannot be None")
        shape = getattr(frame, "shape", None)
        if not shape or len(shape) < 2:
            raise ValueError("Frame must expose height and width in shape")
        height, width = int(shape[0]), int(shape[1])
        if height <= 0 or width <= 0:
            raise ValueError("Frame dimensions must be positive")
        list(self.backend.predict(frame))
        return None

    def detect_source(self, source, max_frames=None):
        """Yield DetectorResult values from a local path or RTSP URL."""
        with OpenCVVideoSource(source) as video:
            for index, frame in enumerate(video):
                if max_frames is not None and index >= max_frames:
                    return
                yield self.detect(frame, source_id=str(source))
