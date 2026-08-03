from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from backend.vision_contracts import VisionEvent


class VisionEventStore:
    """In-memory storage for vision events."""

    def __init__(self, max_events: int = 1000):
        self.events: List[VisionEvent] = []
        self.max_events = max_events
        self.event_map: Dict[str, VisionEvent] = {}

    def add_event(self, event: VisionEvent) -> None:
        """Add event to store, maintaining max size."""
        self.events.append(event)
        self.event_map[event.event_id] = event

        if len(self.events) > self.max_events:
            oldest = self.events.pop(0)
            del self.event_map[oldest.event_id]

    def get_event(self, event_id: str) -> Optional[VisionEvent]:
        """Get event by ID."""
        return self.event_map.get(event_id)

    def get_latest(self, limit: int = 10) -> List[VisionEvent]:
        """Get latest N events in reverse order (newest first)."""
        return list(reversed(self.events[-limit:]))

    def get_all_events(self) -> List[VisionEvent]:
        """Get all stored events."""
        return list(self.events)

    def get_events_by_class(self, class_name: str) -> List[VisionEvent]:
        """Get all events of a specific class."""
        return [e for e in self.events if e.class_name == class_name]

    def clear(self) -> None:
        """Clear all events."""
        self.events.clear()
        self.event_map.clear()


class VisionService:
    """Core service for handling vision events."""

    def __init__(self, store: Optional[VisionEventStore] = None):
        self.store = store or VisionEventStore()
        self.last_event_time = None
        self.event_rate_limit_per_sec = 10
        self.last_alert_time = None

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
        Process a detection and add it to store if rate limit allows.

        Returns:
            VisionEvent if added to store, None if rate-limited or invalid
        """
        if not self._check_rate_limit():
            return None

        if not self._validate_coordinates(latitude, longitude):
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
        except Exception as e:
            raise ValueError(f"Event validation failed: {e}")

        self.store.add_event(event)
        self.last_event_time = datetime.now(timezone.utc)
        return event

    def get_latest_events(self, limit: int = 10) -> List[Dict]:
        """Get latest events as dictionaries."""
        events = self.store.get_latest(limit)
        return [e.to_dict() for e in events]

    def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        """Get specific event by ID."""
        event = self.store.get_event(event_id)
        return event.to_dict() if event else None

    def get_events_by_class(self, class_name: str) -> List[Dict]:
        """Get all events of a specific class."""
        events = self.store.get_events_by_class(class_name)
        return [e.to_dict() for e in events]

    def get_stats(self) -> Dict:
        """Get service statistics."""
        all_events = self.store.get_all_events()
        return {
            "total_events": len(all_events),
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
            "events_by_class": {
                "Person": len(self.store.get_events_by_class("Person")),
                "Car": len(self.store.get_events_by_class("Car")),
                "Truck_Machinery": len(self.store.get_events_by_class("Truck_Machinery")),
            },
        }

    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows new event."""
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
        """Validate GPS coordinates."""
        if not (-90 <= lat <= 90):
            return False
        if not (-180 <= lon <= 180):
            return False
        return True

    def clear_events(self) -> None:
        """Clear all stored events."""
        self.store.clear()
        self.last_event_time = None

    def reset_rate_limit(self) -> None:
        """Reset rate limit tracking (for testing)."""
        self.last_alert_time = None
