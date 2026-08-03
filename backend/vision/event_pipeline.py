"""DetectorResult + telemetry → Pixel-to-GPS → VisionEvent (no false GPS)."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from backend.geo.geo_calculator import BBox, GeoCalculator
from backend.vision.socket_handler import VisionSocketHandler
from backend.vision.vision_service import VisionService
from backend.vision_contracts import TelemetrySnapshot, VisionEvent


class VisionEventPipeline:
    """Merei integration seam for Zhanel's DetectorResult handoff."""

    def __init__(
        self,
        service: Optional[VisionService] = None,
        calculator: Optional[GeoCalculator] = None,
        socket_handler: Optional[VisionSocketHandler] = None,
    ):
        self.service = service or VisionService()
        self.calculator = calculator or GeoCalculator()
        self.socket_handler = socket_handler

    def process(
        self,
        *,
        class_name: str,
        confidence: float,
        bbox: Sequence[int],
        telemetry: Optional[TelemetrySnapshot],
        snapshot_url: str,
        source_id: str,
        processing_latency_ms: Optional[int] = None,
        emit_socket: bool = True,
    ) -> Optional[VisionEvent]:
        """
        Build VisionEvent from detection + telemetry.

        If telemetry is missing/invalid, logs error and returns None — no fake lat/lon.
        """
        if telemetry is None:
            self.service.log_error(
                "missing_telemetry",
                "Cannot geolocate detection without telemetry; alert suppressed",
                {"class_name": class_name, "source_id": source_id},
            )
            return None

        try:
            telemetry.validate()
        except Exception as exc:
            self.service.log_error(
                "invalid_telemetry",
                f"Telemetry failed schema validation: {exc}",
                {"source_id": source_id},
            )
            return None

        box = BBox(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        gps = self.calculator.safe_pixel_to_gps((box.center_x, box.center_y), telemetry)
        if gps is None:
            self.service.log_error(
                "geo_failed",
                "Pixel-to-GPS failed; alert suppressed (no false coordinates)",
                {
                    "class_name": class_name,
                    "bbox": list(bbox),
                    "altitude_m": getattr(telemetry, "altitude_m", None),
                },
            )
            return None

        lat, lon = gps
        event = self.service.process_detection(
            class_name=class_name,
            confidence=confidence,
            bbox=[int(x) for x in bbox],
            latitude=lat,
            longitude=lon,
            snapshot_url=snapshot_url,
            source_id=source_id,
            processing_latency_ms=processing_latency_ms,
        )

        if event is None:
            return None

        if emit_socket and self.socket_handler is not None:
            payload = event.to_dict()
            self.socket_handler.broadcast_detection(payload)
            self.socket_handler.broadcast_alert(payload)

        return event
