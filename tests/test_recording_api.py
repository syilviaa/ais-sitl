"""
Integration tests for Recording API endpoints.
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


class TestRecordingStart:
    """Test POST /api/recording/start endpoint."""

    def test_start_recording_success(self, client, app):
        """Test starting a recording."""
        with patch.object(app.recording_service, 'start_recording', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = {
                "success": True,
                "message": "Recording started for mission mission-001",
                "mission_id": "mission-001",
            }

            response = client.post('/api/recording/start/mission-001')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True


class TestRecordingStop:
    """Test POST /api/recording/stop endpoint."""

    def test_stop_recording_success(self, client, app):
        """Test stopping a recording."""
        with patch.object(app.recording_service, 'stop_recording', new_callable=AsyncMock) as mock_stop:
            mock_stop.return_value = {
                "success": True,
                "message": "Recording stopped for mission mission-001",
                "statistics": {
                    "frame_count": 100,
                    "duration_seconds": 30.5,
                    "distance_meters": 500.0,
                },
            }

            response = client.post('/api/recording/stop/mission-001')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "statistics" in data

    def test_stop_recording_not_found(self, client, app):
        """Test stopping non-existent recording."""
        with patch.object(app.recording_service, 'stop_recording', new_callable=AsyncMock) as mock_stop:
            mock_stop.return_value = {
                "success": False,
                "error": "No active recording for mission-001",
            }

            response = client.post('/api/recording/stop/mission-001')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False


class TestRecordingGet:
    """Test GET /api/recording/get endpoint."""

    def test_get_recording_success(self, client, app):
        """Test retrieving recording details."""
        with patch.object(app.recording_service, 'get_recording', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "success": True,
                "recording_id": "rec-123",
                "mission_id": "mission-001",
                "frame_count": 100,
                "statistics": {
                    "duration_seconds": 30.5,
                    "distance_meters": 500.0,
                },
            }

            response = client.get('/api/recording/get/mission-001')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["frame_count"] == 100

    def test_get_recording_not_found(self, client, app):
        """Test retrieving non-existent recording."""
        with patch.object(app.recording_service, 'get_recording', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "success": False,
                "error": "No recording found for mission-001",
            }

            response = client.get('/api/recording/get/mission-001')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False


class TestRecordingList:
    """Test GET /api/recording/list endpoint."""

    def test_list_recordings_empty(self, client, app):
        """Test listing recordings with empty list."""
        with patch.object(app.recording_service, 'list_recordings', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {
                "success": True,
                "count": 0,
                "recordings": [],
            }

            response = client.get('/api/recording/list')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["count"] == 0

    def test_list_recordings_with_data(self, client, app):
        """Test listing recordings with data."""
        with patch.object(app.recording_service, 'list_recordings', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {
                "success": True,
                "count": 2,
                "recordings": [
                    {
                        "recording_id": "rec-001",
                        "mission_id": "mission-001",
                        "duration_seconds": 30.5,
                        "distance_meters": 500.0,
                    },
                    {
                        "recording_id": "rec-002",
                        "mission_id": "mission-002",
                        "duration_seconds": 45.2,
                        "distance_meters": 750.0,
                    },
                ]
            }

            response = client.get('/api/recording/list?limit=50')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["count"] == 2
            assert len(data["recordings"]) == 2


class TestRecordingPlayback:
    """Test GET /api/recording/playback endpoint."""

    def test_playback_at_1x_speed(self, client, app):
        """Test getting playback timeline at 1x speed."""
        with patch.object(app.recording_service, 'get_playback_timeline', new_callable=AsyncMock) as mock_playback:
            mock_playback.return_value = {
                "success": True,
                "mission_id": "mission-001",
                "playback_speed": 1.0,
                "frame_count": 100,
                "duration_seconds": 30.5,
                "timeline": [
                    {
                        "t": 1721938284.0,
                        "lat": 47.3977,
                        "lon": 8.5455,
                        "alt": 50.0,
                        "playback_time": 0.0,
                    },
                ]
            }

            response = client.get('/api/recording/playback/mission-001?speed=1.0')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["playback_speed"] == 1.0
            assert data["frame_count"] == 100

    def test_playback_at_2x_speed(self, client, app):
        """Test getting playback timeline at 2x speed."""
        with patch.object(app.recording_service, 'get_playback_timeline', new_callable=AsyncMock) as mock_playback:
            mock_playback.return_value = {
                "success": True,
                "mission_id": "mission-001",
                "playback_speed": 2.0,
                "frame_count": 100,
                "duration_seconds": 15.25,
            }

            response = client.get('/api/recording/playback/mission-001?speed=2.0')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["playback_speed"] == 2.0
            assert data["duration_seconds"] == 15.25


class TestRecordingDelete:
    """Test DELETE /api/recording/delete endpoint."""

    def test_delete_recording_success(self, client, app):
        """Test deleting a recording."""
        with patch.object(app.recording_service, 'delete_recording', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {
                "success": True,
                "message": "Recording deleted for mission mission-001",
            }

            response = client.delete('/api/recording/delete/mission-001')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True

    def test_delete_recording_not_found(self, client, app):
        """Test deleting non-existent recording."""
        with patch.object(app.recording_service, 'delete_recording', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {
                "success": False,
                "error": "No recording found for mission-001",
            }

            response = client.delete('/api/recording/delete/mission-001')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
