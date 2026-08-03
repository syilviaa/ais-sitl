import pytest
import math
from backend.geo.geo_calculator import GeoCalculator, BBox
from backend.vision_contracts import TelemetrySnapshot
from backend.geo.geo_validation import GeoValidator


class TestBBox:
    def test_bbox_center(self):
        bbox = BBox(100, 150, 200, 400)
        assert bbox.center_x == 150
        assert bbox.center_y == 275


class TestGeoCalculator:
    @pytest.fixture
    def calculator(self):
        return GeoCalculator()

    @pytest.fixture
    def base_telemetry(self):
        return TelemetrySnapshot(
            timestamp="2026-08-03T12:00:00Z",
            latitude=37.7749,
            longitude=-122.4194,
            altitude_m=75,
            drone_yaw_deg=0,
            camera_pitch_deg=70,
            camera_yaw_deg=0,
            hfov_deg=62,
            vfov_deg=48,
            frame_width=1920,
            frame_height=1080,
        )

    def test_pixel_to_gps_frame_center(self, calculator, base_telemetry):
        """Frame center should map to drone position."""
        lat, lon = calculator.pixel_to_gps((960, 540), base_telemetry)
        # Allow small error due to camera pitch
        assert abs(lat - 37.7749) < 0.0001
        assert abs(lon - (-122.4194)) < 0.0001

    def test_pixel_to_gps_left_edge(self, calculator, base_telemetry):
        """Left edge should map to left of drone."""
        lat_center, lon_center = calculator.pixel_to_gps((960, 540), base_telemetry)
        lat_left, lon_left = calculator.pixel_to_gps((0, 540), base_telemetry)
        assert lon_left < lon_center

    def test_pixel_to_gps_right_edge(self, calculator, base_telemetry):
        """Right edge should map to right of drone."""
        lat_center, lon_center = calculator.pixel_to_gps((960, 540), base_telemetry)
        lat_right, lon_right = calculator.pixel_to_gps((1920, 540), base_telemetry)
        assert lon_right > lon_center

    def test_pixel_to_gps_out_of_bounds(self, calculator, base_telemetry):
        """Out of bounds coordinates should raise ValueError."""
        with pytest.raises(ValueError):
            calculator.pixel_to_gps((2000, 540), base_telemetry)

        with pytest.raises(ValueError):
            calculator.pixel_to_gps((960, 1200), base_telemetry)

    def test_pixel_to_gps_altitude_scaling(self, calculator):
        """Higher altitude should result in larger ground coverage."""
        telemetry_50m = TelemetrySnapshot(
            timestamp="2026-08-03T12:00:00Z",
            latitude=37.7749,
            longitude=-122.4194,
            altitude_m=50,
            drone_yaw_deg=0,
            camera_pitch_deg=70,
            camera_yaw_deg=0,
            hfov_deg=62,
            vfov_deg=48,
            frame_width=1920,
            frame_height=1080,
        )

        telemetry_100m = TelemetrySnapshot(
            timestamp="2026-08-03T12:00:00Z",
            latitude=37.7749,
            longitude=-122.4194,
            altitude_m=100,
            drone_yaw_deg=0,
            camera_pitch_deg=70,
            camera_yaw_deg=0,
            hfov_deg=62,
            vfov_deg=48,
            frame_width=1920,
            frame_height=1080,
        )

        lat_50, lon_50 = calculator.pixel_to_gps((0, 540), telemetry_50m)
        lat_100, lon_100 = calculator.pixel_to_gps((0, 540), telemetry_100m)

        # Same pixel at higher altitude should be further from drone
        error_50 = calculator.calculate_distance_m(37.7749, -122.4194, lat_50, lon_50)
        error_100 = calculator.calculate_distance_m(37.7749, -122.4194, lat_100, lon_100)
        assert error_100 > error_50

    def test_haversine_distance(self, calculator):
        """Test Haversine distance calculation."""
        lat1, lon1 = 37.7749, -122.4194
        lat2, lon2 = 37.7750, -122.4194
        distance = calculator.calculate_distance_m(lat1, lon1, lat2, lon2)
        # 0.0001 degree latitude ≈ 11 meters
        assert 10 < distance < 15

    def test_missing_telemetry_fields(self, calculator):
        """Test with minimal telemetry."""
        minimal_telemetry = TelemetrySnapshot(
            timestamp="2026-08-03T12:00:00Z",
            latitude=37.7749,
            longitude=-122.4194,
            altitude_m=75,
            drone_yaw_deg=45,
            camera_pitch_deg=60,
            camera_yaw_deg=0,
            hfov_deg=62,
            vfov_deg=48,
            frame_width=1920,
            frame_height=1080,
        )
        lat, lon = calculator.pixel_to_gps((960, 540), minimal_telemetry)
        assert isinstance(lat, float) and isinstance(lon, float)


class TestGeoValidator:
    def test_control_points_exist(self):
        validator = GeoValidator()
        points = validator.get_control_points()
        assert len(points) > 0

    def test_control_point_altitudes(self):
        validator = GeoValidator()
        points = validator.get_control_points()
        altitudes = set(p.altitude_m for p in points)
        assert 50 in altitudes
        assert 75 in altitudes
        assert 100 in altitudes

    def test_calculate_error_zero(self):
        validator = GeoValidator()
        error = validator.calculate_error_m(37.7749, -122.4194, 37.7749, -122.4194)
        assert error < 0.1

    def test_calculate_error_meters(self):
        validator = GeoValidator()
        error = validator.calculate_error_m(37.7749, -122.4194, 37.7750, -122.4194)
        assert 10 < error < 15  # 0.0001 degree ≈ 11 meters

    def test_validate_error_bounds_pass(self):
        validator = GeoValidator()
        assert validator.validate_error_bounds(5.0, max_error_m=10.0) is True

    def test_validate_error_bounds_fail(self):
        validator = GeoValidator()
        assert validator.validate_error_bounds(15.0, max_error_m=10.0) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
