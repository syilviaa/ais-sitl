"""
Integration tests for Geofence API endpoints.
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


@pytest.fixture
def sample_zone():
    """Sample geofence zone."""
    return {
        "name": "restricted_area",
        "polygon": {
            "type": "Polygon",
            "coordinates": [[[8.5, 47.3], [8.6, 47.3], [8.6, 47.4], [8.5, 47.4], [8.5, 47.3]]]
        },
        "altitude_min": 0.0,
        "altitude_max": 100.0,
    }


class TestGeofenceCreate:
    """Test POST /api/geofence/create endpoint."""

    def test_create_zone_success(self, client, app, sample_zone):
        """Test successful zone creation."""
        with patch.object(app.geofence_service, 'create_zone', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                "success": True,
                "message": "Zone restricted_area created",
                "zone_id": "zone-123",
                "zone": sample_zone,
            }

            response = client.post('/api/geofence/create', json=sample_zone)

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True

    def test_create_zone_missing_name(self, client):
        """Test creating zone without name."""
        response = client.post('/api/geofence/create', json={
            "polygon": {"type": "Polygon", "coordinates": []},
        })

        assert response.status_code == 400


class TestGeofenceGet:
    """Test GET /api/geofence/get endpoint."""

    def test_get_zone_success(self, client, app, sample_zone):
        """Test retrieving zone."""
        with patch.object(app.geofence_service, 'get_zone', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "success": True,
                "zone": sample_zone,
            }

            response = client.get('/api/geofence/get/restricted_area')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True

    def test_get_zone_not_found(self, client, app):
        """Test retrieving non-existent zone."""
        with patch.object(app.geofence_service, 'get_zone', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "success": False,
                "error": "Zone unknown not found",
            }

            response = client.get('/api/geofence/get/unknown')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False


class TestGeofenceList:
    """Test GET /api/geofence/list endpoint."""

    def test_list_zones_empty(self, client, app):
        """Test listing empty zone list."""
        with patch.object(app.geofence_service, 'list_zones', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {
                "success": True,
                "count": 0,
                "zones": [],
            }

            response = client.get('/api/geofence/list')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["count"] == 0

    def test_list_zones_with_data(self, client, app, sample_zone):
        """Test listing zones with data."""
        with patch.object(app.geofence_service, 'list_zones', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {
                "success": True,
                "count": 1,
                "zones": [sample_zone],
            }

            response = client.get('/api/geofence/list?active=true')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["count"] == 1


class TestGeofenceUpdate:
    """Test POST /api/geofence/update endpoint."""

    def test_update_zone_success(self, client, app, sample_zone):
        """Test updating zone."""
        with patch.object(app.geofence_service, 'update_zone', new_callable=AsyncMock) as mock_update:
            updated_zone = sample_zone.copy()
            updated_zone["altitude_max"] = 150.0

            mock_update.return_value = {
                "success": True,
                "message": "Zone restricted_area updated",
                "zone": updated_zone,
            }

            response = client.post('/api/geofence/update/restricted_area', json={
                "altitude_max": 150.0,
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True


class TestGeofenceDelete:
    """Test DELETE /api/geofence/delete endpoint."""

    def test_delete_zone_success(self, client, app):
        """Test deleting zone."""
        with patch.object(app.geofence_service, 'delete_zone', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {
                "success": True,
                "message": "Zone restricted_area deleted",
            }

            response = client.delete('/api/geofence/delete/restricted_area')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True


class TestGeofenceMissionValidation:
    """Test POST /api/geofence/validate-mission endpoint."""

    def test_validate_mission_valid(self, client, app):
        """Test validating valid mission."""
        with patch.object(app.geofence_service, 'validate_mission', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "success": True,
                "valid": True,
                "violation_count": 0,
                "violations": [],
            }

            response = client.post('/api/geofence/validate-mission', json={
                "waypoints": [
                    {"lat": 47.35, "lon": 8.55, "altitude": 50.0},
                    {"lat": 47.36, "lon": 8.56, "altitude": 60.0},
                ]
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["valid"] is True

    def test_validate_mission_with_violations(self, client, app):
        """Test mission with violations."""
        with patch.object(app.geofence_service, 'validate_mission', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "success": True,
                "valid": False,
                "violation_count": 1,
                "violations": [
                    {
                        "waypoint_index": 0,
                        "zone": "restricted_area",
                        "violation_type": "altitude",
                        "message": "Below minimum altitude",
                    }
                ],
            }

            response = client.post('/api/geofence/validate-mission', json={
                "waypoints": [
                    {"lat": 47.35, "lon": 8.55, "altitude": 30.0},
                ]
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["valid"] is False
            assert data["violation_count"] == 1

    def test_validate_mission_no_waypoints(self, client):
        """Test validation without waypoints."""
        response = client.post('/api/geofence/validate-mission', json={})

        assert response.status_code == 400


class TestGeofencePositionCheck:
    """Test POST /api/geofence/check-position endpoint."""

    def test_check_position_safe(self, client, app):
        """Test checking safe position."""
        with patch.object(app.geofence_service, 'check_position', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {
                "success": True,
                "safe": True,
                "violation_count": 0,
                "violations": [],
            }

            response = client.post('/api/geofence/check-position', json={
                "drone_id": "drone1",
                "position": {
                    "lat": 47.35,
                    "lon": 8.55,
                    "altitude": 50.0,
                }
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["safe"] is True

    def test_check_position_violation(self, client, app):
        """Test position with violation."""
        with patch.object(app.geofence_service, 'check_position', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {
                "success": True,
                "safe": False,
                "violation_count": 1,
                "violations": [
                    {
                        "type": "altitude",
                        "zone": "restricted_area",
                        "message": "Above maximum altitude",
                        "action": "hold",
                    }
                ],
            }

            response = client.post('/api/geofence/check-position', json={
                "drone_id": "drone1",
                "position": {
                    "lat": 47.35,
                    "lon": 8.55,
                    "altitude": 150.0,
                }
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["safe"] is False


class TestGeofenceViolations:
    """Test GET /api/geofence/violations endpoint."""

    def test_get_violations_empty(self, client, app):
        """Test retrieving violation history."""
        with patch.object(app.geofence_service, 'get_violations', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "success": True,
                "zone": "restricted_area",
                "violation_count": 0,
                "violations": [],
            }

            response = client.get('/api/geofence/violations/restricted_area')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["violation_count"] == 0

    def test_get_violations_with_data(self, client, app):
        """Test retrieving violations with history."""
        with patch.object(app.geofence_service, 'get_violations', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "success": True,
                "zone": "restricted_area",
                "violation_count": 2,
                "violations": [
                    {
                        "violation_type": "altitude",
                        "drone_id": "drone1",
                        "timestamp": 1721938284.0,
                        "message": "Above maximum altitude",
                    },
                    {
                        "violation_type": "boundary",
                        "drone_id": "drone2",
                        "timestamp": 1721938285.0,
                        "message": "Outside geofence boundary",
                    },
                ]
            }

            response = client.get('/api/geofence/violations/restricted_area?limit=50')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["violation_count"] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
