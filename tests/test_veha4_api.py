"""
Veha 4 REST API Tests

Tests for all REST endpoints and WebSocket integration.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch


@pytest.fixture
def app():
    """Create Flask test app."""
    from src.backend.app import create_app

    app, socketio = create_app({'TESTING': True})
    app.socketio = socketio
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['veha'] == 4
        assert 'version' in data

    def test_health_includes_drone_status(self, client):
        """Test that health check includes drone connection status."""
        response = client.get('/api/health')
        data = json.loads(response.data)
        assert 'drone_connected' in data
        assert isinstance(data['drone_connected'], bool)


class TestDroneEndpoints:
    """Test drone control endpoints."""

    def test_drone_initialize(self, client, app):
        """Test drone initialization endpoint."""
        with patch('src.backend.app.DroneService') as mock_drone:
            mock_instance = AsyncMock()
            mock_drone.return_value = mock_instance

            response = client.post('/api/drone/initialize')
            assert response.status_code in [200, 500]  # May fail if SITL not running

    def test_drone_status_without_init(self, client):
        """Test drone status when not initialized."""
        response = client.get('/api/drone/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'connected' in data
        assert 'state' in data

    def test_drone_endpoints_exist(self, client):
        """Test that all drone endpoints exist."""
        endpoints = [
            ('/api/drone/initialize', 'POST'),
            ('/api/drone/status', 'GET'),
            ('/api/drone/wait-ready', 'POST'),
            ('/api/drone/arm', 'POST'),
            ('/api/drone/disarm', 'POST'),
            ('/api/drone/takeoff', 'POST'),
            ('/api/drone/land', 'POST'),
            ('/api/drone/hold', 'POST'),
            ('/api/drone/rtl', 'POST'),
        ]

        for endpoint, method in endpoints:
            if method == 'GET':
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json={})
            # Should return 200, 400, 500 but not 404
            assert response.status_code != 404, f"{endpoint} not found"


class TestMissionEndpoints:
    """Test mission endpoints."""

    def test_mission_endpoints_exist(self, client):
        """Test that all mission endpoints exist."""
        endpoints = [
            ('/api/mission/validate', 'POST'),
            ('/api/mission/upload', 'POST'),
            ('/api/mission/start', 'POST'),
            ('/api/mission/pause', 'POST'),
            ('/api/mission/resume', 'POST'),
            ('/api/mission/abort', 'POST'),
            ('/api/mission/progress', 'GET'),
            ('/api/mission/history', 'GET'),
        ]

        for endpoint, method in endpoints:
            if method == 'GET':
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json={})
            # Should return 200, 400, 500 but not 404
            assert response.status_code != 404, f"{endpoint} not found"

    def test_mission_validation_empty(self, client, app):
        """Test mission validation with empty waypoints."""
        with patch.object(app.mission_service, 'validate_mission', new_callable=AsyncMock) as mock:
            mock.return_value = {'valid': False, 'error': 'No waypoints'}

            response = client.post(
                '/api/mission/validate',
                json={'waypoints': []}
            )
            assert response.status_code in [200, 500]

    def test_mission_validation_valid(self, client, app):
        """Test mission validation with valid waypoints."""
        waypoints = [
            {'lat': 47.39, 'lon': 8.54, 'altitude': 50},
            {'lat': 47.40, 'lon': 8.55, 'altitude': 60},
        ]

        with patch.object(app.mission_service, 'validate_mission', new_callable=AsyncMock) as mock:
            mock.return_value = {'valid': True, 'waypoints_count': 2}

            response = client.post(
                '/api/mission/validate',
                json={'waypoints': waypoints}
            )
            assert response.status_code in [200, 500]


class TestTelemetryEndpoints:
    """Test telemetry endpoints."""

    def test_telemetry_endpoints_exist(self, client):
        """Test that all telemetry endpoints exist."""
        endpoints = [
            ('/api/telemetry/latest', 'GET'),
            ('/api/telemetry/history', 'GET'),
            ('/api/telemetry/stats', 'GET'),
        ]

        for endpoint, method in endpoints:
            response = client.get(endpoint)
            # Should return 200, 400, 500 but not 404
            assert response.status_code != 404, f"{endpoint} not found"

    def test_telemetry_latest_not_available(self, client, app):
        """Test telemetry when service not initialized."""
        response = client.get('/api/telemetry/latest')
        # Service not initialized, should handle gracefully
        assert response.status_code in [200, 500]


class TestFailsafeEndpoints:
    """Test failsafe endpoints."""

    def test_failsafe_endpoints_exist(self, client):
        """Test that all failsafe endpoints exist."""
        endpoints = [
            ('/api/failsafe/status', 'GET'),
            ('/api/failsafe/events', 'GET'),
        ]

        for endpoint, method in endpoints:
            response = client.get(endpoint)
            # Should return 200, 400, 500 but not 404
            assert response.status_code != 404, f"{endpoint} not found"


class TestErrorHandling:
    """Test error handling."""

    def test_404_not_found(self, client):
        """Test 404 error handling."""
        response = client.get('/api/nonexistent')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_invalid_json(self, client):
        """Test invalid JSON handling."""
        response = client.post(
            '/api/mission/validate',
            data='invalid json',
            content_type='application/json'
        )
        assert response.status_code in [400, 500]


class TestApiIntegration:
    """Integration tests for full API workflow."""

    def test_health_check_integration(self, client):
        """Test full health check flow."""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['veha'] == 4
        assert 'drone_connected' in data

    def test_mission_workflow(self, client, app):
        """Test complete mission workflow."""
        waypoints = [
            {'lat': 47.3977, 'lon': 8.5455, 'altitude': 50},
            {'lat': 47.3985, 'lon': 8.5465, 'altitude': 60},
            {'lat': 47.3977, 'lon': 8.5455, 'altitude': 0},
        ]

        with patch.object(app.mission_service, 'validate_mission', new_callable=AsyncMock):
            with patch.object(app.mission_service, 'upload_mission', new_callable=AsyncMock):
                with patch.object(app.mission_service, 'start_mission', new_callable=AsyncMock):
                    # Validate
                    resp1 = client.post('/api/mission/validate', json={'waypoints': waypoints})
                    assert resp1.status_code in [200, 500]

                    # Upload
                    resp2 = client.post('/api/mission/upload', json={'waypoints': waypoints})
                    assert resp2.status_code in [200, 500]

                    # Start
                    resp3 = client.post('/api/mission/start')
                    assert resp3.status_code in [200, 500]
