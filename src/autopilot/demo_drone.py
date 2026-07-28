"""Demo drone for dashboard E2E without real PX4 SITL."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any, Callable, Dict, Optional

from src.autopilot.plane import DroneState

# Astana Training Field home
HOME_LAT = 51.1694
HOME_LON = 71.4491


class DemoDrone:
    """Minimal Drone stand-in: Astana telemetry + flight state simulation."""

    def __init__(self) -> None:
        self._system = None
        self._connected = False
        self.state = DroneState.DISCONNECTED
        self._lat = HOME_LAT
        self._lon = HOME_LON
        self._alt_m = 0.0
        self._target_alt_m = 0.0
        self._armed = False
        self._mode = "manual"
        self._battery = 100.0
        self._yaw = 0.0
        self._telemetry_callback: Optional[Callable] = None
        self._callback_task: Optional[asyncio.Task] = None
        self._sim_task: Optional[asyncio.Task] = None
        self._mission_progress = {"current": 0, "total": 0}

    async def connect(self, timeout_s: float = 15.0) -> bool:
        self._connected = True
        self.state = DroneState.READY
        self._start_sim_loop()
        return True

    async def disconnect(self) -> None:
        self._connected = False
        self.state = DroneState.DISCONNECTED
        if self._sim_task:
            self._sim_task.cancel()
            self._sim_task = None

    def is_connected(self) -> bool:
        return self._connected

    async def wait_until_ready(self, timeout_s: float = 30.0) -> bool:
        await asyncio.sleep(0.2)
        self.state = DroneState.READY
        return True

    async def arm(self) -> None:
        self._armed = True
        self.state = DroneState.ARMED

    async def disarm(self) -> None:
        self._armed = False
        if self._alt_m < 0.5:
            self.state = DroneState.READY
        self._mode = "manual"

    async def takeoff(self, altitude_m: float) -> None:
        self._armed = True
        self._target_alt_m = max(0.5, min(120.0, altitude_m))
        self._mode = "takeoff"
        self.state = DroneState.AIRBORNE

    async def land(self) -> None:
        self._target_alt_m = 0.0
        self._mode = "land"
        self.state = DroneState.LANDING

    async def hold_position(self) -> None:
        self._mode = "hold"
        self.state = DroneState.HOLDING

    async def return_to_launch(self, reason: str = "api_request") -> None:
        self._target_alt_m = 0.0
        self._mode = "rtl"
        self.state = DroneState.RTL
        self._lat = HOME_LAT
        self._lon = HOME_LON

    async def get_telemetry(self) -> Dict[str, Any]:
        return {
            "timestamp": time.time(),
            "lat": self._lat,
            "lon": self._lon,
            "absolute_altitude_m": self._alt_m,
            "relative_altitude_m": self._alt_m,
            "alt": self._alt_m,
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": self._yaw,
            "battery": self._battery,
            "battery_percent": self._battery,
            "gps_fix": "3d",
            "satellites": 12,
            "armed": self._armed,
            "flight_mode": self._mode,
            "mode": self._mode,
        }

    async def subscribe_telemetry(
        self, callback: Callable[[Dict[str, Any]], Any], rate_hz: float = 10.0
    ) -> None:
        self._telemetry_callback = callback
        if self._callback_task is None or self._callback_task.done():
            self._callback_task = asyncio.create_task(
                self._publish_telemetry(rate_hz)
            )

    async def unsubscribe_telemetry(self) -> None:
        self._telemetry_callback = None
        if self._callback_task:
            self._callback_task.cancel()
            self._callback_task = None

    async def get_mission_progress(self) -> Dict[str, int]:
        return dict(self._mission_progress)

    def _start_sim_loop(self) -> None:
        if self._sim_task and not self._sim_task.done():
            return
        self._sim_task = asyncio.create_task(self._sim_loop())

    async def _sim_loop(self) -> None:
        try:
            t0 = time.monotonic()
            while self._connected:
                # Gentle orbit for map movement
                t = time.monotonic() - t0
                self._lat = HOME_LAT + 0.00008 * math.sin(t * 0.15)
                self._lon = HOME_LON + 0.00008 * math.cos(t * 0.15)
                self._yaw = (self._yaw + 2.0) % 360.0

                step = 0.8
                if self._alt_m < self._target_alt_m - 0.1:
                    self._alt_m = min(self._target_alt_m, self._alt_m + step * 0.1)
                elif self._alt_m > self._target_alt_m + 0.1:
                    self._alt_m = max(self._target_alt_m, self._alt_m - step * 0.1)
                else:
                    self._alt_m = self._target_alt_m

                if self._alt_m < 0.5 and self._mode in ("land", "rtl"):
                    self._armed = False
                    self._mode = "manual"
                    self.state = DroneState.READY

                self._battery = max(85.0, 100.0 - t * 0.01)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    async def _publish_telemetry(self, rate_hz: float) -> None:
        interval = 1.0 / rate_hz
        try:
            while self._telemetry_callback:
                payload = await self.get_telemetry()
                result = self._telemetry_callback(payload)
                if asyncio.iscoroutine(result):
                    await result
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
