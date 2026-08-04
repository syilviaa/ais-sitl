"""Orchestrate detection, geolocation, snapshots and backend events."""

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from src.backend.services.vision_contracts import VisionEvent

from .snapshots import SnapshotWriter


class VisionPipeline:
    """Convert one video frame into zero or more geolocated events."""

    def __init__(
        self,
        detector,
        geo_locator,
        snapshot_dir,
        snapshot_url_prefix="/api/vision/snapshots",
        latency_target_ms=1000.0,
        monotonic_clock=None,
        utc_now=None,
    ):
        if not isinstance(snapshot_url_prefix, str) or not snapshot_url_prefix:
            raise ValueError("snapshot_url_prefix cannot be blank")
        if latency_target_ms <= 0:
            raise ValueError("latency_target_ms must be positive")
        self.detector = detector
        self.geo_locator = geo_locator
        self.snapshot_writer = SnapshotWriter(snapshot_dir)
        self.snapshot_url_prefix = snapshot_url_prefix.rstrip("/")
        self.latency_target_ms = float(latency_target_ms)
        self._monotonic_clock = monotonic_clock or perf_counter
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self.last_timing = None

    def process_frame(self, frame, telemetry, source_id="unknown"):
        """Run the complete CV flow for a single frame."""
        if telemetry is None:
            raise ValueError("Telemetry cannot be None")
        self.last_timing = None
        frame_received_at = self._utc_now()
        frame_received_tick = self._monotonic_clock()
        result = self.detector.detect(frame, source_id=source_id)
        events = []

        for detection in result.detections:
            latitude, longitude = self.geo_locator.pixel_to_gps(
                detection.bbox.center,
                telemetry,
            )
            event_id = str(uuid4())
            snapshot_url = (
                f"{self.snapshot_url_prefix}/{event_id}.jpg"
            )
            event = VisionEvent.from_detection(
                detection,
                latitude=latitude,
                longitude=longitude,
                snapshot_url=snapshot_url,
                source_id=result.source_id,
                event_id=event_id,
                timestamp=result.timestamp,
            )

            self.snapshot_writer.save(frame, detection, event_id)
            events.append(event)

            alert_created_at = self._utc_now()
            latency_ms = (
                self._monotonic_clock() - frame_received_tick
            ) * 1000.0
            self.last_timing = {
                "frame_received_at": self._format_utc(frame_received_at),
                "alert_created_at": self._format_utc(alert_created_at),
                "latency_ms": latency_ms,
                "within_target": latency_ms <= self.latency_target_ms,
            }

        return events

    @staticmethod
    def _format_utc(value):
        if value.tzinfo is None:
            raise ValueError("latency timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
