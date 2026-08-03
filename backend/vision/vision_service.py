"""Vision event service: store, rate-limit, schema validation, error journal."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

from backend.vision_contracts import VisionEvent


class VisionEventStore:
    """In-memory storage for vision events."""

    def __init__(self, max_events: int = 1000):
        self.events: List[VisionEvent] = []
        self.max_events = max_events
        self.event_map: Dict[str, VisionEvent] = {}

    def add_event(self, event: VisionEvent) -> None:
        self.events.append(event)
        self.event_map[event.event_id] = event
        if len(self.events) > self.max_events:
            oldest = self.events.pop(0)
            self.event_map.pop(oldest.event_id, None)

    def get_event(self, event_id: str) -> Optional[VisionEvent]:
        return self.event_map.get(event_id)

    def get_latest(self, limit: int = 10) -> List[VisionEvent]:
        return list(reversed(self.events[-limit:]))

    def get_all_events(self) -> List[VisionEvent]:
        return list(self.events)

    def get_events_by_class(self, class_name: str) -> List[VisionEvent]:
        return [e for e in self.events if e.class_name == class_name]

    def clear(self) -> None:
        self.events.clear()
        self.event_map.clear()


class VisionService:
    """Core service for handling vision events without inventing GPS."""

    def __init__(self, store: Optional[VisionEventStore] = None, error_journal_size: int = 200):
        self.store = store or VisionEventStore()
        self.last_event_time = None
        self.event_rate_limit_per_sec = 10
        self.last_alert_time = None
        self._errors: Deque[Dict] = deque(maxlen=error_journal_size)
        self.camera_available = True
        self.model_loaded = True
        self.stream_ok = True

    def log_error(self, code: str, message: str, details: Optional[Dict] = None) -> Dict:
        """Append to error journal — does not crash the dashboard."""
        entry = {
            "timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "code": code,
            "message": message,
            "details": details or {},
        }
        self._errors.appendleft(entry)
        return entry

    def get_errors(self, limit: int = 50) -> List[Dict]:
        return list(self._errors)[:limit]

    def clear_errors(self) -> None:
        self._errors.clear()

    def set_runtime_status(
        self,
        *,
        camera_available: Optional[bool] = None,
        model_loaded: Optional[bool] = None,
        stream_ok: Optional[bool] = None,
    ) -> None:
        if camera_available is not None:
            self.camera_available = camera_available
        if model_loaded is not None:
            self.model_loaded = model_loaded
        if stream_ok is not None:
            self.stream_ok = stream_ok

    def process_detection(
        self,
        class_name: str,
        confidence: float,
        bbox: List[int],
        latitude: float,
        longitude: float,
        snapshot_url: str,
        source_id: str,
        processing_latency_ms: Optional[int] = None,
    ) -> Optional[VisionEvent]:
        """
        Store a detection if rate limit and schema allow.

        Returns None (no alert) when rate-limited, invalid coords, or schema fails.
        Never invents coordinates.
        """
        if not self.model_loaded:
            self.log_error("model_not_loaded", "Vision model is not loaded")
            return None
        if not self.camera_available:
            self.log_error("camera_unavailable", "Camera is unavailable")
            return None
        if not self.stream_ok:
            self.log_error("stream_broken", "Video stream is broken")
            return None

        if not self._check_rate_limit():
            self.log_error("rate_limited", "Event dropped by ≤10/s rate limit")
            return None

        if latitude is None or longitude is None:
            self.log_error("missing_gps", "Refusing alert without lat/lon")
            return None

        if not self._validate_coordinates(latitude, longitude):
            self.log_error(
                "invalid_gps",
                "Refusing alert with invalid coordinates",
                {"latitude": latitude, "longitude": longitude},
            )
            return None

        event = VisionEvent.create(
            class_name=class_name,
            confidence=confidence,
            bbox=bbox,
            latitude=latitude,
            longitude=longitude,
            snapshot_url=snapshot_url,
            source_id=source_id,
            processing_latency_ms=processing_latency_ms,
        )

        try:
            event.validate()
        except Exception as exc:
            self.log_error(
                "schema_invalid",
                f"VisionEvent failed JSON Schema validation: {exc}",
                {"event_id": event.event_id},
            )
            return None

        self.store.add_event(event)
        self.last_event_time = datetime.now(timezone.utc)
        return event

    def get_latest_events(self, limit: int = 10) -> List[Dict]:
        return [e.to_dict() for e in self.store.get_latest(limit)]

    def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        event = self.store.get_event(event_id)
        return event.to_dict() if event else None

    def get_events_by_class(self, class_name: str) -> List[Dict]:
        return [e.to_dict() for e in self.store.get_events_by_class(class_name)]

    def get_stats(self) -> Dict:
        all_events = self.store.get_all_events()
        return {
            "total_events": len(all_events),
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
            "events_by_class": {
                "Person": len(self.store.get_events_by_class("Person")),
                "Car": len(self.store.get_events_by_class("Car")),
                "Truck_Machinery": len(self.store.get_events_by_class("Truck_Machinery")),
            },
            "runtime": {
                "camera_available": self.camera_available,
                "model_loaded": self.model_loaded,
                "stream_ok": self.stream_ok,
            },
            "error_count": len(self._errors),
        }

    def _check_rate_limit(self) -> bool:
        now = datetime.now(timezone.utc)
        if self.last_alert_time is None:
            self.last_alert_time = now
            return True
        time_since_last = (now - self.last_alert_time).total_seconds()
        min_interval = 1.0 / self.event_rate_limit_per_sec
        if time_since_last >= min_interval:
            self.last_alert_time = now
            return True
        return False

    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            return False
        return -90 <= lat_f <= 90 and -180 <= lon_f <= 180

    def clear_events(self) -> None:
        self.store.clear()
        self.last_event_time = None

    def reset_rate_limit(self) -> None:
        self.last_alert_time = None
