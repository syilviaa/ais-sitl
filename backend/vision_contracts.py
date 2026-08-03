"""CV data contracts: TelemetrySnapshot and VisionEvent with JSON Schema validation."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import jsonschema

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_TELEMETRY = _REPO_ROOT / "schema_telemetry.json"
_SCHEMA_VISION = _REPO_ROOT / "schema_vision_event.json"

_telemetry_schema_cache = None
_vision_schema_cache = None


def _load_schema(path: Path, cache_attr: str):
    global _telemetry_schema_cache, _vision_schema_cache
    if cache_attr == "telemetry":
        if _telemetry_schema_cache is None:
            with open(path, "r", encoding="utf-8") as f:
                _telemetry_schema_cache = json.load(f)
        return _telemetry_schema_cache
    if _vision_schema_cache is None:
        with open(path, "r", encoding="utf-8") as f:
            _vision_schema_cache = json.load(f)
    return _vision_schema_cache


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
        schema = _load_schema(_SCHEMA_TELEMETRY, "telemetry")
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
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)

    def validate(self):
        schema = _load_schema(_SCHEMA_VISION, "vision")
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
        utc_now = (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
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
