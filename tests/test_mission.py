"""
Mission Management Tests

Tests mission upload, execution, and progress tracking.
"""

import pytest
import asyncio
from src.mission import MissionService, MissionPlanner
from src.models import Waypoint, MissionItem, MissionProgress


class TestMissionService:
    """Test mission service."""

    def test_mission_service_init(self):
        """Test initialization."""
        service = MissionService(system=None)

        assert not service._mission_uploaded
        assert not service._mission_running
        assert len(service._current_mission_items) == 0

    def test_mission_validation_valid(self):
        """Test valid mission validation."""
        waypoints = [
            Waypoint(47.39, 8.54, 50),
            Waypoint(47.40, 8.55, 50),
        ]

        is_valid, msg = MissionService.validate_mission(waypoints)
        assert is_valid is True

    def test_mission_validation_empty(self):
        """Test validation of empty mission."""
        is_valid, msg = MissionService.validate_mission([])
        assert is_valid is False
        assert "at least 1 waypoint" in msg

    def test_mission_validation_too_many(self):
        """Test validation with too many waypoints."""
        waypoints = [Waypoint(47.39, 8.54, 50) for _ in range(501)]
        is_valid, msg = MissionService.validate_mission(waypoints)
        assert is_valid is False
        assert "too many" in msg

    def test_mission_validation_invalid_lat(self):
        """Test validation with invalid latitude."""
        waypoints = [Waypoint(91.0, 8.54, 50)]
        is_valid, msg = MissionService.validate_mission(waypoints)
        assert is_valid is False

    def test_mission_validation_invalid_lon(self):
        """Test validation with invalid longitude."""
        waypoints = [Waypoint(47.39, 181.0, 50)]
        is_valid, msg = MissionService.validate_mission(waypoints)
        assert is_valid is False

    def test_mission_validation_negative_alt(self):
        """Test validation with negative altitude."""
        waypoints = [Waypoint(47.39, 8.54, -10)]
        is_valid, msg = MissionService.validate_mission(waypoints)
        assert is_valid is False

    def test_mission_validation_high_alt(self):
        """Test validation with altitude too high."""
        waypoints = [Waypoint(47.39, 8.54, 11000)]
        is_valid, msg = MissionService.validate_mission(waypoints)
        assert is_valid is False

    def test_mission_validation_invalid_speed(self):
        """Test validation with invalid speed."""
        wp = Waypoint(47.39, 8.54, 50)
        wp.speed_m_s = 50  # Too fast
        is_valid, msg = MissionService.validate_mission([wp])
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_upload_mission(self):
        """Test mission upload."""
        service = MissionService(system=None)

        waypoints = [
            Waypoint(47.39, 8.54, 50),
            Waypoint(47.40, 8.55, 50),
        ]

        result = await service.upload_mission(waypoints)
        assert result is True
        assert service._mission_uploaded is True
        assert len(service._current_mission_items) == 2

    @pytest.mark.asyncio
    async def test_upload_empty_mission(self):
        """Test upload of empty mission fails."""
        service = MissionService(system=None)

        with pytest.raises(ValueError):
            await service.upload_mission([])

    @pytest.mark.asyncio
    async def test_start_mission_no_upload(self):
        """Test start mission without upload fails."""
        service = MissionService(system=None)

        with pytest.raises(RuntimeError):
            await service.start_mission()

    @pytest.mark.asyncio
    async def test_start_mission(self):
        """Test mission start."""
        service = MissionService(system=None)

        waypoints = [
            Waypoint(47.39, 8.54, 50),
            Waypoint(47.40, 8.55, 50),
        ]

        await service.upload_mission(waypoints)
        result = await service.start_mission()

        assert result is True
        assert service._mission_running is True

    @pytest.mark.asyncio
    async def test_pause_mission(self):
        """Test mission pause."""
        service = MissionService(system=None)

        waypoints = [Waypoint(47.39, 8.54, 50)]

        await service.upload_mission(waypoints)
        await service.start_mission()

        result = await service.pause_mission()
        assert result is True
        assert service._mission_running is False

    @pytest.mark.asyncio
    async def test_resume_mission(self):
        """Test mission resume."""
        service = MissionService(system=None)

        waypoints = [Waypoint(47.39, 8.54, 50)]

        await service.upload_mission(waypoints)
        await service.start_mission()
        await service.pause_mission()

        result = await service.resume_mission()
        assert result is True
        assert service._mission_running is True

    @pytest.mark.asyncio
    async def test_abort_mission(self):
        """Test mission abort."""
        service = MissionService(system=None)

        waypoints = [Waypoint(47.39, 8.54, 50)]

        await service.upload_mission(waypoints)
        await service.start_mission()

        result = await service.abort_mission()
        assert result is True
        assert service._mission_running is False

    @pytest.mark.asyncio
    async def test_get_progress(self):
        """Test mission progress tracking."""
        service = MissionService(system=None)

        waypoints = [
            Waypoint(47.39, 8.54, 50),
            Waypoint(47.40, 8.55, 50),
        ]

        await service.upload_mission(waypoints)

        progress = await service.get_progress()

        assert progress is not None
        assert progress.total_waypoints == 2
        assert progress.current_waypoint == 0
        assert not progress.is_mission_finished

    @pytest.mark.asyncio
    async def test_is_mission_finished(self):
        """Test mission finished check."""
        service = MissionService(system=None)

        waypoints = [Waypoint(47.39, 8.54, 50)]

        await service.upload_mission(waypoints)

        finished = await service.is_mission_finished()
        assert finished is False

    def test_get_current_mission(self):
        """Test getting current mission items."""
        service = MissionService(system=None)

        assert len(service.get_current_mission()) == 0

    def test_mission_stats(self):
        """Test mission statistics."""
        service = MissionService(system=None)

        waypoints = [
            Waypoint(47.39, 8.54, 50),
            Waypoint(47.40, 8.55, 50),
        ]

        asyncio.run(service.upload_mission(waypoints))

        stats = service.get_mission_stats()

        assert stats["total_waypoints"] == 2
        assert stats["uploaded"] is True
        assert stats["running"] is False
        assert stats["estimated_distance_m"] > 0

    @pytest.mark.asyncio
    async def test_mission_callbacks(self):
        """Test mission progress callbacks."""
        service = MissionService(system=None)

        received = []

        def callback(progress):
            received.append(progress)

        service.on_progress(callback)

        waypoints = [Waypoint(47.39, 8.54, 50)]

        await service.upload_mission(waypoints)
        await service.get_progress()

        assert len(received) >= 1


