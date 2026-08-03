import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional, Tuple
import jsonschema


@dataclass
class TelemetrySnapshot:
    timestamp: str
    latitude: float
    longitude: float
    altitude_m: float
    drone_yaw_deg: float
    camera_pitch_deg: float
    camera_yaw_deg: float
    hfov_deg: float
    vfov_deg: float
    frame_width: int
    frame_height: int

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)

    def validate(self):
        """Validate telemetry against schema."""
        with open("schema_telemetry.json", "r") as f:
            schema = json.load(f)
        jsonschema.validate(self.to_dict(), schema)


@dataclass
class VisionEvent:
    event_id: str
    timestamp: str
    class_name: str
    confidence: float
    bbox: List[int]
    latitude: float
    longitude: float
    snapshot_url: str
    source_id: str
    processing_latency_ms: Optional[int] = None
    track_id: Optional[str] = None

    def to_dict(self):
        data = asdict(self)
        data = {k: v for k, v in data.items() if v is not None}
        return data

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)

    def validate(self):
        """Validate event against schema."""
        with open("schema_vision_event.json", "r") as f:
            schema = json.load(f)
        jsonschema.validate(self.to_dict(), schema)

    @classmethod
    def create(
        cls,
        class_name: str,
        confidence: float,
        bbox: List[int],
        latitude: float,
        longitude: float,
        snapshot_url: str,
        source_id: str,
        processing_latency_ms: Optional[int] = None,
        track_id: Optional[str] = None,
    ):
        """Factory method to create a new VisionEvent with UUID and UTC timestamp."""
        utc_now = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        return cls(
            event_id=str(uuid.uuid4()),
            timestamp=utc_now,
            class_name=class_name,
            confidence=confidence,
            bbox=bbox,
            latitude=latitude,
            longitude=longitude,
            snapshot_url=snapshot_url,
            source_id=source_id,
            processing_latency_ms=processing_latency_ms,
            track_id=track_id,
        )
