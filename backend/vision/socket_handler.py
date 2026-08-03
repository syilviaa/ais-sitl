"""WebSocket handler for real-time vision events."""
from typing import Dict, List, Callable, Optional
from datetime import datetime, timezone


class VisionSocketHandler:
    """Manages WebSocket subscriptions and broadcasts for vision events."""

    def __init__(self, rate_limit_per_sec: int = 10):
        self.rate_limit_per_sec = rate_limit_per_sec
        self.subscribers: Dict[str, List[Callable]] = {
            "vision_detection": [],
            "vision_alert": [],
        }
        self.last_broadcast_time = {}
        self.event_count_per_sec = 0
        self.last_count_reset = datetime.now(timezone.utc)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)

    def broadcast(self, event_type: str, data: Dict, enforce_rate_limit: bool = True) -> bool:
        """
        Broadcast event to all subscribers.

        Args:
            event_type: Type of event (vision_detection, vision_alert, etc.)
            data: Event data to broadcast
            enforce_rate_limit: Whether to enforce rate limiting

        Returns:
            True if event was broadcasted, False if rate-limited
        """
        if enforce_rate_limit and not self._check_rate_limit():
            return False

        if event_type not in self.subscribers:
            return False

        utc_now = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        payload = {
            "event_type": event_type,
            "timestamp": utc_now,
            "data": data,
        }

        for callback in self.subscribers[event_type]:
            try:
                callback(payload)
            except Exception as e:
                print(f"Error broadcasting to subscriber: {e}")

        return True

    def broadcast_detection(self, event_dict: Dict) -> bool:
        """Broadcast a detection event."""
        return self.broadcast("vision_detection", event_dict)

    def broadcast_alert(self, event_dict: Dict) -> bool:
        """Broadcast an alert event."""
        return self.broadcast("vision_alert", event_dict)

    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows broadcast."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_count_reset).total_seconds()

        if elapsed >= 1.0:
            self.event_count_per_sec = 0
            self.last_count_reset = now
            return True

        if self.event_count_per_sec < self.rate_limit_per_sec:
            self.event_count_per_sec += 1
            return True

        return False

    def get_subscriber_count(self, event_type: str = None) -> int:
        """Get number of subscribers for event type."""
        if event_type is None:
            return sum(len(subs) for subs in self.subscribers.values())
        return len(self.subscribers.get(event_type, []))

    def clear_subscribers(self) -> None:
        """Clear all subscribers."""
        for event_type in self.subscribers:
            self.subscribers[event_type].clear()
