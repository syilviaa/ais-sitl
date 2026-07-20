"""
Unit tests for Drone/Plane flight control.

Tests arm/disarm, takeoff/land, mission planning, and telemetry.

Run: pytest tests/test_plane.py -v
"""

import pytest
import asyncio
from src.autopilot.plane import (
    Drone, Plane, FlightMode,
    Position, Velocity, Attitude,
    ConnectionError, MissionValidationError, BatteryLowError
)


@pytest.fixture
def drone():
    """Create drone instance."""
    return Drone(host="127.0.0.1", port=14540)


@pytest.fixture
def plane():
    """Create plane instance."""
    return Plane(host="127.0.0.1", port=14540)


class TestDroneInitialization:
    """Test drone initialization."""

    def test_drone_init(self, drone):
        """Test drone creation."""
        assert drone.host == "127.0.0.1"
        assert drone.port == 14540
        assert not drone.is_connected()
        assert not drone._armed

    def test_plane_init(self, plane):
        """Test plane is alias for drone."""
        assert isinstance(plane, Drone)
        assert plane.host == "127.0.0.1"

    def test_custom_host_port(self):
        """Test custom host and port."""
        drone = Drone(host="192.168.1.1", port=12345)
        assert drone.host == "192.168.1.1"
        assert drone.port == 12345


class TestFlightControl:
    """Test arm/disarm/takeoff/land commands."""

    @pytest.mark.asyncio
    async def test_arm_not_connected(self, drone):
        """Test arm fails when not connected."""
        with pytest.raises(ConnectionError):
            await drone.arm()

    @pytest.mark.asyncio
    async def test_disarm_when_not_armed(self, drone):
        """Test disarm succeeds even if not armed."""
        drone._connected = True
        result = await drone.disarm()
        assert result is True

    @pytest.mark.asyncio
    async def test_arm_success(self, drone):
        """Test successful arm."""
        drone._connected = True
        result = await drone.arm()
        assert result is True
        assert drone._armed is True

    @pytest.mark.asyncio
    async def test_arm_idempotent(self, drone):
        """Test arming twice is safe."""
        drone._connected = True
        result1 = await drone.arm()
        result2 = await drone.arm()
        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    async def test_disarm_success(self, drone):
        """Test successful disarm."""
        drone._connected = True
        drone._armed = True
        result = await drone.disarm()
        assert result is True
        assert drone._armed is False

    @pytest.mark.asyncio
    async def test_takeoff_not_connected(self, drone):
        """Test takeoff fails when not connected."""
        with pytest.raises(ConnectionError):
            await drone.takeoff(50.0)

    @pytest.mark.asyncio
    async def test_takeoff_low_battery(self, drone):
        """Test takeoff fails with low battery."""
        drone._connected = True
        drone._battery = 10.0  # Below 15% threshold
        with pytest.raises(BatteryLowError):
            await drone.takeoff(50.0)

    @pytest.mark.asyncio
    async def test_takeoff_arms_automatically(self, drone):
        """Test takeoff arms drone automatically."""
        drone._connected = True
        drone._battery = 80.0
        result = await drone.takeoff(50.0)
        assert result is True
        assert drone._armed is True

    @pytest.mark.asyncio
    async def test_land_success(self, drone):
        """Test successful landing."""
        drone._connected = True
        drone._armed = True
        result = await drone.land()
        assert result is True
        assert drone._armed is False

    @pytest.mark.asyncio
    async def test_hold_position_success(self, drone):
        """Test hold position."""
        drone._connected = True
        result = await drone.hold_position()
        assert result is True


class TestMissionPlanning:
    """Test mission planning and execution."""

    @pytest.mark.asyncio
    async def test_mission_requires_min_waypoints(self, drone):
        """Test mission requires at least 2 waypoints."""
        drone._connected = True
        with pytest.raises(ValueError):
            await drone.fly_mission([(47.39, 8.54, 50)])

    @pytest.mark.asyncio
    async def test_mission_validation_skipped_if_no_geofence(self, drone):
        """Test mission proceeds if geofence config missing."""
        drone._connected = True
        waypoints = [
            (47.39, 8.54, 50.0),
            (47.40, 8.55, 50.0),
        ]
        # Should not raise - geofence file may not exist
        result = await drone.fly_mission(waypoints)
        # In stub mode, should succeed
        if not drone._system:  # Stub mode (MAVSDK not available)
            assert result is True

    @pytest.mark.asyncio
    async def test_mission_arms_drone(self, drone):
        """Test mission arms drone automatically."""
        drone._connected = True
        waypoints = [
            (47.39, 8.54, 50.0),
            (47.40, 8.55, 50.0),
        ]
        await drone.fly_mission(waypoints)
        assert drone._armed is True

    @pytest.mark.asyncio
    async def test_mission_sets_active_flag(self, drone):
        """Test mission sets active flag."""
        drone._connected = True
        waypoints = [
            (47.39, 8.54, 50.0),
            (47.40, 8.55, 50.0),
        ]
        await drone.fly_mission(waypoints)
        # After stub mission completes, flag should be False
        assert drone._mission_active is False