class TestMissionPlanner:
    """Test mission planning utilities."""

    def test_create_simple_mission(self):
        """Test creating simple rectangular mission."""
        waypoints = MissionPlanner.create_simple_mission(
            home_lat=47.39,
            home_lon=8.54,
            home_alt=0,
            altitude=50,
            distance_m=1000,
            num_waypoints=4,
        )

        # Should have 4 corners + home return
        assert len(waypoints) == 5

        # All should be Waypoint objects
        for wp in waypoints:
            assert isinstance(wp, Waypoint)

        # All should be at specified altitude (except last = home)
        for wp in waypoints[:-1]:
            assert wp.altitude_m == 50

    def test_create_loiter_mission(self):
        """Test creating loiter mission."""
        waypoints = MissionPlanner.create_loiter_mission(
            lat=47.39,
            lon=8.54,
            altitude=50,
            loiter_time_sec=120,
        )

        assert len(waypoints) == 1
        assert waypoints[0].lat == 47.39
        assert waypoints[0].lon == 8.54
        assert waypoints[0].altitude_m == 50
        assert waypoints[0].wait_time_s == 120


class TestMissionIntegration:
    """Integration tests for mission system."""

    @pytest.mark.asyncio
    async def test_complete_mission_cycle(self):
        """Test complete mission cycle: upload → start → progress → abort."""
        service = MissionService(system=None)

        waypoints = [
            Waypoint(47.39, 8.54, 50),
            Waypoint(47.40, 8.55, 50),
            Waypoint(47.39, 8.54, 0),  # Return home
        ]

        # Upload
        assert await service.upload_mission(waypoints) is True

        # Start
        assert await service.start_mission() is True

        # Check progress
        progress = await service.get_progress()
        assert progress.total_waypoints == 3

        # Pause
        assert await service.pause_mission() is True

        # Resume
        assert await service.resume_mission() is True

        # Abort (RTL)
        assert await service.abort_mission() is True

        assert service._mission_running is False

    @pytest.mark.asyncio
    async def test_mission_stats_after_upload(self):
        """Test mission stats after uploading."""
        service = MissionService(system=None)

        waypoints = MissionPlanner.create_simple_mission(
            home_lat=47.39,
            home_lon=8.54,
            home_alt=0,
            altitude=50,
            distance_m=500,
        )

        await service.upload_mission(waypoints)

        stats = service.get_mission_stats()

        assert stats["total_waypoints"] == 5
        assert stats["uploaded"] is True
        assert stats["estimated_distance_m"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
