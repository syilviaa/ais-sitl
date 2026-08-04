"""WebSocket rate-limited broadcaster for vision_detection / vision_alert."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Dict, List


class VisionSocketHandler:
    def __init__(self, rate_limit_per_sec: int = 10):
        self.rate_limit_per_sec = rate_limit_per_sec
        self.subscribers: Dict[str, List[Callable]] = {
            "vision_detection": [],
            "vision_alert": [],
        }
        self.event_count_per_sec = 0
        self.last_count_reset = datetime.now(timezone.utc)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        self.subscribers.setdefault(event_type, []).append(callback)

    def broadcast(self, event_type: str, data: Dict, enforce_rate_limit: bool = True) -> bool:
        if enforce_rate_limit and not self._check_rate_limit():
            return False
        if event_type not in self.subscribers:
            return False
        payload = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "data": data,
        }
        for callback in self.subscribers[event_type]:
            try:
                callback(payload)
            except Exception:
                pass
        return True

    def broadcast_detection(self, event_dict: Dict) -> bool:
        return self.broadcast("vision_detection", event_dict)

    def broadcast_alert(self, event_dict: Dict) -> bool:
        return self.broadcast("vision_alert", event_dict)

    def _check_rate_limit(self) -> bool:
        now = datetime.now(timezone.utc)
        if (now - self.last_count_reset).total_seconds() >= 1.0:
            self.event_count_per_sec = 0
            self.last_count_reset = now
            return True
        if self.event_count_per_sec < self.rate_limit_per_sec:
            self.event_count_per_sec += 1
            return True
        return False
