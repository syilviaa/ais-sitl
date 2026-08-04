"""Vision event store, rate limit, error journal (Мерей — CV MVP day 4)."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional
from uuid import uuid4

from src.backend.services.vision_contracts import VisionContractError, VisionEvent


class VisionEventStore:
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

    def get_all(self) -> List[VisionEvent]:
        return list(self.events)

    def get_by_class(self, class_name: str) -> List[VisionEvent]:
        return [e for e in self.events if e.class_name == class_name]

    def clear(self) -> None:
        self.events.clear()
        self.event_map.clear()


class VisionService:
    """Persist VisionEvents; never invent GPS; no false alerts on failures."""

    def __init__(self, store: Optional[VisionEventStore] = None, error_journal_size: int = 200):
        self.store = store or VisionEventStore()
        self.last_event_time: Optional[datetime] = None
        self.event_rate_limit_per_sec = 10
        self._last_alert_time: Optional[datetime] = None
        self._errors: Deque[Dict] = deque(maxlen=error_journal_size)
        self.camera_available = True
        self.model_loaded = True
        self.stream_ok = True
        self.max_telemetry_age_s = 5.0

    def log_error(self, code: str, message: str, details: Optional[Dict] = None) -> Dict:
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

    def ingest_event(self, event: VisionEvent, *, emit_check: bool = True) -> Optional[VisionEvent]:
        """
        Accept a validated VisionEvent from the detector pipeline.

        Returns None (no alert) on rate-limit / runtime failure — never fabricates coords.
        """
        if not self.model_loaded:
            self.log_error("model_not_loaded", "Vision model is not loaded — alert suppressed")
            return None
        if not self.camera_available:
            self.log_error("camera_unavailable", "Camera unavailable — alert suppressed")
            return None
        if not self.stream_ok:
            self.log_error("stream_broken", "Video stream broken — alert suppressed")
            return None

        if emit_check and not self._check_rate_limit():
            self.log_error("rate_limited", "Event dropped by ≤10/s rate limit")
            return None

        if event.latitude is None or event.longitude is None:
            self.log_error("missing_gps", "Refusing alert without lat/lon")
            return None

        try:
            # Re-run contract checks (frozen dataclass validates in __post_init__)
            VisionEvent(**event.to_dict())
        except (VisionContractError, TypeError, ValueError) as exc:
            self.log_error(
                "schema_invalid",
                f"VisionEvent failed contract validation: {exc}",
                {"event_id": getattr(event, "event_id", None)},
            )
            return None

        self.store.add_event(event)
        self.last_event_time = datetime.now(timezone.utc)
        return event

    def create_and_ingest(
        self,
        *,
        class_name: str,
        confidence: float,
        bbox,
        latitude: float,
        longitude: float,
        snapshot_url: str,
        source_id: str,
        event_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Optional[VisionEvent]:
        """Build VisionEvent from fields and ingest (used by API tests / ingest route)."""
        try:
            event = VisionEvent(
                event_id=event_id or str(uuid4()),
                timestamp=timestamp
                or datetime.now(timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"),
                class_name=class_name,
                confidence=float(confidence),
                bbox=tuple(bbox),
                latitude=float(latitude),
                longitude=float(longitude),
                snapshot_url=str(snapshot_url),
                source_id=str(source_id),
            )
        except (VisionContractError, TypeError, ValueError) as exc:
            self.log_error("schema_invalid", str(exc))
            return None
        return self.ingest_event(event)

    def reject_stale_or_invalid_telemetry(
        self, telemetry_timestamp: Optional[str], now: Optional[datetime] = None
    ) -> bool:
        """
        Return True if telemetry is usable; False if stale/invalid (and log — no alert).
        """
        if not telemetry_timestamp:
            self.log_error("invalid_telemetry", "Missing telemetry timestamp — alert suppressed")
            return False
        try:
            if not str(telemetry_timestamp).endswith("Z"):
                raise ValueError("not UTC Z")
            parsed = datetime.fromisoformat(str(telemetry_timestamp)[:-1] + "+00:00")
        except ValueError:
            self.log_error(
                "invalid_telemetry",
                f"Unparseable telemetry timestamp: {telemetry_timestamp}",
            )
            return False
        current = now or datetime.now(timezone.utc)
        age = (current - parsed).total_seconds()
        if age > self.max_telemetry_age_s:
            self.log_error(
                "stale_telemetry",
                f"Telemetry age {age:.1f}s exceeds {self.max_telemetry_age_s}s — alert suppressed",
                {"timestamp": telemetry_timestamp, "age_s": age},
            )
            return False
        return True

    def get_latest_events(self, limit: int = 10) -> List[Dict]:
        return [e.to_dict() for e in self.store.get_latest(limit)]

    def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        event = self.store.get_event(event_id)
        return event.to_dict() if event else None

    def get_events_by_class(self, class_name: str) -> List[Dict]:
        return [e.to_dict() for e in self.store.get_by_class(class_name)]

    def get_stats(self) -> Dict:
        return {
            "total_events": len(self.store.get_all()),
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
            "events_by_class": {
                "Person": len(self.store.get_by_class("Person")),
                "Car": len(self.store.get_by_class("Car")),
                "Truck_Machinery": len(self.store.get_by_class("Truck_Machinery")),
            },
            "runtime": {
                "camera_available": self.camera_available,
                "model_loaded": self.model_loaded,
                "stream_ok": self.stream_ok,
            },
            "error_count": len(self._errors),
            "rate_limit_per_sec": self.event_rate_limit_per_sec,
        }

    def _check_rate_limit(self) -> bool:
        now = datetime.now(timezone.utc)
        if self._last_alert_time is None:
            self._last_alert_time = now
            return True
        min_interval = 1.0 / self.event_rate_limit_per_sec
        if (now - self._last_alert_time).total_seconds() >= min_interval:
            self._last_alert_time = now
            return True
        return False

    def clear_events(self) -> None:
        self.store.clear()
        self.last_event_time = None

    def reset_rate_limit(self) -> None:
        self._last_alert_time = None
