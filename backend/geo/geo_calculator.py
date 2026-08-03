"""Pixel-to-GPS using flat-earth model (MVP, small area).

camera_pitch_deg convention (aligned with Zhanel / VisionTelemetry):
  - negative = looking down
  - 0 = horizon (level)
  - -90 = nadir (straight down)
  - positive = looking up (not used in MVP down-looking flights)

Do not pass the old “nadir = +90” convention into this calculator.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Protocol, Tuple


@dataclass
class BBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0


@dataclass(frozen=True)
class GeoTelemetry:
    """Minimal telemetry needed for Pixel-to-GPS (no API/contracts dependency)."""

    latitude: float
    longitude: float
    altitude_m: float
    drone_yaw_deg: float
    camera_pitch_deg: float
    camera_yaw_deg: float
    hfov_deg: float
    vfov_deg: float
    frame_width: int = 1920
    frame_height: int = 1080
    timestamp: str = "2026-08-03T12:00:00Z"


class TelemetryLike(Protocol):
    """Duck-typed telemetry: VisionTelemetry / TelemetrySnapshot both work."""

    latitude: float
    longitude: float
    altitude_m: float
    drone_yaw_deg: float
    camera_pitch_deg: float
    camera_yaw_deg: float
    hfov_deg: float
    vfov_deg: float
    frame_width: int
    frame_height: int


class GeoCalculator:
    """
    Converts pixel coordinates to GPS using a flat-earth + pinhole FOV model.

    Assumptions:
    - Small demo area (flat earth OK)
    - Known HFOV/VFOV, no DEM / lens distortion
    - camera_pitch_deg: negative down, -90 nadir, 0 horizon
    """

    EARTH_RADIUS_M = 6371000.0
    MIN_ALTITUDE_M = 50.0
    MAX_ALTITUDE_M = 100.0
    # Reject pitches closer to horizon than this (degrees below level).
    MIN_LOOKDOWN_DEG = 10.0  # require pitch <= -10

    def pixel_to_gps(
        self,
        bbox_center: Tuple[float, float],
        telemetry: TelemetryLike,
    ) -> Tuple[float, float]:
        """
        Convert bbox center pixel coordinates to GPS lat/lon.

        Raises:
            ValueError: invalid telemetry or out-of-bounds pixels — never invents coordinates
        """
        self._validate_telemetry(telemetry)

        pixel_x, pixel_y = bbox_center
        if not (0 <= pixel_x <= telemetry.frame_width):
            raise ValueError(
                f"pixel_x {pixel_x} out of frame bounds [0, {telemetry.frame_width}]"
            )
        if not (0 <= pixel_y <= telemetry.frame_height):
            raise ValueError(
                f"pixel_y {pixel_y} out of frame bounds [0, {telemetry.frame_height}]"
            )

        frame_center_x = telemetry.frame_width / 2.0
        frame_center_y = telemetry.frame_height / 2.0
        norm_x = (pixel_x - frame_center_x) / frame_center_x
        norm_y = (pixel_y - frame_center_y) / frame_center_y

        alt = telemetry.altitude_m
        hfov_rad = math.radians(telemetry.hfov_deg)
        vfov_rad = math.radians(telemetry.vfov_deg)

        # pitch: -90 nadir → angle_from_nadir = 0; -60 → 30° from nadir toward horizon
        angle_from_nadir_rad = math.radians(telemetry.camera_pitch_deg + 90.0)
        horizontal_distance = alt / math.cos(angle_from_nadir_rad)

        ground_offset_x_cam = horizontal_distance * math.tan(hfov_rad / 2.0) * norm_x
        ground_offset_y_cam = horizontal_distance * math.tan(vfov_rad / 2.0) * norm_y

        total_yaw_rad = math.radians(telemetry.drone_yaw_deg + telemetry.camera_yaw_deg)
        cos_yaw = math.cos(total_yaw_rad)
        sin_yaw = math.sin(total_yaw_rad)
        ground_offset_x = ground_offset_x_cam * cos_yaw - ground_offset_y_cam * sin_yaw
        ground_offset_y = ground_offset_x_cam * sin_yaw + ground_offset_y_cam * cos_yaw

        lat_delta = ground_offset_y / self.EARTH_RADIUS_M * (180 / math.pi)
        lon_delta = (
            ground_offset_x / self.EARTH_RADIUS_M * (180 / math.pi)
        ) / math.cos(math.radians(telemetry.latitude))

        return telemetry.latitude + lat_delta, telemetry.longitude + lon_delta

    def safe_pixel_to_gps(
        self,
        bbox_center: Tuple[float, float],
        telemetry: Optional[TelemetryLike],
    ) -> Optional[Tuple[float, float]]:
        """Return lat/lon or None — never fabricates coordinates on bad input."""
        if telemetry is None:
            return None
        try:
            return self.pixel_to_gps(bbox_center, telemetry)
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    def calculate_distance_m(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Haversine distance in meters."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return self.EARTH_RADIUS_M * c

    def _validate_telemetry(self, telemetry: TelemetryLike) -> None:
        if telemetry is None:
            raise ValueError("telemetry is required")

        required = [
            "latitude",
            "longitude",
            "altitude_m",
            "drone_yaw_deg",
            "camera_pitch_deg",
            "camera_yaw_deg",
            "hfov_deg",
            "vfov_deg",
            "frame_width",
            "frame_height",
        ]
        for field in required:
            if getattr(telemetry, field, None) is None:
                raise ValueError(f"missing telemetry field: {field}")

        if not (self.MIN_ALTITUDE_M <= telemetry.altitude_m <= self.MAX_ALTITUDE_M):
            raise ValueError(
                f"altitude_m {telemetry.altitude_m} outside MVP range "
                f"[{self.MIN_ALTITUDE_M}, {self.MAX_ALTITUDE_M}]"
            )
        if not (-90 <= telemetry.latitude <= 90):
            raise ValueError(f"invalid latitude: {telemetry.latitude}")
        if not (-180 <= telemetry.longitude <= 180):
            raise ValueError(f"invalid longitude: {telemetry.longitude}")
        if not (-90 <= telemetry.camera_pitch_deg <= 90):
            raise ValueError(
                f"camera_pitch_deg {telemetry.camera_pitch_deg} outside [-90, 90]"
            )
        # Looking down only for MVP; reject near-horizon / upward views
        if telemetry.camera_pitch_deg > -self.MIN_LOOKDOWN_DEG:
            raise ValueError(
                f"camera_pitch_deg={telemetry.camera_pitch_deg}: expected negative "
                f"look-down (≤ -{self.MIN_LOOKDOWN_DEG}), nadir=-90, horizon=0"
            )
        if telemetry.hfov_deg <= 0 or telemetry.vfov_deg <= 0:
            raise ValueError("FOV must be positive")
        if telemetry.frame_width <= 0 or telemetry.frame_height <= 0:
            raise ValueError("frame dimensions must be positive")
