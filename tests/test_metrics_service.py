"""
Tests for Metrics Service - Prometheus metrics export.
"""

import pytest
from src.backend.services.metrics_service import MetricsService


@pytest.fixture
def metrics_service():
    """Create a metrics service."""
    return MetricsService()


class TestMetricsFleet:
    """Test fleet metrics."""

    def test_update_fleet_metrics(self, metrics_service):
        """Test updating fleet metrics."""
        fleet_status = {
            "drones": {
                "drone1": {
                    "connected": True,
                    "battery_percent": 85.0,
                },
                "drone2": {
                    "connected": True,
                    "battery_percent": 90.0,
                },
            }
        }

        metrics_service.update_fleet_metrics(fleet_status)

        assert metrics_service.fleet_size == 2
        assert metrics_service.connected_drones == 2
        assert metrics_service.total_battery_percent == 87.5
        assert metrics_service.min_battery_percent == 85.0
        assert metrics_service.max_battery_percent == 90.0

    def test_fleet_metrics_with_disconnected(self, metrics_service):
        """Test fleet metrics with disconnected drone."""
        fleet_status = {
            "drones": {
                "drone1": {
                    "connected": True,
                    "battery_percent": 85.0,
                },
                "drone2": {
                    "connected": False,
                    "battery_percent": 10.0,
                },
            }
        }

        metrics_service.update_fleet_metrics(fleet_status)

        assert metrics_service.fleet_size == 2
        assert metrics_service.connected_drones == 1
        assert metrics_service.min_battery_percent == 10.0


class TestMetricsMissions:
    """Test mission metrics."""

    def test_update_mission_metrics(self, metrics_service):
        """Test updating mission metrics."""
        missions_data = {
            "total": 10,
            "completed": 8,
            "failed": 2,
            "total_duration": 480.0,  # 8 missions × 60 seconds avg
            "total_distance": 4000.0,  # 8 missions × 500m avg
        }

        metrics_service.update_mission_metrics(missions_data)

        assert metrics_service.missions_total == 10
        assert metrics_service.missions_completed == 8
        assert metrics_service.missions_failed == 2

    def test_record_mission_completion(self, metrics_service):
        """Test recording mission completion."""
        metrics_service.record_mission_completion(
            duration_seconds=60.0,
            distance_meters=500.0,
            success=True,
        )

        assert metrics_service.missions_total == 1
        assert metrics_service.missions_completed == 1
        assert metrics_service.missions_failed == 0
        assert metrics_service.total_mission_duration == 60.0
        assert metrics_service.total_mission_distance == 500.0

    def test_record_mission_failure(self, metrics_service):
        """Test recording mission failure."""
        metrics_service.record_mission_completion(
            duration_seconds=30.0,
            distance_meters=250.0,
            success=False,
        )

        assert metrics_service.missions_total == 1
        assert metrics_service.missions_completed == 0
        assert metrics_service.missions_failed == 1


class TestMetricsTelemetry:
    """Test telemetry metrics."""

    def test_update_telemetry_metrics(self, metrics_service):
        """Test updating telemetry metrics."""
        telemetry_stats = {
            "update_count": 1000,
            "actual_rate_hz": 9.8,
        }

        metrics_service.update_telemetry_metrics(telemetry_stats)

        assert metrics_service.telemetry_updates == 1000
        assert metrics_service.telemetry_rate_hz == 9.8


class TestMetricsGeofence:
    """Test geofence metrics."""

    def test_update_geofence_metrics(self, metrics_service):
        """Test updating geofence metrics."""
        geofence_data = {
            "violations_total": 5,
            "zones_active": 3,
        }

        metrics_service.update_geofence_metrics(geofence_data)

        assert metrics_service.geofence_violations_total == 5
        assert metrics_service.geofence_zones_active == 3

    def test_record_geofence_violation(self, metrics_service):
        """Test recording geofence violation."""
        metrics_service.record_geofence_violation()
        metrics_service.record_geofence_violation()

        assert metrics_service.geofence_violations_total == 2


class TestMetricsExport:
    """Test metrics export formats."""

    def test_get_prometheus_metrics(self, metrics_service):
        """Test Prometheus format export."""
        metrics_service.fleet_size = 2
        metrics_service.connected_drones = 2
        metrics_service.total_battery_percent = 85.0
        metrics_service.missions_total = 10
        metrics_service.missions_completed = 8

        prometheus_metrics = metrics_service.get_prometheus_metrics()

        assert "ais_sitl_fleet_size_total 2" in prometheus_metrics
        assert "ais_sitl_fleet_connected_drones 2" in prometheus_metrics
        assert "ais_sitl_fleet_battery_percent_avg 85.00" in prometheus_metrics
        assert "ais_sitl_missions_total 10" in prometheus_metrics
        assert "ais_sitl_missions_completed 8" in prometheus_metrics

    def test_get_metrics_summary(self, metrics_service):
        """Test JSON summary export."""
        metrics_service.fleet_size = 2
        metrics_service.connected_drones = 2
        metrics_service.total_battery_percent = 85.0
        metrics_service.missions_total = 10
        metrics_service.missions_completed = 8

        summary = metrics_service.get_metrics_summary()

        assert summary["fleet"]["size"] == 2
        assert summary["fleet"]["connected"] == 2
        assert summary["fleet"]["battery_avg"] == 85.0
        assert summary["missions"]["total"] == 10
        assert summary["missions"]["completed"] == 8


class TestMetricsCalculations:
    """Test metric calculations."""

    def test_mission_success_rate(self, metrics_service):
        """Test mission success rate calculation."""
        metrics_service.missions_total = 10
        metrics_service.missions_completed = 8

        summary = metrics_service.get_metrics_summary()

        assert summary["missions"]["success_rate_percent"] == 80.0

    def test_average_mission_duration(self, metrics_service):
        """Test average mission duration calculation."""
        metrics_service.missions_completed = 5
        metrics_service.total_mission_duration = 300.0  # 5 × 60 seconds

        summary = metrics_service.get_metrics_summary()

        assert summary["missions"]["avg_duration_seconds"] == 60.0

    def test_zero_missions(self, metrics_service):
        """Test calculations with zero missions."""
        metrics_service.missions_total = 0
        metrics_service.missions_completed = 0

        summary = metrics_service.get_metrics_summary()

        assert summary["missions"]["success_rate_percent"] == 0.0
        assert summary["missions"]["avg_duration_seconds"] == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
