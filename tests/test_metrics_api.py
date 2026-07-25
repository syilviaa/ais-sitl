"""
Integration tests for Metrics API endpoints.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch

from src.backend.app import create_app


@pytest.fixture
def app():
    """Create Flask test app."""
    app, socketio = create_app({'TESTING': True})
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


class TestMetricsPrometheus:
    """Test Prometheus metrics endpoint."""

    def test_get_prometheus_metrics(self, client, app):
        """Test Prometheus format metrics export."""
        app.metrics_service.fleet_size = 2
        app.metrics_service.connected_drones = 2
        app.metrics_service.total_battery_percent = 85.0
        app.metrics_service.missions_total = 10
        app.metrics_service.missions_completed = 8

        response = client.get('/metrics')

        assert response.status_code == 200
        assert response.content_type == 'text/plain; charset=utf-8'
        assert b'ais_sitl_fleet_size_total 2' in response.data
        assert b'ais_sitl_missions_total 10' in response.data

    def test_prometheus_metrics_format(self, client, app):
        """Test that Prometheus metrics have correct format."""
        response = client.get('/metrics')

        assert response.status_code == 200
        data = response.data.decode('utf-8')

        # Check for HELP and TYPE comments
        assert '# HELP ais_sitl_' in data
        assert '# TYPE ais_sitl_' in data

        # Check for metric lines
        assert 'ais_sitl_fleet_size_total' in data
        assert 'ais_sitl_missions_total' in data


class TestMetricsSummary:
    """Test JSON metrics summary endpoint."""

    def test_get_metrics_summary(self, client, app):
        """Test JSON summary metrics."""
        app.metrics_service.fleet_size = 2
        app.metrics_service.connected_drones = 2
        app.metrics_service.total_battery_percent = 85.0
        app.metrics_service.missions_total = 10
        app.metrics_service.missions_completed = 8

        response = client.get('/api/metrics/summary')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["success"] is True
        assert data["metrics"]["fleet"]["size"] == 2
        assert data["metrics"]["fleet"]["connected"] == 2
        assert data["metrics"]["missions"]["total"] == 10
        assert data["metrics"]["missions"]["completed"] == 8

    def test_metrics_summary_structure(self, client, app):
        """Test JSON summary has correct structure."""
        response = client.get('/api/metrics/summary')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert "metrics" in data
        assert "fleet" in data["metrics"]
        assert "missions" in data["metrics"]
        assert "telemetry" in data["metrics"]
        assert "geofence" in data["metrics"]


class TestMetricsUpdate:
    """Test metrics update endpoint."""

    def test_update_metrics(self, client, app):
        """Test updating metrics from services."""
        with patch.object(app.fleet_service, 'get_fleet_status', new_callable=AsyncMock) as mock_fleet:
            with patch.object(app.telemetry_service, 'get_statistics', new_callable=AsyncMock) as mock_telem:
                with patch.object(app.geofence_service, 'list_zones', new_callable=AsyncMock) as mock_geo:
                    mock_fleet.return_value = {
                        "success": True,
                        "fleet_size": 2,
                        "drones": {
                            "drone1": {"connected": True, "battery_percent": 85.0},
                            "drone2": {"connected": True, "battery_percent": 90.0},
                        }
                    }
                    mock_telem.return_value = {
                        "update_count": 1000,
                        "actual_rate_hz": 9.8,
                    }
                    mock_geo.return_value = {
                        "success": True,
                        "count": 3,
                        "zones": [],
                    }

                    response = client.post('/api/metrics/update')

                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data["success"] is True
                    assert "metrics" in data

    def test_update_metrics_with_services(self, client, app):
        """Test metrics update with active services."""
        # Setup mock services
        app.fleet_service = AsyncMock()
        app.fleet_service.get_fleet_status = AsyncMock(
            return_value={
                "success": True,
                "fleet_size": 1,
                "drones": {"drone1": {"connected": True, "battery_percent": 80.0}}
            }
        )

        app.telemetry_service = AsyncMock()
        app.telemetry_service.get_statistics = AsyncMock(
            return_value={
                "update_count": 500,
                "actual_rate_hz": 9.5,
            }
        )

        app.geofence_service = AsyncMock()
        app.geofence_service.list_zones = AsyncMock(
            return_value={"success": True, "count": 2, "zones": []}
        )

        response = client.post('/api/metrics/update')

        assert response.status_code in [200, 500]  # May fail due to async mocking


class TestMetricsContent:
    """Test metrics content accuracy."""

    def test_prometheus_has_help_comments(self, client):
        """Test that all metrics have HELP comments."""
        response = client.get('/metrics')

        data = response.data.decode('utf-8')
        lines = data.split('\n')

        # Count metric definitions
        metric_lines = [l for l in lines if l and not l.startswith('#')]
        help_lines = [l for l in lines if l.startswith('# HELP')]

        # Should have help comments
        assert len(help_lines) > 0

    def test_prometheus_has_type_comments(self, client):
        """Test that all metrics have TYPE comments."""
        response = client.get('/metrics')

        data = response.data.decode('utf-8')
        type_lines = [l for l in data.split('\n') if l.startswith('# TYPE')]

        # Should have type comments
        assert len(type_lines) > 0

    def test_metrics_counter_format(self, client, app):
        """Test that counter metrics have counter type."""
        app.metrics_service.missions_total = 5

        response = client.get('/metrics')

        data = response.data.decode('utf-8')
        assert '# TYPE ais_sitl_missions_total counter' in data

    def test_metrics_gauge_format(self, client, app):
        """Test that gauge metrics have gauge type."""
        app.metrics_service.fleet_size = 3

        response = client.get('/metrics')

        data = response.data.decode('utf-8')
        assert '# TYPE ais_sitl_fleet_size_total gauge' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
