"""
Drone Coordinator - Manages multiple drones simultaneously.

Features:
- Drone fleet management
- Multi-drone command execution
- Conflict detection & resolution
- Coordinated mission execution
"""

import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DroneStatus:
    """Status of a single drone."""

    drone_id: str
    name: str
    connected: bool
    state: str
    battery_percent: float
    lat: float
    lon: float
    altitude: float
    last_update: float


class DroneCoordinator:
    """Coordinates operations across multiple drones."""

    def __init__(self):
        """Initialize coordinator."""
        self.drones: Dict[str, any] = {}  # drone_id -> DroneService
        self.locks: Dict[str, asyncio.Lock] = {}  # Per-drone locking
        self.fleet_lock = asyncio.Lock()

    async def add_drone(self, drone_id: str, service):
        """Add drone to fleet."""
        async with self.fleet_lock:
            if drone_id in self.drones:
                logger.warning(f"Drone {drone_id} already in fleet")
                return False

            self.drones[drone_id] = service
            self.locks[drone_id] = asyncio.Lock()
            logger.info(f"✅ Added drone {drone_id} to fleet")
            return True

    async def remove_drone(self, drone_id: str):
        """Remove drone from fleet."""
        async with self.fleet_lock:
            if drone_id not in self.drones:
                logger.warning(f"Drone {drone_id} not in fleet")
                return False

            del self.drones[drone_id]
            del self.locks[drone_id]
            logger.info(f"✅ Removed drone {drone_id} from fleet")
            return True

    async def get_drone(self, drone_id: str):
        """Get drone service by ID."""
        if drone_id not in self.drones:
            raise ValueError(f"Drone {drone_id} not found")
        return self.drones[drone_id]

    async def list_drones(self) -> List[str]:
        """List all drone IDs."""
        async with self.fleet_lock:
            return list(self.drones.keys())

    async def get_fleet_status(self) -> Dict[str, DroneStatus]:
        """Get status of all drones."""
        statuses = {}

        tasks = []
        for drone_id, service in self.drones.items():
            tasks.append(self._get_drone_status(drone_id, service))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for drone_id, result in zip(self.drones.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Error getting status for {drone_id}: {result}")
            else:
                statuses[drone_id] = result

        return statuses

    async def _get_drone_status(self, drone_id: str, service) -> DroneStatus:
        """Get status of single drone."""
        try:
            status = await service.get_status()
            telemetry = status.get("telemetry", {})

            return DroneStatus(
                drone_id=drone_id,
                name=getattr(service, "name", drone_id),
                connected=status.get("connected", False),
                state=status.get("state", "unknown"),
                battery_percent=telemetry.get("battery", 0),
                lat=telemetry.get("lat", 0),
                lon=telemetry.get("lon", 0),
                altitude=telemetry.get("alt", 0),
                last_update=telemetry.get("timestamp", 0),
            )
        except Exception as e:
            logger.error(f"Error getting status for {drone_id}: {e}")
            raise

    async def broadcast_command(self, command: str, data: dict = None, exclude: List[str] = None):
        """Execute command on all drones."""
        exclude = exclude or []
        results = {}

        tasks = []
        active_drones = [d for d in self.drones if d not in exclude]

        for drone_id in active_drones:
            tasks.append(self._execute_command_on_drone(drone_id, command, data))

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for drone_id, result in zip(active_drones, results_list):
            if isinstance(result, Exception):
                results[drone_id] = {"success": False, "error": str(result)}
            else:
                results[drone_id] = result

        return results

    async def _execute_command_on_drone(self, drone_id: str, command: str, data: dict):
        """Execute single command on drone."""
        async with self.locks[drone_id]:
            service = self.drones[drone_id]

            try:
                if command == "arm":
                    await service.arm()
                    return {"success": True, "message": "Armed"}
                elif command == "disarm":
                    await service.disarm()
                    return {"success": True, "message": "Disarmed"}
                elif command == "takeoff":
                    altitude = data.get("altitude", 50) if data else 50
                    await service.takeoff(altitude)
                    return {"success": True, "message": f"Takeoff to {altitude}m"}
                elif command == "land":
                    await service.land()
                    return {"success": True, "message": "Landing"}
                elif command == "hold":
                    await service.hold_position()
                    return {"success": True, "message": "Holding position"}
                elif command == "rtl":
                    reason = data.get("reason", "coordinated_rtl") if data else "coordinated_rtl"
                    await service.return_to_launch(reason=reason)
                    return {"success": True, "message": "RTL initiated"}
                else:
                    return {"success": False, "error": f"Unknown command: {command}"}

            except Exception as e:
                logger.error(f"Error executing {command} on {drone_id}: {e}")
                return {"success": False, "error": str(e)}

    async def coordinated_takeoff(self, drone_ids: List[str], altitude: float, start_delay: float = 0.0):
        """
        Execute coordinated takeoff on multiple drones.

        Args:
            drone_ids: List of drone IDs to takeoff
            altitude: Target altitude
            start_delay: Delay between drone takeoffs (seconds)
        """
        logger.info(f"Coordinated takeoff: {drone_ids} to {altitude}m, delay={start_delay}s")

        for i, drone_id in enumerate(drone_ids):
            if i > 0:
                await asyncio.sleep(start_delay)

            try:
                service = await self.get_drone(drone_id)
                await service.takeoff(altitude)
                logger.info(f"✅ {drone_id} takeoff initiated")
            except Exception as e:
                logger.error(f"❌ {drone_id} takeoff failed: {e}")

    async def emergency_stop_all(self):
        """Emergency stop all drones (land immediately)."""
        logger.critical("🚨 EMERGENCY STOP ALL DRONES")
        await self.broadcast_command("land")

    async def check_airspace_conflicts(self) -> Dict[str, List[str]]:
        """
        Check for potential airspace conflicts between drones.

        Returns:
            Dict of {drone_id: [list of conflicting drone IDs]}
        """
        conflicts = {}
        statuses = await self.get_fleet_status()

        drone_list = list(statuses.items())

        for i, (drone_id_1, status_1) in enumerate(drone_list):
            conflicts[drone_id_1] = []

            for drone_id_2, status_2 in drone_list[i + 1 :]:
                # Check if drones are within 100m horizontally and 50m vertically
                horizontal_distance = self._haversine(
                    status_1.lat,
                    status_1.lon,
                    status_2.lat,
                    status_2.lon,
                )
                vertical_distance = abs(status_1.altitude - status_2.altitude)

                if horizontal_distance < 100 and vertical_distance < 50:
                    conflicts[drone_id_1].append(drone_id_2)
                    if drone_id_2 not in conflicts:
                        conflicts[drone_id_2] = []
                    conflicts[drone_id_2].append(drone_id_1)

                    logger.warning(
                        f"⚠️  Potential conflict: {drone_id_1} and {drone_id_2} "
                        f"({horizontal_distance:.1f}m, {vertical_distance:.1f}m)"
                    )

        return conflicts

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        """Calculate distance between two coordinates (meters)."""
        from math import radians, cos, sin, asin, sqrt

        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Radius of earth in meters
        return c * r

    def get_fleet_size(self) -> int:
        """Get number of drones in fleet."""
        return len(self.drones)

    async def shutdown(self):
        """Shutdown coordinator and all drones."""
        logger.info("Shutting down drone coordinator...")
        await self.emergency_stop_all()

        for drone_id, service in self.drones.items():
            try:
                await service.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {drone_id}: {e}")

        self.drones.clear()
        self.locks.clear()
        logger.info("✅ Coordinator shutdown complete")
