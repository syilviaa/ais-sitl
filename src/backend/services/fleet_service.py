"""
Fleet Service - Multi-drone management and coordination.

Provides:
- Drone registry management (add/remove drones)
- Coordinated flight operations (takeoff, land, RTL)
- Airspace conflict detection
- Fleet-wide status aggregation
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from src.backend.services.drone_service import DroneService
from src.backend.services.drone_coordinator import DroneCoordinator
from src.backend.database import SessionLocal
from src.backend.models import Drone

logger = logging.getLogger(__name__)


class FleetService:
    """Service for managing drone fleet operations."""

    def __init__(self):
        """Initialize fleet service."""
        self.coordinator = DroneCoordinator()
        self.services: Dict[str, DroneService] = {}
        self._db = None

    def set_database(self, session_factory):
        """Set database session factory."""
        self._db = session_factory

    async def add_drone(self, name: str, host: str, port: int) -> Dict:
        """Register a new drone in the fleet."""
        try:
            # Check if drone already exists
            if name in self.services:
                return {"success": False, "error": f"Drone {name} already registered"}

            # Create service
            service = DroneService(host=host, port=port)

            # Register in coordinator
            await self.coordinator.add_drone(name, service)
            self.services[name] = service

            # Save to database
            if self._db:
                session = self._db()
                try:
                    drone = Drone(
                        name=name,
                        host=host,
                        port=port,
                        status="disconnected"
                    )
                    session.add(drone)
                    session.commit()
                    drone_id = str(drone.id)
                except Exception as e:
                    session.rollback()
                    logger.error(f"Database error: {e}")
                    drone_id = None
                finally:
                    session.close()
            else:
                drone_id = None

            logger.info(f"✅ Drone {name} added to fleet")
            return {
                "success": True,
                "message": f"Drone {name} registered",
                "drone_id": drone_id,
                "name": name,
                "host": host,
                "port": port,
            }

        except Exception as e:
            logger.error(f"Add drone error: {e}")
            return {"success": False, "error": str(e)}

    async def remove_drone(self, drone_id: str) -> Dict:
        """Remove drone from fleet."""
        try:
            # Find drone by ID or name
            service = None
            drone_name = None

            if drone_id in self.services:
                drone_name = drone_id
                service = self.services[drone_id]
            else:
                # Search by DB ID
                if self._db:
                    session = self._db()
                    try:
                        db_drone = session.query(Drone).filter_by(id=drone_id).first()
                        if db_drone:
                            drone_name = db_drone.name
                            service = self.services.get(drone_name)
                    finally:
                        session.close()

            if not service or not drone_name:
                return {"success": False, "error": f"Drone {drone_id} not found"}

            # Disconnect
            await service.disconnect()

            # Remove from coordinator
            await self.coordinator.remove_drone(drone_name)
            del self.services[drone_name]

            # Update database
            if self._db:
                session = self._db()
                try:
                    db_drone = session.query(Drone).filter_by(name=drone_name).first()
                    if db_drone:
                        db_drone.status = "disconnected"
                        session.commit()
                finally:
                    session.close()

            logger.info(f"✅ Drone {drone_name} removed from fleet")
            return {
                "success": True,
                "message": f"Drone {drone_name} removed",
                "drone_id": drone_id,
            }

        except Exception as e:
            logger.error(f"Remove drone error: {e}")
            return {"success": False, "error": str(e)}

    async def get_fleet_status(self) -> Dict:
        """Get status of all drones in fleet."""
        try:
            statuses = await self.coordinator.get_fleet_status()

            return {
                "success": True,
                "fleet_size": len(statuses),
                "drones": {
                    drone_id: {
                        "name": status.name,
                        "connected": status.connected,
                        "state": status.state,
                        "battery_percent": status.battery_percent,
                        "position": {
                            "lat": status.lat,
                            "lon": status.lon,
                            "altitude": status.altitude,
                        },
                        "last_update": status.last_update,
                    }
                    for drone_id, status in statuses.items()
                }
            }

        except Exception as e:
            logger.error(f"Fleet status error: {e}")
            return {"success": False, "error": str(e), "fleet_size": 0, "drones": {}}

    async def check_conflicts(self) -> Dict:
        """Check for airspace conflicts."""
        try:
            conflicts = await self.coordinator.check_airspace_conflicts()

            return {
                "success": True,
                "conflict_count": sum(len(v) for v in conflicts.values()),
                "conflicts": conflicts,
            }

        except Exception as e:
            logger.error(f"Conflict check error: {e}")
            return {"success": False, "error": str(e), "conflicts": {}}

    async def coordinated_takeoff(self, drone_names: List[str], altitude: float, delay: float = 1.0) -> Dict:
        """Execute coordinated takeoff."""
        try:
            await self.coordinator.coordinated_takeoff(drone_names, altitude, delay)

            return {
                "success": True,
                "message": f"Coordinated takeoff initiated for {len(drone_names)} drones",
                "drones": drone_names,
                "altitude": altitude,
                "delay": delay,
            }

        except Exception as e:
            logger.error(f"Coordinated takeoff error: {e}")
            return {"success": False, "error": str(e)}

    async def broadcast_command(self, command: str, data: Dict = None) -> Dict:
        """Broadcast command to all drones."""
        try:
            results = await self.coordinator.broadcast_command(command, data)

            return {
                "success": True,
                "command": command,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Broadcast command error: {e}")
            return {"success": False, "error": str(e)}

    async def emergency_stop(self) -> Dict:
        """Emergency stop all drones."""
        try:
            await self.coordinator.emergency_stop_all()

            return {
                "success": True,
                "message": "Emergency stop initiated for all drones",
            }

        except Exception as e:
            logger.error(f"Emergency stop error: {e}")
            return {"success": False, "error": str(e)}

    async def shutdown(self):
        """Shutdown fleet service."""
        try:
            await self.coordinator.shutdown()
            logger.info("✅ Fleet service shutdown complete")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")

    def get_fleet_size(self) -> int:
        """Get number of drones in fleet."""
        return len(self.services)
