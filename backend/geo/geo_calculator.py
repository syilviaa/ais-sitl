import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
from backend.vision_contracts import TelemetrySnapshot


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


class GeoCalculator:
    """
    Converts pixel coordinates to GPS coordinates using flat-earth model.
    Suitable for small areas (MVP scope).

    Assumptions:
    - Flat earth model (valid for MVP small areas)
    - Pinhole camera model
    - Fixed camera orientation relative to drone
    """

    EARTH_RADIUS_M = 6371000.0

    def __init__(self):
        pass

    def pixel_to_gps(
        self,
        bbox_center: Tuple[float, float],
        telemetry: TelemetrySnapshot,
    ) -> Tuple[float, float]:
        """
        Convert bbox center pixel coordinates to GPS lat/lon.

        Args:
            bbox_center: (pixel_x, pixel_y) in frame coordinates
            telemetry: TelemetrySnapshot with drone position and camera orientation

        Returns:
            (latitude, longitude) of bbox center

        Raises:
            ValueError: if telemetry is invalid or calculation fails
        """
        pixel_x, pixel_y = bbox_center

        # Validate inputs
        if not (0 <= pixel_x <= telemetry.frame_width):
            raise ValueError(f"pixel_x {pixel_x} out of frame bounds [0, {telemetry.frame_width}]")
        if not (0 <= pixel_y <= telemetry.frame_height):
            raise ValueError(f"pixel_y {pixel_y} out of frame bounds [0, {telemetry.frame_height}]")

        # Frame center in pixels
        frame_center_x = telemetry.frame_width / 2.0
        frame_center_y = telemetry.frame_height / 2.0

        # Offset from frame center in pixels
        offset_x_px = pixel_x - frame_center_x
        offset_y_px = pixel_y - frame_center_y

        # Convert to normalized coordinates (-1 to +1)
        norm_x = offset_x_px / frame_center_x
        norm_y = offset_y_px / frame_center_y

        # Get ground distance from camera using flat-earth model
        alt = telemetry.altitude_m
        hfov_rad = math.radians(telemetry.hfov_deg)
        vfov_rad = math.radians(telemetry.vfov_deg)

        # Distance from camera to frame edges at this altitude
        # For pinhole model: tan(fov/2) = (frame_size/2) / distance_to_plane
        distance_to_ground_h = (telemetry.frame_width / 2.0) / math.tan(hfov_rad / 2.0)
        distance_to_ground_v = (telemetry.frame_height / 2.0) / math.tan(vfov_rad / 2.0)

        # Average for both axes (assume symmetric optics)
        distance_to_ground = (distance_to_ground_h + distance_to_ground_v) / 2.0

        # Camera pitch: 90 = nadir (straight down), 0 = horizon
        camera_pitch_rad = math.radians(telemetry.camera_pitch_deg)

        # Horizontal distance from camera to ground point along camera view
        # For nadir (pitch=90): all altitude projects to ground distance
        # For non-nadir: apply cosine correction
        horizontal_distance = alt / math.cos(camera_pitch_rad - math.pi / 2.0)

        # Ground offset in camera frame (before rotation)
        ground_offset_x_cam = horizontal_distance * math.tan(hfov_rad / 2.0) * norm_x
        ground_offset_y_cam = horizontal_distance * math.tan(vfov_rad / 2.0) * norm_y

        # Apply camera yaw and drone yaw to get absolute bearing
        total_yaw_rad = math.radians(telemetry.drone_yaw_deg + telemetry.camera_yaw_deg)

        # Rotate camera frame to world frame
        cos_yaw = math.cos(total_yaw_rad)
        sin_yaw = math.sin(total_yaw_rad)

        ground_offset_x = ground_offset_x_cam * cos_yaw - ground_offset_y_cam * sin_yaw
        ground_offset_y = ground_offset_x_cam * sin_yaw + ground_offset_y_cam * cos_yaw

        # Convert ground offset to lat/lon using flat-earth model
        lat_offset_m = ground_offset_y
        lon_offset_m = ground_offset_x

        # Convert to degrees (rough approximation valid for small areas)
        lat_delta = lat_offset_m / self.EARTH_RADIUS_M * (180 / math.pi)
        lon_delta = (lon_offset_m / self.EARTH_RADIUS_M * (180 / math.pi)) / math.cos(
            math.radians(telemetry.latitude)
        )

        result_lat = telemetry.latitude + lat_delta
        result_lon = telemetry.longitude + lon_delta

        return result_lat, result_lon

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
            + math.cos(lat1_rad)
            * math.cos(lat2_rad)
            * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return self.EARTH_RADIUS_M * c
