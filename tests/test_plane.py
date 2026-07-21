"""Unit tests for the local PX4 SITL Drone controller."""

import asyncio
from types import SimpleNamespace

import pytest

from src.autopilot.plane import (
    ConnectionError,
    Drone,
    DroneState,
    DroneTimeoutError,
    InvalidStateError,
)


async def value_stream(value):
    """Yield a value once, then wait without consuming CPU."""
    yield value
    await asyncio.Event().wait()


class FakeAction:
    def __init__(self, system):
        self.system = system
        self.calls = []

    async def arm(self):
        self.calls.append("arm")
        self.system.armed_value = True

    async def disarm(self):
        self.calls.append("disarm")
        self.system.armed_value = False

    async def set_takeoff_altitude(self, altitude):
        self.calls.append(("set_takeoff_altitude", altitude))

    async def takeoff(self):
        self.calls.append("takeoff")
        if self.system.reaches_altitude:
            self.system.position_value.relative_altitude_m = 5.0

    async def land(self):
        self.calls.append("land")
        self.system.armed_value = False

    async def hold(self):
        self.calls.append("hold")

    async def return_to_launch(self):
        self.calls.append("return_to_launch")


class FakeTelemetry:
    def __init__(self, system):
        self.system = system

    def health(self):
        return value_stream(
            SimpleNamespace(
                is_global_position_ok=True,
                is_home_position_ok=True,
            )
        )

    def home(self):
        return value_stream(SimpleNamespace(latitude_deg=47.4))

    def armed(self):
        return value_stream(self.system.armed_value)

    def position(self):
        return value_stream(self.system.position_value)

    def velocity_ned(self):
        return value_stream(
            SimpleNamespace(north_m_s=3.0, east_m_s=4.0, down_m_s=-0.5)
        )

    def attitude_euler(self):
        return value_stream(
            SimpleNamespace(roll_deg=1.0, pitch_deg=2.0, yaw_deg=3.0)
        )

    def battery(self):
        return value_stream(SimpleNamespace(remaining_percent=80.0))

    def flight_mode(self):
        return value_stream("HOLD")

    def gps_info(self):
        return value_stream(
            SimpleNamespace(fix_type="FIX_3D", num_satellites=12)
        )


class FakeMission:
    async def upload_mission(self, plan):
        self.plan = plan

    async def start_mission(self):
        self.started = True

    def mission_progress(self):
        return value_stream(SimpleNamespace(current=1, total=2))


class FakeSystem:
    def __init__(self, reaches_altitude=True):
        self.armed_value = False
        self.reaches_altitude = reaches_altitude
        self.position_value = SimpleNamespace(
            latitude_deg=47.4,
            longitude_deg=8.5,
            absolute_altitude_m=500.0,
            relative_altitude_m=0.0,
        )
        self.action = FakeAction(self)
        self.telemetry = FakeTelemetry(self)
        self.mission = FakeMission()
        self.core = SimpleNamespace(
            connection_state=lambda: value_stream(
                SimpleNamespace(is_connected=True)
            )
        )

    async def connect(self, system_address=None):
        self.address = system_address


async def ready_drone(system=None):
    drone = Drone(system=system or FakeSystem(), command_timeout_s=0.05)
    await drone.connect()
    await drone.wait_until_ready()
    return drone


@pytest.mark.asyncio
async def test_arm_is_rejected_before_connection_and_ready():
    drone = Drone(system=FakeSystem())
    with pytest.raises(ConnectionError):
        await drone.arm()
    await drone.connect()
    with pytest.raises(InvalidStateError):
        await drone.arm()
    await drone.disconnect()


@pytest.mark.asyncio
async def test_takeoff_is_rejected_before_arm():
    drone = await ready_drone()
    with pytest.raises(InvalidStateError):
        await drone.takeoff(5.0)
    await drone.disconnect()


@pytest.mark.asyncio
async def test_invalid_takeoff_height_is_rejected():
    drone = await ready_drone()
    with pytest.raises(ValueError):
        await drone.takeoff(0.1)
    await drone.disconnect()


@pytest.mark.asyncio
async def test_valid_state_transitions():
    drone = await ready_drone()
    await drone.arm()
    assert drone.state is DroneState.ARMED
    await drone.takeoff(5.0)
    assert drone.state is DroneState.AIRBORNE
    await drone.hold_position()
    assert drone.state is DroneState.HOLDING
    await drone.land()
    assert drone.state is DroneState.READY
    await drone.disconnect()


@pytest.mark.asyncio
async def test_takeoff_times_out_if_altitude_is_not_reached():
    drone = await ready_drone(FakeSystem(reaches_altitude=False))
    await drone.arm()
    with pytest.raises(DroneTimeoutError):
        await drone.takeoff(5.0, timeout_s=0.01)
    assert drone.state is DroneState.ERROR
    await drone.disconnect()


@pytest.mark.asyncio
async def test_land_and_rtl_send_mavsdk_commands():
    drone = await ready_drone()
    await drone.arm()
    await drone.takeoff(5.0)
    await drone.land()
    assert "land" in drone._system.action.calls
    await drone.arm()
    await drone.takeoff(5.0)
    await drone.return_to_launch("test")
    assert "return_to_launch" in drone._system.action.calls
    await drone.disconnect()


@pytest.mark.asyncio
async def test_telemetry_format_uses_received_values():
    drone = await ready_drone()
    await asyncio.sleep(0)
    telemetry = await drone.get_telemetry()
    assert telemetry["lat"] == 47.4
    assert telemetry["absolute_altitude_m"] == 500.0
    assert telemetry["alt"] == 0.0
    assert telemetry["vx"] == 3.0
    assert telemetry["pitch"] == 2.0
    assert telemetry["battery"] == 80.0
    assert telemetry["armed"] is False
    assert telemetry["mode"] == "HOLD"
    assert telemetry["satellites"] == 12
    await drone.disconnect()


@pytest.mark.asyncio
async def test_telemetry_callback_is_limited_to_ten_hz():
    drone = await ready_drone()
    timestamps = []

    async def callback(_telemetry):
        timestamps.append(asyncio.get_running_loop().time())

    await drone.subscribe_telemetry(callback)
    await asyncio.sleep(0.31)
    await drone.unsubscribe_telemetry()
    assert len(timestamps) <= 4
    assert all(
        later - earlier >= 0.09
        for earlier, later in zip(timestamps, timestamps[1:])
    )
    await drone.disconnect()
