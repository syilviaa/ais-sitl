from dataclasses import dataclass
from typing import List, Tuple
import math


@dataclass
class ControlPoint:
    """Synthetic control point for geo validation."""
    pixel_x: int
    pixel_y: int
    expected_lat: float
    expected_lon: float
    scenario_name: str
    altitude_m: float


class GeoValidator:
    """Validation utility for Pixel-to-GPS calculations."""

    @staticmethod
    def get_control_points() -> List[ControlPoint]:
        """
        Synthetic control points for testing at different altitudes.

        Drone position: (37.7749, -122.4194) - San Francisco
        """
        return [
            # 50m altitude tests
            ControlPoint(
                pixel_x=960,  # frame center
                pixel_y=540,
                expected_lat=37.7749,
                expected_lon=-122.4194,
                scenario_name="50m_frame_center",
                altitude_m=50,
            ),
            ControlPoint(
                pixel_x=0,  # left edge
                pixel_y=540,
                expected_lat=37.7749,
                expected_lon=-122.4234,
                scenario_name="50m_left_edge",
                altitude_m=50,
            ),
            ControlPoint(
                pixel_x=1920,  # right edge
                pixel_y=540,
                expected_lat=37.7749,
                expected_lon=-122.4154,
                scenario_name="50m_right_edge",
                altitude_m=50,
            ),
            # 75m altitude tests
            ControlPoint(
                pixel_x=960,
                pixel_y=540,
                expected_lat=37.7749,
                expected_lon=-122.4194,
                scenario_name="75m_frame_center",
                altitude_m=75,
            ),
            # 100m altitude tests
            ControlPoint(
                pixel_x=960,
                pixel_y=540,
                expected_lat=37.7749,
                expected_lon=-122.4194,
                scenario_name="100m_frame_center",
                altitude_m=100,
            ),
        ]

    @staticmethod
    def calculate_error_m(
        calculated_lat: float,
        calculated_lon: float,
        expected_lat: float,
        expected_lon: float,
    ) -> float:
        """Calculate error in meters using Haversine distance."""
        EARTH_RADIUS_M = 6371000.0

        lat1_rad = math.radians(calculated_lat)
        lat2_rad = math.radians(expected_lat)
        delta_lat = math.radians(expected_lat - calculated_lat)
        delta_lon = math.radians(expected_lon - calculated_lon)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad)
            * math.cos(lat2_rad)
            * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return EARTH_RADIUS_M * c

    @staticmethod
    def validate_error_bounds(error_m: float, max_error_m: float = 10.0) -> bool:
        """Check if error is within acceptable bounds."""
        return error_m <= max_error_m
