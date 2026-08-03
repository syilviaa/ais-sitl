"""Input service for test/MAVLink-like JSON used by the CV module.

This does not create a second flight telemetry collector. It accepts an
explicit payload and validates it for Pixel-to-GPS consumers.
"""

from collections import deque

from .vision_contracts import VisionTelemetry


class VisionTelemetryService:
    """Validate and retain recent CV telemetry samples."""

    def __init__(self, history_size=100):
        if history_size <= 0:
            raise ValueError("history_size must be positive")
        self._history = deque(maxlen=history_size)

    def ingest(self, payload):
        telemetry = VisionTelemetry.from_dict(payload)
        self._history.append(telemetry)
        return telemetry

    def latest(self):
        return self._history[-1] if self._history else None

    def history(self):
        return list(self._history)
