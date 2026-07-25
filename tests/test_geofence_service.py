"""
Tests for Geofence Service - Airspace boundary enforcement.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.backend.services.geofence_service import GeofenceService
from src.backend.services.geofence_monitor import GeofenceMonitor, GeofenceViolation


@pytest.fixture
def geofence_service():
    """Create a geofence service."""
    service = GeofenceService()
    return service


@pytest.fixture
def sample_zone():
    """Create a sample geofence zone."""
    return {
        "name": "restricted_area",
        "polygon": {
            "type": "Polygon",
            "coordinates": [[[8.5, 47.3], [8.6, 47.3], [8.6, 47.4], [8.5, 47.4], [8.5, 47.3]]]
        },
        "altitude_min": 0.0,
        "altitude_max": 100.0,
    }


class TestGeofenceMonitor:
    """Test geofence monitor functionality."""

    @pytest.mark.asyncio
    async def test_altitude_below_minimum(self):
        """Test altitude violation below minimum."""
        monitor = GeofenceMonitor()

        zone = {
            "name": "zone1",
            "altitude_min": 50.0,
            "altitude_max": 100.0,
        }

        position = {
            "lat": 47.3977,
            "lon": 8.5455,
            "altitude": 30.0,  # Below minimum
        }

        violation = await monitor.check_position("drone1", position, zone)

        assert violation is not None
        assert violation.violation_type == "altitude"
        assert "Below minimum altitude" in violation.message

    @pytest.mark.asyncio
    async def test_altitude_above_maximum(self):
        """Test altitude violation above maximum."""
        monitor = GeofenceMonitor()

        zone = {
            "name": "zone1",
            "altitude_min": 0.0,
            "altitude_max": 100.0,
        }

        position = {
            "lat": 47.3977,
            "lon": 8.5455,
            "altitude": 150.0,  # Above maximum
        }

        violation = await monitor.check_position("drone1", position, zone)

        assert violation is not None
        assert violation.violation_type == "altitude"
        assert "Above maximum altitude" in violation.message

    @pytest.mark.asyncio
    async def test_altitude_within_range(self):
        """Test altitude within valid range."""
        monitor = GeofenceMonitor()

        zone = {
            "name": "zone1",
            "altitude_min": 0.0,
            "altitude_max": 100.0,
        }

        position = {
            "lat": 47.3977,
            "lon": 8.5455,
            "altitude": 50.0,  # Within range
        }

        violation = await monitor.check_position("drone1", position, zone)

        assert violation is None

    def test_point_in_polygon_inside(self):
        """Test point inside polygon."""
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        point = (0.5, 0.5)

        result = GeofenceMonitor._point_in_polygon(point, polygon)

        assert result is True

    def test_point_in_polygon_outside(self):
        """Test point outside polygon."""
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        point = (2, 2)

        result = GeofenceMonitor._point_in_polygon(point, polygon)

        assert result is False


class TestGeofenceServiceCRUD:
    """Test geofence service CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_zone(self, geofence_service, sample_zone):
        """Test creating a geofence zone."""
        result = await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
            sample_zone["altitude_min"],
            sample_zone["altitude_max"],
        )

        assert result["success"] is True
        assert result["zone"]["name"] == "restricted_area"

    @pytest.mark.asyncio
    async def test_create_duplicate_zone(self, geofence_service, sample_zone):
        """Test creating duplicate zone fails."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
            sample_zone["altitude_min"],
            sample_zone["altitude_max"],
        )

        result = await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
        )

        assert result["success"] is False
        assert "already exists" in result["error"]

    @pytest.mark.asyncio
    async def test_get_zone(self, geofence_service, sample_zone):
        """Test retrieving a zone."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
        )

        result = await geofence_service.get_zone(sample_zone["name"])

        assert result["success"] is True
        assert result["zone"]["name"] == "restricted_area"

    @pytest.mark.asyncio
    async def test_list_zones(self, geofence_service, sample_zone):
        """Test listing zones."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
        )

        result = await geofence_service.list_zones()

        assert result["success"] is True
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_update_zone(self, geofence_service, sample_zone):
        """Test updating a zone."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
            altitude_min=0.0,
            altitude_max=100.0,
        )

        result = await geofence_service.update_zone(
            sample_zone["name"],
            altitude_max=150.0,
        )

        assert result["success"] is True
        assert result["zone"]["altitude_max"] == 150.0

    @pytest.mark.asyncio
    async def test_delete_zone(self, geofence_service, sample_zone):
        """Test deleting a zone."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
        )

        result = await geofence_service.delete_zone(sample_zone["name"])

        assert result["success"] is True

        result = await geofence_service.get_zone(sample_zone["name"])
        assert result["success"] is False


class TestGeofenceMissionValidation:
    """Test mission validation against geofence."""

    @pytest.mark.asyncio
    async def test_validate_mission_valid(self, geofence_service, sample_zone):
        """Test validating valid mission."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
            altitude_min=0.0,
            altitude_max=100.0,
        )

        waypoints = [
            {"lat": 47.35, "lon": 8.55, "altitude": 50.0},
            {"lat": 47.36, "lon": 8.56, "altitude": 60.0},
        ]

        result = await geofence_service.validate_mission(waypoints)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_validate_mission_altitude_violation(self, geofence_service, sample_zone):
        """Test mission with altitude violation."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
            altitude_min=50.0,
            altitude_max=100.0,
        )

        waypoints = [
            {"lat": 47.35, "lon": 8.55, "altitude": 30.0},  # Below minimum
            {"lat": 47.36, "lon": 8.56, "altitude": 60.0},
        ]

        result = await geofence_service.validate_mission(waypoints)

        assert result["success"] is True
        assert result["valid"] is False or result["violation_count"] > 0

    @pytest.mark.asyncio
    async def test_validate_mission_no_zones(self, geofence_service):
        """Test validating mission with no zones."""
        waypoints = [
            {"lat": 47.35, "lon": 8.55, "altitude": 50.0},
        ]

        result = await geofence_service.validate_mission(waypoints)

        assert result["success"] is True
        assert result["valid"] is True


class TestGeofencePositionCheck:
    """Test real-time position checking."""

    @pytest.mark.asyncio
    async def test_check_position_safe(self, geofence_service, sample_zone):
        """Test checking safe position."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
            altitude_min=0.0,
            altitude_max=100.0,
        )

        position = {
            "lat": 47.35,
            "lon": 8.55,
            "altitude": 50.0,
        }

        result = await geofence_service.check_position("drone1", position)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_check_position_no_zones(self, geofence_service):
        """Test position check with no zones."""
        position = {
            "lat": 47.35,
            "lon": 8.55,
            "altitude": 50.0,
        }

        result = await geofence_service.check_position("drone1", position)

        assert result["success"] is True
        assert result["safe"] is True


class TestGeofenceViolationTracking:
    """Test violation history tracking."""

    @pytest.mark.asyncio
    async def test_get_violations(self, geofence_service, sample_zone):
        """Test retrieving violation history."""
        await geofence_service.create_zone(
            sample_zone["name"],
            sample_zone["polygon"],
        )

        result = await geofence_service.get_violations(sample_zone["name"])

        assert result["success"] is True
        assert result["violation_count"] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
