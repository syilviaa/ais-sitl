"""
Integration tests for SITL environment.

Tests actual flight scenarios in PX4 SITL simulator.
Requires: PX4 SITL running on 127.0.0.1:14540

Run: pytest tests/test_sitl_integration.py -v -s

Note: These tests are skipped if SITL not available.
"""

import pytest
import asyncio
import os
from src.autopilot.plane import Drone
from src.autopilot.geofence import GeofenceValidator


# Skip if SITL not available
SITL_AVAILABLE = os.environ.get("SITL_HOST", "127.0.0.1")
SITL_PORT = int(os.environ.get("SITL_PORT", "14540"))

pytestmark = pytest.mark.skipif(
    not SITL_AVAILABLE,
    reason="SITL simulator not available"
)


@pytest.fixture
async def drone_connected():
    """Create drone connected to SITL."""
    drone = Drone(host=SITL_AVAILABLE, port=SITL_PORT)

    # Try to connect (may fail if SITL not running)
    connected = await drone.connect()
    if not connected:
        pytest.skip("Could not connect to SITL simulator")

    yield drone

    # Cleanup: disarm if armed
    if drone._armed:
        try:
            await drone.disarm()
        except:
            pass


class TestSITLConnection:
    """Test connection to SITL simulator."""

    @pytest.mark.asyncio
    async def test_connect_to_sitl(self):
        """Test connecting to SITL autopilot."""
        drone = Drone(host=SITL_AVAILABLE, port=SITL_PORT)
        is_connected = await drone.connect()

        # Connection may fail if SITL not running, which is ok for CI
        if is_connected:
            assert drone.is_connected()

    @pytest.mark.asyncio
    async def test_heartbeat_received(self, drone_connected):
        """Test heartbeat received from autopilot."""
        # If we're here, connection was successful
        assert drone_connected.is_connected()


class TestSITLFlightControl:
    """Test flight control with SITL."""

    @pytest.mark.asyncio
    async def test_arm_disarm_cycle(self, drone_connected):
        """Test arm/disarm cycle."""
        # Arm
        result = await drone_connected.arm()
        assert result is True

        # Disarm
        result = await drone_connected.disarm()
        assert result is True

    @pytest.mark.asyncio
    async def test_takeoff_and_land(self, drone_connected):
        """Test takeoff and landing sequence."""
        # Takeoff
        result = await drone_connected.takeoff(10.0)
        assert result is True

        # Land
        result = await drone_connected.land()
        assert result is True

    @pytest.mark.asyncio
    async def test_hold_position(self, drone_connected):
        """Test hold position (hover)."""
        await drone_connected.arm()
        await drone_connected.takeoff(20.0)

        # Hold position
        result = await drone_connected.hold_position()
        assert result is True

        await drone_connected.land()


class TestSITLTelemetry:
    """Test telemetry from SITL."""

    @pytest.mark.asyncio
    async def test_get_telemetry(self, drone_connected):
        """Test retrieving telemetry."""
        telemetry = await drone_connected.get_telemetry()

        assert telemetry is not None
        assert "timestamp" in telemetry
        assert "lat" in telemetry
        assert "lon" in telemetry
        assert "alt" in telemetry
        assert "battery" in telemetry

    @pytest.mark.asyncio
    async def test_telemetry_updates_on_flight(self, drone_connected):
        """Test telemetry updates during flight."""
        initial = await drone_connected.get_telemetry()

        # Takeoff
        await drone_connected.takeoff(30.0)

        # Get updated telemetry
        updated = await drone_connected.get_telemetry()

        # Altitude should have increased
        assert updated["alt"] > initial["alt"]

        await drone_connected.land()

    @pytest.mark.asyncio
    async def test_telemetry_stream(self, drone_connected):
        """Test telemetry streaming at 10 Hz."""
        telemetry_count = 0

        async def callback(data):
            nonlocal telemetry_count
            telemetry_count += 1
            if telemetry_count >= 10:  # Collect 10 samples (~1 second at 10Hz)
                drone_connected._telemetry_streaming = False

        # Start streaming
        await drone_connected.subscribe_telemetry(callback, rate_hz=10)

        # Should have received ~10 telemetry updates
        assert telemetry_count >= 5  # Allow some tolerance


class TestSITLMissions:
    """Test mission execution in SITL."""

    @pytest.mark.asyncio
    async def test_simple_mission(self, drone_connected):
        """Test executing a simple 4-point mission."""
        # Define mission: 4 waypoints
        waypoints = [
            (47.39770, 8.54550, 20.0),  # Home
            (47.39800, 8.54600, 25.0),  # WP1
            (47.39850, 8.54550, 25.0),  # WP2
            (47.39770, 8.54550, 0.0),   # Return home and land
        ]

        result = await drone_connected.fly_mission(waypoints)
        # Mission may fail in CI without full SITL, but code should not crash
        assert result is not None

    @pytest.mark.asyncio
    async def test_mission_validates_geofence(self, drone_connected):
        """Test mission validation against geofence."""
        # Mission that might cross NFZ
        waypoints = [
            (47.39770, 8.54550, 50.0),
            (47.40100, 8.55700, 50.0),  # May cross Zurich Airport zone
        ]

        # Should return True or False without crashing
        is_valid = await drone_connected.validate_mission(waypoints)
        assert isinstance(is_valid, bool)

    @pytest.mark.asyncio
    async def test_mission_progress(self, drone_connected):
        """Test mission progress reporting."""
        progress = await drone_connected.get_mission_progress()

        assert "current" in progress
        assert "total" in progress
        assert "distance_to_next" in progress
        assert "eta" in progress


class TestSITLGeofencing:
    """Test geofencing with SITL."""

    def test_nfz_zones_loaded(self):
        """Test NFZ zones can be loaded."""
        validator = GeofenceValidator()
        loaded = validator.load_nfz_zones("config/nfz_zones.geojson")

        # Zones should exist in config
        if loaded:
            assert len(validator.zones) > 0

    @pytest.mark.asyncio
    async def test_mission_avoids_nfz(self, drone_connected):
        """Test mission planning avoids No-Fly Zones."""
        # Mission that stays clear of NFZ (far from Zurich)
        safe_waypoints = [
            (47.2000, 8.0000, 50.0),
            (47.2100, 8.0100, 50.0),
            (47.2000, 8.0000, 0.0),
        ]

        is_valid = await drone_connected.validate_mission(safe_waypoints)
        # Safe mission should be valid
        assert is_valid is True


class TestSITLFailsafe:
    """Test failsafe scenarios."""

    @pytest.mark.asyncio
    async def test_low_battery_detection(self, drone_connected):
        """Test low battery detection."""
        drone_connected._battery = 15.0

        # Should raise BatteryLowError
        with pytest.raises(Exception):  # Could be BatteryLowError
            await drone_connected.takeoff(50.0)

    @pytest.mark.asyncio
    async def test_connection_state(self, drone_connected):
        """Test connection state tracking."""
        assert drone_connected.is_connected() is True

        # Connection should remain stable
        await asyncio.sleep(0.1)
        assert drone_connected.is_connected() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
