"""Orchestrate detection, geolocation, snapshots and backend events."""

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
    ):
        if not isinstance(snapshot_url_prefix, str) or not snapshot_url_prefix:
            raise ValueError("snapshot_url_prefix cannot be blank")
        self.detector = detector
        self.geo_locator = geo_locator
        self.snapshot_writer = SnapshotWriter(snapshot_dir)
        self.snapshot_url_prefix = snapshot_url_prefix.rstrip("/")

    def process_frame(self, frame, telemetry, source_id="unknown"):
        """Run the complete CV flow for a single frame."""
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

        return events
