"""
Integration tests for Fleet REST API endpoints.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.backend.app import create_app


@pytest.fixture
def app():
    """Create Flask test app."""
    app, socketio = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    })
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def socketio_client(app):
    """Create SocketIO test client."""
    _, socketio = create_app({'TESTING': True})
    return socketio.test_client(app)


class TestFleetAddDrone:
    """Test POST /api/fleet/add-drone endpoint."""

    def test_add_drone_success(self, client, app):
        """Test successful drone registration."""
        with patch.object(app.fleet_service, 'add_drone', new_callable=AsyncMock) as mock_add:
            mock_add.return_value = {
                "success": True,
                "name": "drone1",
                "host": "127.0.0.1",
                "port": 14540,
            }

            response = client.post('/api/fleet/add-drone', json={
                'name': 'drone1',
                'host': '127.0.0.1',
                'port': 14540,
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["name"] == "drone1"

    def test_add_drone_missing_name(self, client):
        """Test adding drone without name."""
        response = client.post('/api/fleet/add-drone', json={
            'host': '127.0.0.1',
            'port': 14540,
        })

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "name required" in data["error"]

    def test_add_drone_duplicate(self, client, app):
        """Test adding duplicate drone."""
        with patch.object(app.fleet_service, 'add_drone', new_callable=AsyncMock) as mock_add:
            mock_add.return_value = {
                "success": False,
                "error": "Drone drone1 already registered",
            }

            response = client.post('/api/fleet/add-drone', json={
                'name': 'drone1',
                'host': '127.0.0.1',
                'port': 14540,
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False
            assert "already registered" in data["error"]


class TestFleetRemoveDrone:
    """Test DELETE /api/fleet/remove-drone endpoint."""

    def test_remove_drone_success(self, client, app):
        """Test successful drone removal."""
        with patch.object(app.fleet_service, 'remove_drone', new_callable=AsyncMock) as mock_remove:
            mock_remove.return_value = {
                "success": True,
                "message": "Drone drone1 removed",
            }

            response = client.delete('/api/fleet/remove-drone/drone1')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True

    def test_remove_drone_not_found(self, client, app):
        """Test removing non-existent drone."""
        with patch.object(app.fleet_service, 'remove_drone', new_callable=AsyncMock) as mock_remove:
            mock_remove.return_value = {
                "success": False,
                "error": "Drone nonexistent not found",
            }

            response = client.delete('/api/fleet/remove-drone/nonexistent')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False


class TestFleetStatus:
    """Test GET /api/fleet/status endpoint."""

    def test_fleet_status_empty(self, client, app):
        """Test getting status of empty fleet."""
        with patch.object(app.fleet_service, 'get_fleet_status', new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {
                "success": True,
                "fleet_size": 0,
                "drones": {},
            }

            response = client.get('/api/fleet/status')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["fleet_size"] == 0

    def test_fleet_status_multiple_drones(self, client, app):
        """Test getting status with multiple drones."""
        with patch.object(app.fleet_service, 'get_fleet_status', new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {
                "success": True,
                "fleet_size": 2,
                "drones": {
                    "drone1": {
                        "name": "drone1",
                        "connected": True,
                        "state": "guided",
                        "battery_percent": 85.0,
                    },
                    "drone2": {
                        "name": "drone2",
                        "connected": True,
                        "state": "armed",
                        "battery_percent": 90.0,
                    },
                }
            }

            response = client.get('/api/fleet/status')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["fleet_size"] == 2
            assert len(data["drones"]) == 2


class TestFleetConflicts:
    """Test GET /api/fleet/conflicts endpoint."""

    def test_no_conflicts(self, client, app):
        """Test with no airspace conflicts."""
        with patch.object(app.fleet_service, 'check_conflicts', new_callable=AsyncMock) as mock_conflicts:
            mock_conflicts.return_value = {
                "success": True,
                "conflict_count": 0,
                "conflicts": {},
            }

            response = client.get('/api/fleet/conflicts')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["conflict_count"] == 0


class TestFleetCoordinatedTakeoff:
    """Test POST /api/fleet/coordinated-takeoff endpoint."""

    def test_coordinated_takeoff_success(self, client, app):
        """Test successful coordinated takeoff."""
        with patch.object(app.fleet_service, 'coordinated_takeoff', new_callable=AsyncMock) as mock_takeoff:
            mock_takeoff.return_value = {
                "success": True,
                "message": "Coordinated takeoff initiated for 2 drones",
                "drones": ["drone1", "drone2"],
            }

            response = client.post('/api/fleet/coordinated-takeoff', json={
                'drones': ['drone1', 'drone2'],
                'altitude': 50,
                'delay': 1.0,
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True

    def test_coordinated_takeoff_no_drones(self, client):
        """Test coordinated takeoff without drones."""
        response = client.post('/api/fleet/coordinated-takeoff', json={
            'altitude': 50,
        })

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "required" in data["error"]


class TestFleetBroadcast:
    """Test POST /api/fleet/broadcast endpoint."""

    def test_broadcast_arm(self, client, app):
        """Test broadcasting arm command."""
        with patch.object(app.fleet_service, 'broadcast_command', new_callable=AsyncMock) as mock_broadcast:
            mock_broadcast.return_value = {
                "success": True,
                "command": "arm",
                "results": {
                    "drone1": {"success": True, "message": "Armed"},
                    "drone2": {"success": True, "message": "Armed"},
                }
            }

            response = client.post('/api/fleet/broadcast', json={
                'command': 'arm',
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["command"] == "arm"

    def test_broadcast_no_command(self, client):
        """Test broadcast without command."""
        response = client.post('/api/fleet/broadcast', json={})

        assert response.status_code == 400


class TestFleetEmergencyStop:
    """Test POST /api/fleet/emergency-stop endpoint."""

    def test_emergency_stop(self, client, app):
        """Test emergency stop."""
        with patch.object(app.fleet_service, 'emergency_stop', new_callable=AsyncMock) as mock_stop:
            mock_stop.return_value = {
                "success": True,
                "message": "Emergency stop initiated for all drones",
            }

            response = client.post('/api/fleet/emergency-stop')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
