"""Geo validation: control points and meter-error checks for Pixel-to-GPS.

camera_pitch_deg convention (same as GeoCalculator / Zhanel):
  negative = down, -90 = nadir, 0 = horizon.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Dict, List, Optional
import math

from backend.geo.geo_calculator import GeoTelemetry

if TYPE_CHECKING:
    from backend.geo.geo_calculator import GeoCalculator


@dataclass
class ControlPoint:
    """Synthetic control point for geo validation."""

    pixel_x: int
    pixel_y: int
    expected_lat: float
    expected_lon: float
    scenario_name: str
    altitude_m: float
    camera_pitch_deg: float = -90.0
    drone_yaw_deg: float = 0.0
    camera_yaw_deg: float = 0.0


@dataclass
class ScenarioResult:
    scenario_name: str
    altitude_m: float
    camera_pitch_deg: float
    error_m: float
    calculated_lat: float
    calculated_lon: float
    expected_lat: float
    expected_lon: float
    within_10m: bool


class GeoValidator:
    """Validation utility for Pixel-to-GPS calculations."""

    DRONE_LAT = 37.7749
    DRONE_LON = -122.4194
    HFOV_DEG = 62.0
    VFOV_DEG = 48.0
    FRAME_W = 1920
    FRAME_H = 1080

    @classmethod
    def get_control_points(cls) -> List[ControlPoint]:
        """
        Control points at 50/75/100 m and look-down pitches -90/-75/-60.

        Frame-center expected GPS = drone position (model projects center to nadir ray).
        Edge points at nadir use independent flat-earth FOV projection for expected lon.
        """
        points: List[ControlPoint] = []

        for alt in (50.0, 75.0, 100.0):
            for pitch in (-90.0, -75.0, -60.0):
                points.append(
                    ControlPoint(
                        pixel_x=960,
                        pixel_y=540,
                        expected_lat=cls.DRONE_LAT,
                        expected_lon=cls.DRONE_LON,
                        scenario_name=f"{int(alt)}m_pitch{int(pitch)}_center",
                        altitude_m=alt,
                        camera_pitch_deg=pitch,
                    )
                )

            # Left / right edge at nadir (-90)
            half_width_m = alt * math.tan(math.radians(cls.HFOV_DEG / 2.0))
            lon_delta = (half_width_m / 6371000.0 * (180 / math.pi)) / math.cos(
                math.radians(cls.DRONE_LAT)
            )
            points.append(
                ControlPoint(
                    pixel_x=0,
                    pixel_y=540,
                    expected_lat=cls.DRONE_LAT,
                    expected_lon=cls.DRONE_LON - lon_delta,
                    scenario_name=f"{int(alt)}m_nadir_left_edge",
                    altitude_m=alt,
                    camera_pitch_deg=-90.0,
                )
            )
            points.append(
                ControlPoint(
                    pixel_x=1920,
                    pixel_y=540,
                    expected_lat=cls.DRONE_LAT,
                    expected_lon=cls.DRONE_LON + lon_delta,
                    scenario_name=f"{int(alt)}m_nadir_right_edge",
                    altitude_m=alt,
                    camera_pitch_deg=-90.0,
                )
            )

        return points

    @staticmethod
    def calculate_error_m(
        calculated_lat: float,
        calculated_lon: float,
        expected_lat: float,
        expected_lon: float,
    ) -> float:
        """Haversine error in meters."""
        earth = 6371000.0
        lat1_rad = math.radians(calculated_lat)
        lat2_rad = math.radians(expected_lat)
        delta_lat = math.radians(expected_lat - calculated_lat)
        delta_lon = math.radians(expected_lon - calculated_lon)
        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return earth * c

    @staticmethod
    def validate_error_bounds(error_m: float, max_error_m: float = 10.0) -> bool:
        return error_m <= max_error_m

    @classmethod
    def telemetry_for_point(cls, point: ControlPoint) -> GeoTelemetry:
        return GeoTelemetry(
            timestamp="2026-08-03T12:00:00Z",
            latitude=cls.DRONE_LAT,
            longitude=cls.DRONE_LON,
            altitude_m=point.altitude_m,
            drone_yaw_deg=point.drone_yaw_deg,
            camera_pitch_deg=point.camera_pitch_deg,
            camera_yaw_deg=point.camera_yaw_deg,
            hfov_deg=cls.HFOV_DEG,
            vfov_deg=cls.VFOV_DEG,
            frame_width=cls.FRAME_W,
            frame_height=cls.FRAME_H,
        )

    @classmethod
    def run_mae_report(
        cls,
        calculator: Optional["GeoCalculator"] = None,
        max_error_m: float = 10.0,
    ) -> Dict:
        """Run pixel_to_gps on all control points; return MAE / max error summary."""
        from backend.geo.geo_calculator import GeoCalculator

        calc = calculator or GeoCalculator()
        results: List[ScenarioResult] = []

        for point in cls.get_control_points():
            telemetry = cls.telemetry_for_point(point)
            lat, lon = calc.pixel_to_gps((point.pixel_x, point.pixel_y), telemetry)
            error = cls.calculate_error_m(
                lat, lon, point.expected_lat, point.expected_lon
            )
            results.append(
                ScenarioResult(
                    scenario_name=point.scenario_name,
                    altitude_m=point.altitude_m,
                    camera_pitch_deg=point.camera_pitch_deg,
                    error_m=round(error, 3),
                    calculated_lat=lat,
                    calculated_lon=lon,
                    expected_lat=point.expected_lat,
                    expected_lon=point.expected_lon,
                    within_10m=error <= max_error_m,
                )
            )

        errors = [r.error_m for r in results]
        center_errors = [r.error_m for r in results if "center" in r.scenario_name]
        mae = sum(errors) / len(errors) if errors else 0.0
        center_mae = sum(center_errors) / len(center_errors) if center_errors else 0.0
        max_err = max(errors) if errors else 0.0

        return {
            "mae_m": round(mae, 3),
            "center_mae_m": round(center_mae, 3),
            "max_error_m": round(max_err, 3),
            "target_max_m": max_error_m,
            "target_mae_range_m": [5.0, 10.0],
            "camera_pitch_convention": "negative_down_nadir_minus_90",
            "scenarios": [asdict(r) for r in results],
            "pass_center_max_10m": all(e <= max_error_m for e in center_errors),
            "notes": (
                "camera_pitch_deg: negative=down, -90=nadir, 0=horizon. "
                "Center points should stay within 10 m."
            ),
        }