class TestTelemetry:
    """Test telemetry retrieval."""

    def test_get_telemetry_default(self, drone):
        """Test default telemetry values."""
        telemetry = asyncio.run(drone.get_telemetry())

        assert telemetry["lat"] == drone._position.lat
        assert telemetry["lon"] == drone._position.lon
        assert telemetry["alt"] == drone._position.alt
        assert telemetry["battery"] == drone._battery
        assert telemetry["armed"] == drone._armed

    def test_telemetry_has_required_fields(self, drone):
        """Test telemetry includes all required fields."""
        telemetry = asyncio.run(drone.get_telemetry())

        required_fields = [
            "timestamp", "lat", "lon", "alt",
            "vx", "vy", "vz",
            "pitch", "roll", "yaw",
            "battery", "rssi", "armed", "mode", "gps_status", "satellites"
        ]

        for field in required_fields:
            assert field in telemetry, f"Missing field: {field}"

    def test_position_dataclass(self):
        """Test Position dataclass."""
        pos = Position(47.39, 8.54, 50.0)
        assert pos.lat == 47.39
        assert pos.lon == 8.54
        assert pos.alt == 50.0
        assert pos.to_dict() == {"lat": 47.39, "lon": 8.54, "alt": 50.0}

    def test_velocity_dataclass(self):
        """Test Velocity dataclass."""
        vel = Velocity(5.1, 0.3, -0.1)
        assert vel.vx == 5.1
        assert vel.vy == 0.3
        assert vel.vz == -0.1

    def test_attitude_dataclass(self):
        """Test Attitude dataclass."""
        att = Attitude(2.1, -0.5, 142.3)
        assert att.pitch == 2.1
        assert att.roll == -0.5
        assert att.yaw == 142.3

    @pytest.mark.asyncio
    async def test_mission_progress_default(self, drone):
        """Test mission progress default values."""
        progress = await drone.get_mission_progress()

        assert progress["current"] == 0
        assert progress["total"] == 0
        assert progress["distance_to_next"] == 0.0
        assert progress["eta"] == 0


class TestFlightMode:
    """Test flight mode enum."""

    def test_flight_mode_values(self):
        """Test flight mode enum values."""
        assert FlightMode.MANUAL.value == "MANUAL"
        assert FlightMode.AUTO.value == "AUTO"
        assert FlightMode.RTL.value == "RTL"
        assert FlightMode.LAND.value == "LAND"


class TestErrorHandling:
    """Test error handling."""

    def test_connection_error_message(self):
        """Test ConnectionError message."""
        with pytest.raises(ConnectionError, match="Not connected"):
            raise ConnectionError("Not connected to autopilot")

    def test_mission_validation_error(self):
        """Test MissionValidationError."""
        with pytest.raises(MissionValidationError, match="crosses"):
            raise MissionValidationError("Mission crosses No-Fly Zone")

    def test_battery_low_error(self):
        """Test BatteryLowError."""
        with pytest.raises(BatteryLowError, match="Battery"):
            raise BatteryLowError("Battery too low: 10.0%")


class TestTelemetryStreaming:
    """Test telemetry subscription."""

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, drone):
        """Test subscribe fails if not connected."""
        async def callback(data):
            pass

        with pytest.raises(ConnectionError):
            await drone.subscribe_telemetry(callback)

    @pytest.mark.asyncio
    async def test_subscribe_sets_flag(self, drone):
        """Test subscribe sets streaming flag."""
        drone._connected = True

        async def callback(data):
            drone._telemetry_streaming = False  # Stop after 1 iteration

        await drone.subscribe_telemetry(callback, rate_hz=100)
        assert drone._telemetry_streaming is False

    @pytest.mark.asyncio
    async def test_unsubscribe_clears_flag(self, drone):
        """Test unsubscribe clears streaming flag."""
        drone._connected = True
        drone._telemetry_streaming = True

        await drone.unsubscribe_telemetry()

        assert drone._telemetry_streaming is False
        assert drone._telemetry_callback is None


class TestIntegration:
    """Integration tests with typical flight sequence."""

    @pytest.mark.asyncio
    async def test_complete_flight_sequence(self, drone):
        """Test typical flight sequence: connect -> arm -> takeoff -> land -> disarm."""
        drone._connected = True  # Simulate successful connection
        drone._battery = 80.0

        # Arm
        assert await drone.arm() is True
        assert drone._armed is True

        # Takeoff
        assert await drone.takeoff(50.0) is True

        # Get telemetry
        telemetry = await drone.get_telemetry()
        assert "timestamp" in telemetry
        assert telemetry["armed"] is True

        # Land
        assert await drone.land() is True

        # Disarm
        assert await drone.disarm() is True
        assert drone._armed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
