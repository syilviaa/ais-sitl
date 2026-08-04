"""Thread-safe storage and Socket.IO rate limiting for vision events."""

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

from .vision_contracts import VisionEvent


class SlidingWindowRateLimiter:
    """Allow at most ``limit`` operations in any rolling one-second window."""

    def __init__(self, limit=10, clock=None):
        if limit <= 0:
            raise ValueError("limit must be positive")
        self.limit = int(limit)
        self._clock = clock or monotonic
        self._timestamps = deque()
        self._lock = Lock()

    def allow(self):
        now = self._clock()
        with self._lock:
            while self._timestamps and now - self._timestamps[0] >= 1.0:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.limit:
                return False
            self._timestamps.append(now)
            return True


class VisionEventService:
    """Keep recent validated events and a non-fatal error journal."""

    def __init__(self, max_events=1000, max_errors=200):
        if max_events <= 0 or max_errors <= 0:
            raise ValueError("history limits must be positive")
        self._events = deque(maxlen=int(max_events))
        self._by_id = {}
        self._errors = deque(maxlen=int(max_errors))
        self._lock = Lock()

    def add(self, event):
        if not isinstance(event, VisionEvent):
            raise TypeError("event must be a VisionEvent")
        with self._lock:
            if len(self._events) == self._events.maxlen:
                self._by_id.pop(self._events[0].event_id, None)
            self._events.append(event)
            self._by_id[event.event_id] = event
        return event

    def latest(self, limit=10):
        limit = max(1, min(int(limit), 100))
        with self._lock:
            return list(reversed(list(self._events)[-limit:]))

    def all(self, class_name=None):
        with self._lock:
            events = list(self._events)
        if class_name is not None:
            events = [event for event in events if event.class_name == class_name]
        return events

    def get(self, event_id):
        with self._lock:
            return self._by_id.get(event_id)

    def log_error(self, code, message, details=None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z"),
            "code": str(code),
            "message": str(message),
            "details": dict(details or {}),
        }
        with self._lock:
            self._errors.appendleft(entry)
        return entry

    def errors(self, limit=50):
        limit = max(1, min(int(limit), 200))
        with self._lock:
            return list(self._errors)[:limit]

    def stats(self):
        events = self.all()
        return {
            "total_events": len(events),
            "events_by_class": {
                class_name: sum(
                    event.class_name == class_name for event in events
                )
                for class_name in ("Person", "Car", "Truck_Machinery")
            },
            "error_count": len(self.errors(200)),
        }
