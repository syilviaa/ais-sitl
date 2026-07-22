"""
Mission Management System

Loads and executes missions in PX4 SITL:
- Upload waypoints to autopilot
- Monitor mission progress
- Handle mission events
- Convert Waypoint → MAVSDK MissionItem

Timeline: Veha 2-3 (July 22-23, 2026)
Owner: Мерей
"""

import asyncio
import logging
from typing import List, Optional, Callable

from src.models import Waypoint, MissionItem, MissionProgress

try:
    from mavsdk import System
    MAVSDK_AVAILABLE = True
except ImportError:
    MAVSDK_AVAILABLE = False

logger = logging.getLogger(__name__)


class MissionService:
    """
    Mission management and execution.

    Workflow:
    1. Create mission from waypoints
    2. Validate mission
    3. Upload to autopilot
    4. Start mission
    5. Monitor progress
    6. Handle completion

    Usage:
        service = MissionService(system)
        waypoints = [
            Waypoint(47.39, 8.54, 50),
            Waypoint(47.40, 8.55, 50),
        ]
        await service.upload_mission(waypoints)
        await service.start_mission()

        while True:
            progress = await service.get_progress()
            print(f"Waypoint {progress.current_waypoint}/{progress.total_waypoints}")
            if progress.is_mission_finished:
                break
            await asyncio.sleep(1.0)
    """

    def __init__(self, system: Optional[System] = None):
        """
        Initialize mission service.

        Args:
            system: MAVSDK System instance (None for stub mode)
        """
        self._system = system
        self._mission_uploaded = False
        self._mission_running = False
        self._current_mission_items: List[MissionItem] = []
        self._on_progress_callbacks: List[Callable] = []

        logger.info("MissionService initialized")

    # ========================================================================
    # Mission Upload
    # ========================================================================

    async def upload_mission(self, waypoints: List[Waypoint]) -> bool:
        """
        Upload mission to autopilot.

        Args:
            waypoints: List of Waypoint objects

        Returns:
            True if successful

        Raises:
            ValueError: If waypoints list is empty
        """
        if not waypoints:
            raise ValueError("Mission must have at least 1 waypoint")

        logger.info(f"Uploading mission with {len(waypoints)} waypoints")

        # Convert waypoints to MissionItems
        mission_items = [MissionItem.from_waypoint(wp) for wp in waypoints]
        self._current_mission_items = mission_items

        # Upload to autopilot
        if not MAVSDK_AVAILABLE or not self._system:
            logger.info("✅ Mission uploaded (stub mode)")
            self._mission_uploaded = True
            return True

        try:
            logger.debug(f"Uploading {len(mission_items)} items to autopilot")

            # MAVSDK mission upload
            mission_plan = self._system.mission.import_qgroundcontrol_mission(
                mission_items
            )
            await self._system.mission.upload_mission(mission_plan)

            logger.info("✅ Mission uploaded successfully")
            self._mission_uploaded = True
            return True

        except Exception as e:
            logger.error(f"❌ Mission upload failed: {e}")
            self._mission_uploaded = False
            return False

    # ========================================================================
    # Mission Execution
    # ========================================================================

    async def start_mission(self) -> bool:
        """
        Start mission execution.

        Returns:
            True if successful

        Raises:
            RuntimeError: If no mission uploaded
        """
        if not self._mission_uploaded:
            raise RuntimeError("No mission uploaded. Call upload_mission() first.")

        logger.info("Starting mission execution")

        if not MAVSDK_AVAILABLE or not self._system:
            logger.info("✅ Mission started (stub mode)")
            self._mission_running = True
            return True

        try:
            await self._system.mission.start_mission()
            logger.info("✅ Mission started")
            self._mission_running = True
            return True

        except Exception as e:
            logger.error(f"❌ Mission start failed: {e}")
            return False

    async def pause_mission(self) -> bool:
        """Pause mission execution."""
        if not self._mission_running:
            logger.warning("No mission running to pause")
            return False

        logger.info("Pausing mission")

        if not MAVSDK_AVAILABLE or not self._system:
            self._mission_running = False
            return True

        try:
            # PX4 doesn't have native pause, use hold instead
            await self._system.action.hold()
            logger.info("✅ Mission paused")
            self._mission_running = False
            return True

        except Exception as e:
            logger.error(f"❌ Pause failed: {e}")
            return False

    async def resume_mission(self) -> bool:
        """Resume paused mission."""
        logger.info("Resuming mission")

        if not MAVSDK_AVAILABLE or not self._system:
            self._mission_running = True
            return True

        try:
            await self._system.mission.start_mission()
            logger.info("✅ Mission resumed")
            self._mission_running = True
            return True

        except Exception as e:
            logger.error(f"❌ Resume failed: {e}")
            return False

    async def abort_mission(self) -> bool:
        """Abort mission and return to launch."""
        logger.warning("Aborting mission - RTL")
        self._mission_running = False

        if not MAVSDK_AVAILABLE or not self._system:
            return True

        try:
            await self._system.action.return_to_launch()
            logger.info("✅ Mission aborted - RTL initiated")
            return True

        except Exception as e:
            logger.error(f"❌ Abort failed: {e}")
            return False

    # ========================================================================
    # Mission Progress
    # ========================================================================

    async def get_progress(self) -> Optional[MissionProgress]:
        """
        Get current mission progress.

        Returns:
            MissionProgress object or None if not available
        """
        if not MAVSDK_AVAILABLE or not self._system:
            # Stub: return progress as if mission running
            return MissionProgress(
                current_waypoint=0,
                total_waypoints=len(self._current_mission_items),
                is_mission_finished=False,
            )

        try:
            async for progress in self._system.mission.mission_progress():
                mission_progress = MissionProgress(
                    current_waypoint=progress.current,
                    total_waypoints=progress.total,
                    is_mission_finished=progress.current >= progress.total,
                )

                # Notify callbacks
                await self._notify_callbacks(mission_progress)

                return mission_progress

        except Exception as e:
            logger.error(f"Failed to get mission progress: {e}")
            return None

    async def is_mission_finished(self) -> bool:
        """Check if mission is complete."""
        progress = await self.get_progress()
        if progress:
            return progress.is_mission_finished
        return False

    # ========================================================================
    # Callbacks
    # ========================================================================

    def on_progress(self, callback: Callable[[MissionProgress], None]):
        """Register callback for mission progress updates."""
        self._on_progress_callbacks.append(callback)

    async def _notify_callbacks(self, progress: MissionProgress):
        """Notify all registered callbacks."""
        for callback in self._on_progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress)
                else:
                    callback(progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    # ========================================================================
    # Mission Info
    # ========================================================================

    def get_current_mission(self) -> List[MissionItem]:
        """Get currently loaded mission items."""
        return self._current_mission_items

    def get_mission_stats(self) -> dict:
        """Get mission statistics."""
        total_items = len(self._current_mission_items)

        # Calculate total distance (rough estimate)
        total_distance_m = 0.0
        if total_items >= 2:
            for i in range(total_items - 1):
                item1 = self._current_mission_items[i]
                item2 = self._current_mission_items[i + 1]

                # Simple distance calc (lat/lon difference in meters)
                # Real implementation would use proper geodetic distance
                lat_diff = (item2.latitude_deg - item1.latitude_deg) * 111000
                lon_diff = (item2.longitude_deg - item1.longitude_deg) * 111000
                distance = (lat_diff**2 + lon_diff**2) ** 0.5
                total_distance_m += distance

        return {
            "total_waypoints": total_items,
            "estimated_distance_m": total_distance_m,
            "uploaded": self._mission_uploaded,
            "running": self._mission_running,
        }

    # ========================================================================
    # Validation
    # ========================================================================

    @staticmethod
    def validate_mission(waypoints: List[Waypoint]) -> tuple[bool, str]:
        """
        Validate mission before upload.

        Args:
            waypoints: Mission waypoints to validate

        Returns:
            (is_valid, error_message)
        """
        if not waypoints:
            return False, "Mission must have at least 1 waypoint"

        if len(waypoints) > 500:
            return False, "Mission has too many waypoints (max 500)"

        # Check each waypoint
        for i, wp in enumerate(waypoints):
            # Check GPS bounds
            if not (-90 <= wp.lat <= 90):
                return False, f"Waypoint {i}: invalid latitude {wp.lat}"

            if not (-180 <= wp.lon <= 180):
                return False, f"Waypoint {i}: invalid longitude {wp.lon}"

            # Check altitude
            if wp.altitude_m < 0:
                return False, f"Waypoint {i}: negative altitude"

            if wp.altitude_m > 10000:
                return False, f"Waypoint {i}: altitude too high (max 10000m)"

            # Check speed
            if wp.speed_m_s < 1 or wp.speed_m_s > 30:
                return False, f"Waypoint {i}: invalid speed {wp.speed_m_s}"

        return True, "Mission valid"


class MissionPlanner:
    """
    High-level mission planning utility.

    Helper for creating missions from scratch.
    """

    @staticmethod
    def create_simple_mission(
        home_lat: float,
        home_lon: float,
        home_alt: float,
        altitude: float,
        distance_m: float,
        num_waypoints: int = 4,
    ) -> List[Waypoint]:
        """
        Create simple rectangular mission.

        Args:
            home_lat, home_lon, home_alt: Home position
            altitude: Mission altitude
            distance_m: Distance from home to each corner
            num_waypoints: Number of waypoints in rectangle

        Returns:
            List of Waypoint objects
        """
        waypoints = []

        # Convert distance to lat/lon degrees (rough)
        lat_offset = distance_m / 111000
        lon_offset = distance_m / 111000

        # Rectangle corners
        corners = [
            (home_lat + lat_offset, home_lon + lon_offset),
            (home_lat + lat_offset, home_lon - lon_offset),
            (home_lat - lat_offset, home_lon - lon_offset),
            (home_lat - lat_offset, home_lon + lon_offset),
        ]

        # Add waypoints
        for lat, lon in corners:
            waypoints.append(Waypoint(lat=lat, lon=lon, altitude_m=altitude))

        # Return home
        waypoints.append(
            Waypoint(lat=home_lat, lon=home_lon, altitude_m=home_alt)
        )

        return waypoints

    @staticmethod
    def create_loiter_mission(
        lat: float,
        lon: float,
        altitude: float,
        loiter_time_sec: float = 60.0,
    ) -> List[Waypoint]:
        """
        Create loiter (hover) mission at single point.

        Args:
            lat, lon: Position
            altitude: Altitude
            loiter_time_sec: How long to hover

        Returns:
            List with single loiter waypoint
        """
        return [
            Waypoint(
                lat=lat,
                lon=lon,
                altitude_m=altitude,
                wait_time_s=loiter_time_sec,
            )
        ]
