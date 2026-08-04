"""Contracts shared by the CV pipeline and backend services."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import math
from uuid import UUID, uuid4


class VisionContractError(ValueError):
    """Raised when CV input does not satisfy the agreed contract."""


def _finite_number(payload, name):
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VisionContractError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise VisionContractError(f"{name} must be finite")
    return value


def parse_utc_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise VisionContractError("timestamp must be ISO 8601 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise VisionContractError("timestamp must be valid ISO 8601") from exc
    if parsed.tzinfo != timezone.utc:
        raise VisionContractError("timestamp must use UTC")
    return value


@dataclass(frozen=True)
class VisionTelemetry:
    timestamp: str
    latitude: float
    longitude: float
    altitude_m: float
    drone_yaw_deg: float
    camera_pitch_deg: float
    camera_yaw_deg: float
    hfov_deg: float
    vfov_deg: float
    frame_width: int = 1920
    frame_height: int = 1080

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict):
            raise VisionContractError("telemetry payload must be an object")
        timestamp = parse_utc_timestamp(payload.get("timestamp"))
        latitude = _finite_number(payload, "latitude")
        longitude = _finite_number(payload, "longitude")
        altitude = _finite_number(payload, "altitude_m")
        yaw = _finite_number(payload, "drone_yaw_deg")
        pitch = _finite_number(payload, "camera_pitch_deg")
        camera_yaw = _finite_number(payload, "camera_yaw_deg")
        hfov = _finite_number(payload, "hfov_deg")
        vfov = _finite_number(payload, "vfov_deg")
        width = payload.get("frame_width", 1920)
        height = payload.get("frame_height", 1080)

        if not -90 <= latitude <= 90:
            raise VisionContractError("latitude must be in [-90, 90]")
        if not -180 <= longitude <= 180:
            raise VisionContractError("longitude must be in [-180, 180]")
        if not 50 <= altitude <= 100:
            raise VisionContractError("altitude_m must be in [50, 100]")
        if not 0 <= yaw < 360 or not -180 <= camera_yaw <= 180:
            raise VisionContractError("yaw values are outside supported range")
        if not -90 <= pitch <= 90:
            raise VisionContractError("camera_pitch_deg must be in [-90, 90]")
        if not 0 < hfov < 180 or not 0 < vfov < 180:
            raise VisionContractError("camera FOV must be in (0, 180)")
        if not isinstance(width, int) or not isinstance(height, int):
            raise VisionContractError("frame dimensions must be integers")
        if width <= 0 or height <= 0:
            raise VisionContractError("frame dimensions must be positive")

        return cls(
            timestamp, latitude, longitude, altitude, yaw, pitch,
            camera_yaw, hfov, vfov, width, height,
        )

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class VisionEvent:
    """JSON-ready backend event created from one detector result."""

    event_id: str
    timestamp: str
    class_name: str
    confidence: float
    bbox: tuple
    latitude: float
    longitude: float
    snapshot_url: str
    source_id: str
    processing_latency_ms: float | None = None

    def __post_init__(self):
        try:
            parsed_id = UUID(self.event_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise VisionContractError("event_id must be a UUID") from exc
        if str(parsed_id) != self.event_id:
            raise VisionContractError("event_id must use canonical UUID format")

        parse_utc_timestamp(self.timestamp)
        if self.class_name not in {"Person", "Car", "Truck_Machinery"}:
            raise VisionContractError("class_name is not supported")
        if not 0.65 <= self.confidence <= 1.0:
            raise VisionContractError("confidence must be in [0.65, 1]")
        if len(self.bbox) != 4:
            raise VisionContractError("bbox must contain four coordinates")
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in self.bbox
        ):
            raise VisionContractError("bbox coordinates must be finite numbers")
        if self.bbox[2] <= self.bbox[0] or self.bbox[3] <= self.bbox[1]:
            raise VisionContractError("bbox must have positive width and height")
        if not -90 <= self.latitude <= 90:
            raise VisionContractError("latitude must be in [-90, 90]")
        if not -180 <= self.longitude <= 180:
            raise VisionContractError("longitude must be in [-180, 180]")
        if not self.snapshot_url:
            raise VisionContractError("snapshot_url cannot be blank")
        if not self.source_id:
            raise VisionContractError("source_id cannot be blank")
        if self.processing_latency_ms is not None:
            if (
                isinstance(self.processing_latency_ms, bool)
                or not isinstance(self.processing_latency_ms, (int, float))
                or not math.isfinite(self.processing_latency_ms)
                or self.processing_latency_ms < 0
            ):
                raise VisionContractError(
                    "processing_latency_ms must be a non-negative finite number"
                )

    @classmethod
    def from_detection(
        cls,
        detection,
        latitude,
        longitude,
        snapshot_url,
        source_id,
        event_id=None,
        timestamp=None,
        processing_latency_ms=None,
    ):
        captured_at = timestamp or datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        return cls(
            event_id=event_id or str(uuid4()),
            timestamp=captured_at,
            class_name=detection.class_name.value,
            confidence=float(detection.confidence),
            bbox=tuple(detection.bbox.to_list()),
            latitude=float(latitude),
            longitude=float(longitude),
            snapshot_url=str(snapshot_url),
            source_id=str(source_id),
            processing_latency_ms=(
                None
                if processing_latency_ms is None
                else float(processing_latency_ms)
            ),
        )

    def to_dict(self):
        payload = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "bbox": list(self.bbox),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "snapshot_url": self.snapshot_url,
            "source_id": self.source_id,
        }
        if self.processing_latency_ms is not None:
            payload["processing_latency_ms"] = self.processing_latency_ms
        return payload



def load_schema(name):
    """Load a checked-in schema for clients that use jsonschema."""
    root = Path(__file__).resolve().parents[3]
    path = root / "config" / "vision" / name
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)
