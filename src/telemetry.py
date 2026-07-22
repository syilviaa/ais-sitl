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

try:
    from mavsdk import System
    MAVSDK_AVAILABLE = True
except ImportError:
    MAVSDK_AVAILABLE = False

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
        system: Optional[System] = None,
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

        # Collection control
        self._collecting = False
        self._collection_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_telemetry_callbacks: List[Callable] = []

        # Statistics
        self._update_count = 0
        self._last_update_time = time.time()

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
        self._collection_task = asyncio.create_task(self._collection_loop())

    async def stop(self):
        """Stop telemetry collection."""
        logger.info("🔴 Stopping telemetry collection")
        self._collecting = False

        if self._collection_task:
            try:
                await asyncio.wait_for(self._collection_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Telemetry collection task timeout")
                self._collection_task.cancel()

    # ========================================================================
    # Data Access
    # ========================================================================

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

        return {
            "updates": self._update_count,
            "actual_rate_hz": actual_rate,
            "target_rate_hz": self._rate_hz,
            "history_size": len(self._history),
            "collecting": self._collecting,
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
        if not MAVSDK_AVAILABLE or not self._system:
            return self._get_stub_telemetry()

        try:
            # Collect data from MAVSDK streams (async)
            position = await self._get_position()
            velocity = await self._get_velocity()
            attitude = await self._get_attitude()
            battery = await self._get_battery()
            gps = await self._get_gps()
            armed = await self._get_armed()
            flight_mode = await self._get_flight_mode()

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
                battery_percent=battery["percent"],
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
    # MAVSDK Data Streams
    # ========================================================================

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
                speed = (vel.north_m_s**2 + vel.east_m_s**2) ** 0.5
                return {
                    "vx": vel.north_m_s,
                    "vy": vel.east_m_s,
                    "vz": vel.down_m_s,
                    "speed": speed,
                }
        except Exception as e:
            logger.error(f"Velocity stream error: {e}")
            return {"vx": 0.0, "vy": 0.0, "vz": 0.0, "speed": 0.0}

    async def _get_attitude(self) -> dict:
        """Get attitude (Euler angles) from MAVSDK."""
        try:
            async for att in self._system.telemetry.attitude_euler_deg():
                return {
                    "roll": att.roll_deg,
                    "pitch": att.pitch_deg,
                    "yaw": att.yaw_deg,
                }
        except Exception as e:
            logger.error(f"Attitude stream error: {e}")
            return {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}

    async def _get_battery(self) -> dict:
        """Get battery status from MAVSDK."""
        try:
            async for bat in self._system.telemetry.battery():
                return {
                    "percent": bat.remaining_percent * 100,
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

    def _get_stub_telemetry(self) -> TelemetrySnapshot:
        """Generate stub telemetry for testing without MAVSDK."""
        return TelemetrySnapshot(
            timestamp=time.time(),
            lat=47.39770,
            lon=8.54550,
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
