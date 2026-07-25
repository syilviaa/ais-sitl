"""
Tests for Fleet Service - Multi-drone management.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.backend.services.fleet_service import FleetService
from src.backend.services.drone_service import DroneService
from src.backend.services.drone_coordinator import DroneCoordinator, DroneStatus


@pytest.fixture
def fleet_service():
    """Create a fleet service for testing."""
    service = FleetService()
    return service


@pytest.fixture
def mock_drone_service():
    """Create a mock drone service."""
    mock = Mock(spec=DroneService)
    mock.disconnect = AsyncMock()
    return mock


class TestFleetServiceBasics:
    """Test basic fleet operations."""

    @pytest.mark.asyncio
    async def test_add_drone(self, fleet_service, mock_drone_service):
        """Test adding a drone to fleet."""
        result = await fleet_service.add_drone("drone1", "127.0.0.1", 14540)

        assert result["success"] is True
        assert result["name"] == "drone1"
        assert result["host"] == "127.0.0.1"
        assert result["port"] == 14540

    @pytest.mark.asyncio
    async def test_add_duplicate_drone(self, fleet_service):
        """Test adding duplicate drone fails."""
        await fleet_service.add_drone("drone1", "127.0.0.1", 14540)
        result = await fleet_service.add_drone("drone1", "127.0.0.1", 14541)

        assert result["success"] is False
        assert "already registered" in result["error"]

    @pytest.mark.asyncio
    async def test_remove_drone(self, fleet_service, mock_drone_service):
        """Test removing drone from fleet."""
        # Add a drone first
        await fleet_service.add_drone("drone1", "127.0.0.1", 14540)

        # Remove it
        result = await fleet_service.remove_drone("drone1")

        assert result["success"] is True
        assert result["name"] == "drone1"

    @pytest.mark.asyncio
    async def test_remove_nonexistent_drone(self, fleet_service):
        """Test removing non-existent drone fails."""
        result = await fleet_service.remove_drone("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_fleet_size(self, fleet_service):
        """Test getting fleet size."""
        assert fleet_service.get_fleet_size() == 0

        await fleet_service.add_drone("drone1", "127.0.0.1", 14540)
        assert fleet_service.get_fleet_size() == 1

        await fleet_service.add_drone("drone2", "127.0.0.1", 14541)
        assert fleet_service.get_fleet_size() == 2


class TestFleetStatusAndCoordinates:
    """Test fleet status and coordination."""

    @pytest.mark.asyncio
    async def test_get_fleet_status_empty(self, fleet_service):
        """Test getting status of empty fleet."""
        result = await fleet_service.get_fleet_status()

        assert result["success"] is True
        assert result["fleet_size"] == 0
        assert result["drones"] == {}

    @pytest.mark.asyncio
    async def test_check_conflicts_empty(self, fleet_service):
        """Test checking conflicts with empty fleet."""
        result = await fleet_service.check_conflicts()

        assert result["success"] is True
        assert result["conflict_count"] == 0
        assert result["conflicts"] == {}

    @pytest.mark.asyncio
    async def test_coordinated_takeoff(self, fleet_service):
        """Test coordinated takeoff."""
        # Mock the coordinator
        fleet_service.coordinator.coordinated_takeoff = AsyncMock()

        result = await fleet_service.coordinated_takeoff(
            ["drone1", "drone2"],
            altitude=50,
            delay=1.0
        )

        assert result["success"] is True
        fleet_service.coordinator.coordinated_takeoff.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_command(self, fleet_service):
        """Test broadcasting command."""
        # Mock the coordinator
        fleet_service.coordinator.broadcast_command = AsyncMock(
            return_value={"drone1": {"success": True, "message": "Armed"}}
        )

        result = await fleet_service.broadcast_command("arm")

        assert result["success"] is True
        assert result["command"] == "arm"


class TestFleetEmergency:
    """Test emergency operations."""

    @pytest.mark.asyncio
    async def test_emergency_stop(self, fleet_service):
        """Test emergency stop."""
        # Mock the coordinator
        fleet_service.coordinator.emergency_stop_all = AsyncMock()

        result = await fleet_service.emergency_stop()

        assert result["success"] is True
        fleet_service.coordinator.emergency_stop_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown(self, fleet_service):
        """Test fleet shutdown."""
        # Mock the coordinator
        fleet_service.coordinator.shutdown = AsyncMock()

        await fleet_service.shutdown()

        fleet_service.coordinator.shutdown.assert_called_once()


class TestFleetDatabaseIntegration:
    """Test fleet service with database."""

    @pytest.mark.asyncio
    async def test_add_drone_with_database(self, fleet_service):
        """Test adding drone with database persistence."""
        # Mock database session
        mock_session = MagicMock()
        mock_session_factory = Mock(return_value=mock_session)

        fleet_service.set_database(mock_session_factory)

        result = await fleet_service.add_drone("drone1", "127.0.0.1", 14540)

        assert result["success"] is True
        assert mock_session.add.called
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_add_drone_database_error(self, fleet_service):
        """Test handling database errors."""
        # Mock database session that raises error
        mock_session = MagicMock()
        mock_session.add.side_effect = Exception("Database error")
        mock_session_factory = Mock(return_value=mock_session)

        fleet_service.set_database(mock_session_factory)

        result = await fleet_service.add_drone("drone1", "127.0.0.1", 14540)

        assert result["success"] is True  # Drone still added in memory
        assert mock_session.rollback.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
