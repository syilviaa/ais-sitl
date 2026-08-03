"""
Unit tests for GeoCalculator / GeoValidator only.

camera_pitch_deg: negative = looking down, -90 = nadir, 0 = horizon
(aligned with Zhanel VisionTelemetry; NOT the old +90-as-nadir convention).
"""
import pytest

from backend.geo.geo_calculator import BBox, GeoCalculator, GeoTelemetry
from backend.geo.geo_validation import GeoValidator


def make_telemetry(**overrides):
    data = dict(
        timestamp="2026-08-03T12:00:00Z",
        latitude=37.7749,
        longitude=-122.4194,
        altitude_m=75,
        drone_yaw_deg=0,
        camera_pitch_deg=-70,  # look-down (Zhanel convention)
        camera_yaw_deg=0,
        hfov_deg=62,
        vfov_deg=48,
        frame_width=1920,
        frame_height=1080,
    )
    data.update(overrides)
    return GeoTelemetry(**data)


class TestBBox:
    def test_bbox_center(self):
        bbox = BBox(100, 150, 200, 400)
        assert bbox.center_x == 150
        assert bbox.center_y == 275


class TestCameraPitchConvention:
    def test_rejects_positive_pitch_legacy_nadir(self):
        """Old Merey tests used +70/+90; calculator must reject that convention."""
        calc = GeoCalculator()
        with pytest.raises(ValueError, match="negative"):
            calc.pixel_to_gps((960, 540), make_telemetry(camera_pitch_deg=70))

        with pytest.raises(ValueError, match="negative"):
            calc.pixel_to_gps((960, 540), make_telemetry(camera_pitch_deg=90))

    def test_accepts_zhanel_negative_lookdown(self):
        calc = GeoCalculator()
        lat, lon = calc.pixel_to_gps(
            (960, 540), make_telemetry(camera_pitch_deg=-60)
        )
        assert isinstance(lat, float) and isinstance(lon, float)

    def test_nadir_is_minus_90(self):
        calc = GeoCalculator()
        lat, lon = calc.pixel_to_gps(
            (960, 540), make_telemetry(camera_pitch_deg=-90)
        )
        assert abs(lat - 37.7749) < 1e-9
        assert abs(lon - (-122.4194)) < 1e-9


class TestGeoCalculator:
    @pytest.fixture
    def calculator(self):
        return GeoCalculator()

    @pytest.fixture
    def base_telemetry(self):
        return make_telemetry(camera_pitch_deg=-70)

    def test_pixel_to_gps_frame_center(self, calculator, base_telemetry):
        lat, lon = calculator.pixel_to_gps((960, 540), base_telemetry)
        assert abs(lat - 37.7749) < 0.0001
        assert abs(lon - (-122.4194)) < 0.0001

    def test_pixel_to_gps_left_edge(self, calculator, base_telemetry):
        lat_center, lon_center = calculator.pixel_to_gps((960, 540), base_telemetry)
        lat_left, lon_left = calculator.pixel_to_gps((0, 540), base_telemetry)
        assert lon_left < lon_center

    def test_pixel_to_gps_right_edge(self, calculator, base_telemetry):
        lat_center, lon_center = calculator.pixel_to_gps((960, 540), base_telemetry)
        lat_right, lon_right = calculator.pixel_to_gps((1920, 540), base_telemetry)
        assert lon_right > lon_center

    def test_pixel_to_gps_out_of_bounds(self, calculator, base_telemetry):
        with pytest.raises(ValueError):
            calculator.pixel_to_gps((2000, 540), base_telemetry)
        with pytest.raises(ValueError):
            calculator.pixel_to_gps((960, 1200), base_telemetry)

    def test_pixel_to_gps_altitude_scaling(self, calculator):
        t50 = make_telemetry(altitude_m=50, camera_pitch_deg=-70)
        t100 = make_telemetry(altitude_m=100, camera_pitch_deg=-70)
        lat_50, lon_50 = calculator.pixel_to_gps((0, 540), t50)
        lat_100, lon_100 = calculator.pixel_to_gps((0, 540), t100)
        d50 = calculator.calculate_distance_m(37.7749, -122.4194, lat_50, lon_50)
        d100 = calculator.calculate_distance_m(37.7749, -122.4194, lat_100, lon_100)
        assert d100 > d50

    def test_haversine_distance(self, calculator):
        distance = calculator.calculate_distance_m(
            37.7749, -122.4194, 37.7750, -122.4194
        )
        assert 10 < distance < 15

    def test_safe_pixel_to_gps_none_telemetry(self, calculator):
        assert calculator.safe_pixel_to_gps((960, 540), None) is None

    def test_rejects_altitude_out_of_range(self, calculator):
        with pytest.raises(ValueError):
            calculator.pixel_to_gps((960, 540), make_telemetry(altitude_m=20))


class TestPixelToGpsControlPointsErrorMeters:
    """Requested handoff test: pixel_to_gps on control points → error in meters."""

    def test_pixel_to_gps_control_points_error_m(self):
        calculator = GeoCalculator()
        validator = GeoValidator()
        points = validator.get_control_points()
        assert len(points) > 0

        errors = []
        for point in points:
            telemetry = validator.telemetry_for_point(point)
            lat, lon = calculator.pixel_to_gps((point.pixel_x, point.pixel_y), telemetry)
            error_m = validator.calculate_error_m(
                lat, lon, point.expected_lat, point.expected_lon
            )
            errors.append((point.scenario_name, error_m))
            # Center / look-down rays must stay within demo bound
            if "center" in point.scenario_name:
                assert error_m <= 10.0, (
                    f"{point.scenario_name}: error {error_m:.2f} m exceeds 10 m"
                )

        assert any(name.endswith("_center") for name, _ in errors)
        assert all(err >= 0 for _, err in errors)

    def test_mae_report_uses_negative_pitch(self):
        report = GeoValidator.run_mae_report()
        assert report["camera_pitch_convention"] == "negative_down_nadir_minus_90"
        assert report["pass_center_max_10m"] is True
        pitches = {s["camera_pitch_deg"] for s in report["scenarios"]}
        assert pitches <= {-90.0, -75.0, -60.0}
        assert all(p < 0 for p in pitches)


class TestGeoValidator:
    def test_control_points_exist(self):
        assert len(GeoValidator.get_control_points()) > 0

    def test_control_point_altitudes(self):
        altitudes = {p.altitude_m for p in GeoValidator.get_control_points()}
        assert {50.0, 75.0, 100.0} <= altitudes

    def test_control_point_pitches_are_negative(self):
        pitches = {p.camera_pitch_deg for p in GeoValidator.get_control_points()}
        assert all(p < 0 for p in pitches)
        assert -90.0 in pitches

    def test_calculate_error_zero(self):
        error = GeoValidator.calculate_error_m(
            37.7749, -122.4194, 37.7749, -122.4194
        )
        assert error < 0.1

    def test_calculate_error_meters(self):
        error = GeoValidator.calculate_error_m(
            37.7749, -122.4194, 37.7750, -122.4194
        )
        assert 10 < error < 15

    def test_validate_error_bounds_pass(self):
        assert GeoValidator.validate_error_bounds(5.0, max_error_m=10.0) is True

    def test_validate_error_bounds_fail(self):
        assert GeoValidator.validate_error_bounds(15.0, max_error_m=10.0) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
