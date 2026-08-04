"""Save annotated detector frames and per-detection JPEG crops."""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .models import Detection


@dataclass(frozen=True)
class SnapshotPaths:
    """Files produced for one vision event."""

    event_id: str
    snapshot_path: Path
    crop_path: Path
    full_path: Path


def draw_detection_box(frame, detection: Detection, color=(0, 255, 0)):
    """Draw class label + confidence on a BGR frame copy and return it."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is missing. Install requirements-cv.txt"
        ) from exc

    annotated = frame.copy()
    height, width = annotated.shape[:2]
    x1 = max(0, min(width, int(detection.bbox.x1)))
    y1 = max(0, min(height, int(detection.bbox.y1)))
    x2 = max(0, min(width, int(detection.bbox.x2)))
    y2 = max(0, min(height, int(detection.bbox.y2)))
    label = f"{detection.class_name.value} {detection.confidence:.0%}"
    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    top = max(0, y1 - th - 6)
    cv2.rectangle(annotated, (x1, top), (x1 + tw + 4, y1), color, -1)
    cv2.putText(
        annotated,
        label,
        (x1 + 2, y1 - 4),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 0),
        1,
        cv2.LINE_AA,
    )
    return annotated


def draw_detections(frame, detections, color=(0, 255, 0)):
    """Draw every detection onto one annotated frame."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is missing. Install requirements-cv.txt"
        ) from exc

    annotated = frame.copy()
    height, width = annotated.shape[:2]
    for detection in detections:
        x1 = max(0, min(width, int(detection.bbox.x1)))
        y1 = max(0, min(height, int(detection.bbox.y1)))
        x2 = max(0, min(width, int(detection.bbox.x2)))
        y2 = max(0, min(height, int(detection.bbox.y2)))
        label = f"{detection.class_name.value} {detection.confidence:.0%}"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        top = max(0, y1 - th - 6)
        cv2.rectangle(annotated, (x1, top), (x1 + tw + 4, y1), color, -1)
        cv2.putText(
            annotated,
            label,
            (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )
    return annotated


class SnapshotWriter:
    """Write TZ snapshot = object crop with box; also keep full annotated frame."""

    def __init__(self, output_dir, jpeg_quality=90):
        if not 1 <= jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")
        self.output_dir = Path(output_dir)
        self.jpeg_quality = int(jpeg_quality)

    def save(self, frame, detection: Detection, event_id: str) -> SnapshotPaths:
        if frame is None:
            raise ValueError("Frame cannot be None")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id cannot be blank")
        try:
            parsed_event_id = UUID(event_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("event_id must be a UUID") from exc
        if str(parsed_event_id) != event_id:
            raise ValueError("event_id must use canonical UUID format")

        shape = getattr(frame, "shape", None)
        if not shape or len(shape) < 2:
            raise ValueError("Frame must expose height and width in shape")
        height, width = int(shape[0]), int(shape[1])

        x1 = max(0, min(width, int(detection.bbox.x1)))
        y1 = max(0, min(height, int(detection.bbox.y1)))
        x2 = max(0, min(width, int(detection.bbox.x2)))
        y2 = max(0, min(height, int(detection.bbox.y2)))
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Detection bbox is outside the frame")

        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "OpenCV is missing. Install requirements-cv.txt"
            ) from exc

        self.output_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.output_dir / f"{event_id}.jpg"
        crop_path = self.output_dir / f"{event_id}_crop.jpg"
        full_path = self.output_dir / f"{event_id}_full.jpg"

        annotated = draw_detection_box(frame, detection)
        # TZ: snapshot = cropped object WITH the drawn box
        boxed_crop = annotated[y1:y2, x1:x2].copy()
        options = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]

        if not cv2.imwrite(str(snapshot_path), boxed_crop, options):
            raise RuntimeError(f"Cannot write snapshot: {snapshot_path}")
        if not cv2.imwrite(str(crop_path), boxed_crop, options):
            snapshot_path.unlink(missing_ok=True)
            raise RuntimeError(f"Cannot write crop: {crop_path}")
        if not cv2.imwrite(str(full_path), annotated, options):
            snapshot_path.unlink(missing_ok=True)
            crop_path.unlink(missing_ok=True)
            raise RuntimeError(f"Cannot write full frame: {full_path}")

        return SnapshotPaths(event_id, snapshot_path, crop_path, full_path)
