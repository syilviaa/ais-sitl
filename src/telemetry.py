"""
Telemetry Collection System

Collects drone telemetry at 10 Hz (100ms interval):
- GPS position (lat, lon, altitude)
- Velocity (vx, vy, vz)
- Attitude (roll, pitch, yaw)
- Battery status
- Flight mode & armed state
- GPS fix quality

Timeline: Veha 2-3 (July 21-25, 2026)
Owner: Мерей
"""

import asyncio
import logging
import time
from typing import Optional, List, Callable
from collections import deque
from datetime import datetime

from src.models import TelemetrySnapshot, GPSFixType, FlightMode
from src.telemetry_battery import BatterySimulator

from src.mavsdk_import import IMPORT_ERROR, MAVSDK_AVAILABLE, System

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """
    Collects telemetry from PX4 SITL at 10 Hz.

    Streams:
    - Position (lat, lon, altitude)
    - Velocity (vx, vy, vz)
    - Attitude (roll, pitch, yaw)
    - Battery status
    - GPS quality
    - Flight mode

    Usage:
        collector = TelemetryCollector(system)
        await collector.start()

        while True:
            telemetry = collector.get_latest()
            print(f"Altitude: {telemetry.altitude_m}m")
            await asyncio.sleep(0.1)

        await collector.stop()
    """

    def __init__(
        self,
        system: Optional["System"] = None,
        rate_hz: float = 10.0,
        history_size: int = 100,
    ):
        """
        Initialize telemetry collector.

        Args:
            system: MAVSDK System instance (None for stub mode)
            rate_hz: Collection rate in Hz (default: 10 Hz)
            history_size: Keep last N telemetry snapshots
        """
        self._system = system
        self._rate_hz = rate_hz
        self._rate_interval_sec = 1.0 / rate_hz  # 0.1 sec for 10 Hz
        self._history_size = history_size

        # Telemetry state
        self._latest_snapshot: Optional[TelemetrySnapshot] = None
        self._history: deque = deque(maxlen=history_size)
        self._demo_drone = None
        self._drone_source = None
        self._battery_sim = BatterySimulator()

        # Collection control
        self._collecting = False
        self._collection_task: Optional[asyncio.Task] = None
        self._stream_tasks: List[asyncio.Task] = []

        # Latest values from MAVSDK background streams (non-blocking reads)
        self._stream_cache: dict = {
            "position": None,
            "velocity": None,
            "attitude": None,
            "battery": None,
            "gps": None,
            "armed": None,
            "flight_mode": None,
        }

        # Callbacks
        self._on_telemetry_callbacks: List[Callable] = []

        # Statistics
        self._update_count = 0
        self._last_update_time = time.time()
        self._latency_samples: deque = deque(maxlen=100)

        logger.info(f"TelemetryCollector initialized at {rate_hz} Hz")

    # ========================================================================
    # Lifecycle
    # ========================================================================

    async def start(self):
        """Start background telemetry collection."""
        if self._collecting:
            logger.warning("Telemetry collection already running")
            return

        logger.info(f"🟢 Starting telemetry collection at {self._rate_hz} Hz")
        self._collecting = True
        self._start_stream_consumers()
        self._collection_task = asyncio.create_task(self._collection_loop())

    async def rebind_system(self, system) -> None:
        """Attach to a fresh MAVSDK system after a link recovery."""
        for task in self._stream_tasks:
            if not task.done():
                task.cancel()
        if self._stream_tasks:
            await asyncio.gather(*self._stream_tasks, return_exceptions=True)
        self._stream_tasks = []
        self._system = system
        for key in self._stream_cache:
            self._stream_cache[key] = None
        if self._collecting:
            self._start_stream_consumers()

    async def stop(self):
        """Stop telemetry collection."""
        logger.info("🔴 Stopping telemetry collection")
        self._collecting = False

        for task in self._stream_tasks:
            if not task.done():
                task.cancel()
        if self._stream_tasks:
            await asyncio.gather(*self._stream_tasks, return_exceptions=True)
        self._stream_tasks = []

        if self._collection_task:
            try:
                await asyncio.wait_for(self._collection_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Telemetry collection task timeout")
                self._collection_task.cancel()

    # ========================================================================
    # Data Access
    # ========================================================================

    def set_demo_drone(self, drone) -> None:
        """Use demo drone telemetry instead of MAVSDK/stub."""
        self._demo_drone = drone

    def set_drone_source(self, drone) -> None:
        """Read from the Drone's existing streams instead of opening new ones.

        mavsdk_server aborts on MAVLink heartbeat timeout once its user callback
        queue backs up, which happens as soon as the collector duplicates the
        seven subscriptions the Drone already holds on the same server.
        """
        self._drone_source = drone

    def get_latest(self) -> Optional[TelemetrySnapshot]:
        """
        Get latest telemetry snapshot (non-blocking).

        Returns:
            Latest TelemetrySnapshot or None if no data yet
        """
        return self._latest_snapshot

    def get_history(self, count: int = 10) -> List[TelemetrySnapshot]:
        """
        Get last N telemetry snapshots.

        Args:
            count: Number of snapshots to return

        Returns:
            List of TelemetrySnapshot objects (most recent first)
        """
        return list(reversed(list(self._history)))[:count]

    def get_statistics(self) -> dict:
        """Get collection statistics."""
        elapsed = time.time() - self._last_update_time
        actual_rate = self._update_count / elapsed if elapsed > 0 else 0
        samples = list(self._latency_samples)
        avg_latency = sum(samples) / len(samples) if samples else 0.0
        max_latency = max(samples) if samples else 0.0

        return {
            "updates": self._update_count,
            "actual_rate_hz": actual_rate,
            "target_rate_hz": self._rate_hz,
            "history_size": len(self._history),
            "collecting": self._collecting,
            "avg_latency_ms": round(avg_latency, 2),
            "max_latency_ms": round(max_latency, 2),
            "rtt_target_ms": 50.0,
            "rtt_ok": max_latency < 50.0 if samples else True,
        }

    # ========================================================================
    # Callbacks
    # ========================================================================

    def on_telemetry(self, callback: Callable[[TelemetrySnapshot], None]):
        """
        Register callback for telemetry updates.

        Args:
            callback: Function(TelemetrySnapshot) called on each update
        """
        self._on_telemetry_callbacks.append(callback)

    async def _notify_callbacks(self, snapshot: TelemetrySnapshot):
        """Notify all registered callbacks."""
        for callback in self._on_telemetry_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(snapshot)
                else:
                    callback(snapshot)
            except Exception as e:
                logger.error(f"Telemetry callback error: {e}")

    # ========================================================================
    # Collection Loop
    # ========================================================================

    async def _collection_loop(self):
        """Background task: collect telemetry at 10 Hz."""
        logger.debug("Telemetry collection loop started")

        try:
            while self._collecting:
                start_time = time.time()

                # Collect telemetry
                snapshot = await self._collect_snapshot()

                if snapshot:
                    now = time.time()
                    interval_ms = (now - self._last_update_time) * 1000.0
                    self._last_update_time = now
                    snapshot.latency_ms = interval_ms
                    self._latency_samples.append(interval_ms)

                    self._latest_snapshot = snapshot
                    self._history.append(snapshot)
                    self._update_count += 1

                    # Notify callbacks
                    await self._notify_callbacks(snapshot)

                # Maintain 10 Hz rate (100ms interval)
                elapsed = time.time() - start_time
                sleep_time = max(0, self._rate_interval_sec - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                elif elapsed > self._rate_interval_sec * 1.5:
                    logger.warning(
                        f"Telemetry collection slow: "
                        f"{elapsed:.3f}s (target: {self._rate_interval_sec:.3f}s)"
                    )

        except Exception as e:
            logger.error(f"Telemetry collection error: {e}")
        finally:
            logger.debug("Telemetry collection loop ended")

    async def _collect_snapshot(self) -> Optional[TelemetrySnapshot]:
        """Collect single telemetry snapshot from MAVSDK."""
        if self._demo_drone is not None:
            return self._snapshot_from_demo(await self._demo_drone.get_telemetry())

        if self._drone_source is not None:
            return self._snapshot_from_drone(
                await self._drone_source.get_telemetry()
            )

        if not MAVSDK_AVAILABLE or not self._system:
            return self._get_stub_telemetry()

        try:
            position = self._stream_cache["position"] or self._default_position()
            velocity = self._stream_cache["velocity"] or self._default_velocity()
            attitude = self._stream_cache["attitude"] or self._default_attitude()
            battery = self._stream_cache["battery"] or self._default_battery()
            gps = self._stream_cache["gps"] or self._default_gps()
            armed = (
                self._stream_cache["armed"]
                if self._stream_cache["armed"] is not None
                else False
            )
            flight_mode = self._stream_cache["flight_mode"] or "unknown"

            # Create snapshot
            snapshot = TelemetrySnapshot(
                timestamp=time.time(),
                lat=position["lat"],
                lon=position["lon"],
                altitude_m=position["alt"],
                altitude_msl_m=position["alt_msl"],
                vx=velocity["vx"],
                vy=velocity["vy"],
                vz=velocity["vz"],
                speed_m_s=velocity["speed"],
                roll_deg=attitude["roll"],
                pitch_deg=attitude["pitch"],
                yaw_deg=attitude["yaw"],
                battery_percent=self._battery_sim.tick(
                    armed=armed,
                    mode=flight_mode,
                    alt_m=position["alt"],
                ),
                battery_voltage_v=battery["voltage"],
                battery_current_a=battery["current"],
                gps_fix=gps["fix"],
                satellites=gps["satellites"],
                armed=armed,
                flight_mode=flight_mode,
                in_air=position["alt"] > 0.5,
                ground_distance_m=position["distance"],
            )

            return snapshot

        except Exception as e:
            logger.error(f"Telemetry collection failed: {e}")
            return None

    # ========================================================================
    # MAVSDK background streams (subscribe once, read from cache at 10 Hz)
    # ========================================================================

    def _start_stream_consumers(self) -> None:
        if not MAVSDK_AVAILABLE or not self._system or self._stream_tasks:
            return
        if self._demo_drone is not None or self._drone_source is not None:
            return
        self._stream_tasks = [
            asyncio.create_task(self._consume_position()),
            asyncio.create_task(self._consume_velocity()),
            asyncio.create_task(self._consume_attitude()),
            asyncio.create_task(self._consume_battery()),
            asyncio.create_task(self._consume_gps()),
            asyncio.create_task(self._consume_armed()),
            asyncio.create_task(self._consume_flight_mode()),
        ]

    async def _consume_position(self) -> None:
        try:
            async for pos in self._system.telemetry.position():
                self._stream_cache["position"] = {
                    "lat": pos.latitude_deg,
                    "lon": pos.longitude_deg,
                    "alt": pos.relative_altitude_m,
                    "alt_msl": pos.absolute_altitude_m,
                    "distance": pos.distance_m if hasattr(pos, "distance_m") else 0.0,
                }
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Position stream error: {e}")

    @staticmethod
    def _speed_m_s(north: float, east: float, down: float) -> float:
        """Total speed (m/s) — includes vertical during takeoff/hover."""
        return (north * north + east * east + down * down) ** 0.5

    @staticmethod
    def _velocity_dict(north: float, east: float, down: float) -> dict:
        total = TelemetryCollector._speed_m_s(north, east, down)
        return {
            "vx": north,
            "vy": east,
            "vz": down,
            "speed": total,
            "ground_speed": (north * north + east * east) ** 0.5,
            "vertical_speed": abs(down),
        }

    async def _consume_velocity(self) -> None:
        try:
            async for vel in self._system.telemetry.velocity_ned():
                self._stream_cache["velocity"] = self._velocity_dict(
                    vel.north_m_s, vel.east_m_s, vel.down_m_s
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Velocity stream error: {e}")

    async def _consume_attitude(self) -> None:
        try:
            async for att in self._system.telemetry.attitude_euler():
                self._stream_cache["attitude"] = {
                    "roll": att.roll_deg,
                    "pitch": att.pitch_deg,
                    "yaw": att.yaw_deg,
                }
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Attitude stream error: {e}")

    async def _consume_battery(self) -> None:
        try:
            async for bat in self._system.telemetry.battery():
                percent = bat.remaining_percent
                if percent is not None and percent <= 1.0:
                    percent *= 100.0
                self._stream_cache["battery"] = {
                    "percent": percent if percent is not None else 100.0,
                    "voltage": bat.voltage_v if hasattr(bat, "voltage_v") else 0.0,
                    "current": bat.current_a if hasattr(bat, "current_a") else 0.0,
                }
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Battery stream error: {e}")

    async def _consume_gps(self) -> None:
        try:
            async for gps in self._system.telemetry.gps_info():
                fix = "no_fix"
                if gps.fix_type == 3:
                    fix = "3d"
                elif gps.fix_type == 2:
                    fix = "2d"
                self._stream_cache["gps"] = {
                    "fix": fix,
                    "satellites": gps.num_satellites,
                }
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"GPS stream error: {e}")

    async def _consume_armed(self) -> None:
        try:
            async for armed in self._system.telemetry.armed():
                self._stream_cache["armed"] = armed
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Armed stream error: {e}")

    async def _consume_flight_mode(self) -> None:
        try:
            async for mode in self._system.telemetry.flight_mode():
                self._stream_cache["flight_mode"] = str(mode).split(".")[-1].lower()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Flight mode stream error: {e}")

    @staticmethod
    def _default_position() -> dict:
        return {
            "lat": 0.0,
            "lon": 0.0,
            "alt": 0.0,
            "alt_msl": 0.0,
            "distance": 0.0,
        }

    @staticmethod
    def _default_velocity() -> dict:
        return {
            "vx": 0.0, "vy": 0.0, "vz": 0.0, "speed": 0.0,
            "ground_speed": 0.0, "vertical_speed": 0.0,
        }

    @staticmethod
    def _default_attitude() -> dict:
        return {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}

    @staticmethod
    def _default_battery() -> dict:
        return {"percent": 100.0, "voltage": 0.0, "current": 0.0}

    @staticmethod
    def _default_gps() -> dict:
        return {"fix": "no_fix", "satellites": 0}

    # Legacy per-call stream readers (kept for tests / compatibility)
    async def _get_position(self) -> dict:
        """Get position from MAVSDK."""
        try:
            async for pos in self._system.telemetry.position():
                return {
                    "lat": pos.latitude_deg,
                    "lon": pos.longitude_deg,
                    "alt": pos.relative_altitude_m,
                    "alt_msl": pos.absolute_altitude_m,
                    "distance": pos.distance_m if hasattr(pos, "distance_m") else 0.0,
                }
        except Exception as e:
            logger.error(f"Position stream error: {e}")
            return {
                "lat": 0.0,
                "lon": 0.0,
                "alt": 0.0,
                "alt_msl": 0.0,
                "distance": 0.0,
            }

    async def _get_velocity(self) -> dict:
        """Get velocity from MAVSDK."""
        try:
            async for vel in self._system.telemetry.velocity_ned():
                return self._velocity_dict(
                    vel.north_m_s, vel.east_m_s, vel.down_m_s
                )
        except Exception as e:
            logger.error(f"Velocity stream error: {e}")
            return {"vx": 0.0, "vy": 0.0, "vz": 0.0, "speed": 0.0}

    async def _get_attitude(self) -> dict:
        """Get attitude (Euler angles) from MAVSDK."""
        try:
            async for att in self._system.telemetry.attitude_euler():
                return {
                    "roll": att.roll_deg,
                    "pitch": att.pitch_deg,
                    "yaw": att.yaw_deg,
                }
        except Exception as e:
            logger.error(f"Attitude stream error: {e}")
            return self._default_attitude()

    async def _get_battery(self) -> dict:
        """Get battery status from MAVSDK."""
        try:
            async for bat in self._system.telemetry.battery():
                percent = bat.remaining_percent
                if percent is not None and percent <= 1.0:
                    percent *= 100.0
                return {
                    "percent": percent if percent is not None else 100.0,
                    "voltage": bat.voltage_v if hasattr(bat, "voltage_v") else 0.0,
                    "current": bat.current_a if hasattr(bat, "current_a") else 0.0,
                }
        except Exception as e:
            logger.error(f"Battery stream error: {e}")
            return {"percent": 100.0, "voltage": 0.0, "current": 0.0}

    async def _get_gps(self) -> dict:
        """Get GPS status from MAVSDK."""
        try:
            async for gps in self._system.telemetry.gps_info():
                fix = "no_fix"
                if gps.fix_type == 3:
                    fix = "3d"
                elif gps.fix_type == 2:
                    fix = "2d"

                return {
                    "fix": fix,
                    "satellites": gps.num_satellites,
                }
        except Exception as e:
            logger.error(f"GPS stream error: {e}")
            return {"fix": "no_fix", "satellites": 0}

    async def _get_armed(self) -> bool:
        """Get armed state from MAVSDK."""
        try:
            async for armed in self._system.telemetry.armed():
                return armed
        except Exception as e:
            logger.error(f"Armed stream error: {e}")
            return False

    async def _get_flight_mode(self) -> str:
        """Get flight mode from MAVSDK."""
        try:
            async for mode in self._system.telemetry.flight_mode():
                return str(mode).split(".")[-1].lower()
        except Exception as e:
            logger.error(f"Flight mode stream error: {e}")
            return "unknown"

    # ========================================================================
    # Stub Mode (when MAVSDK not available)
    # ========================================================================

    def _snapshot_from_demo(self, data: dict) -> TelemetrySnapshot:
        """Build snapshot from DemoDrone flat telemetry dict."""
        return TelemetrySnapshot(
            timestamp=data.get("timestamp", time.time()),
            lat=data.get("lat", 51.1694),
            lon=data.get("lon", 71.4491),
            altitude_m=data.get("alt", data.get("relative_altitude_m", 0.0)),
            altitude_msl_m=data.get("absolute_altitude_m", 0.0),
            vx=data.get("vx", 0.0),
            vy=data.get("vy", 0.0),
            vz=data.get("vz", 0.0),
            roll_deg=data.get("roll", 0.0),
            pitch_deg=data.get("pitch", 0.0),
            yaw_deg=data.get("yaw", 0.0),
            battery_percent=data.get("battery", data.get("battery_percent", 100.0)),
            gps_fix=data.get("gps_fix", "3d"),
            satellites=data.get("satellites", 12),
            armed=data.get("armed", False),
            flight_mode=data.get("mode", data.get("flight_mode", "manual")),
            in_air=data.get("alt", 0.0) > 0.5,
        )

    def _snapshot_from_drone(self, data: dict) -> TelemetrySnapshot:
        """Build snapshot from the Drone's cached MAVSDK telemetry."""
        vx = data.get("vx") or 0.0
        vy = data.get("vy") or 0.0
        vz = data.get("vz") or 0.0
        alt = data.get("alt") or data.get("relative_altitude_m") or 0.0
        armed = bool(data.get("armed"))
        mode = data.get("mode") or data.get("flight_mode") or "unknown"
        return TelemetrySnapshot(
            timestamp=data.get("timestamp") or time.time(),
            lat=data.get("lat") or 0.0,
            lon=data.get("lon") or 0.0,
            altitude_m=alt,
            altitude_msl_m=data.get("absolute_altitude_m") or 0.0,
            vx=vx,
            vy=vy,
            vz=vz,
            speed_m_s=self._speed_m_s(vx, vy, vz),
            roll_deg=data.get("roll") or 0.0,
            pitch_deg=data.get("pitch") or 0.0,
            yaw_deg=data.get("yaw") or 0.0,
            battery_percent=self._battery_sim.tick(
                armed=armed,
                mode=mode,
                alt_m=alt,
            ),
            gps_fix=data.get("gps_fix") or data.get("gps_status") or "3d",
            satellites=data.get("satellites") or 0,
            armed=armed,
            flight_mode=mode,
            in_air=alt > 0.5,
        )

    def _get_stub_telemetry(self) -> TelemetrySnapshot:
        """Generate stub telemetry for testing without MAVSDK."""
        return TelemetrySnapshot(
            timestamp=time.time(),
            lat=51.1694,
            lon=71.4491,
            altitude_m=0.0,
            vx=0.0,
            vy=0.0,
            vz=0.0,
            roll_deg=0.0,
            pitch_deg=0.0,
            yaw_deg=0.0,
            battery_percent=100.0,
            gps_fix="3d",
            satellites=12,
            armed=False,
            flight_mode="manual",
        )
