"""
Geofence Service - Manages No-Fly Zones and airspace restrictions.

Provides:
- CRUD operations for geofence zones
- Zone activation/deactivation
- Mission pre-flight validation
- Real-time boundary monitoring
"""

import logging
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from src.backend.services.geofence_monitor import GeofenceMonitor
from src.backend.models import NoFlyZone

logger = logging.getLogger(__name__)


class GeofenceService:
    """Service for managing geofence zones."""

    def __init__(self):
        """Initialize geofence service."""
        self.monitor = GeofenceMonitor()
        self._db = None
        self.zones_cache: Dict[str, Dict] = {}

    def set_database(self, session_factory):
        """Set database session factory."""
        self._db = session_factory
        self._load_zones_from_db()

    def _load_zones_from_db(self):
        """Load all active zones from database."""
        if not self._db:
            return

        try:
            session = self._db()
            try:
                zones = session.query(NoFlyZone).filter_by(active=True).all()

                for zone in zones:
                    zone_dict = {
                        "id": str(zone.id),
                        "name": zone.name,
                        "polygon": zone.polygon,
                        "altitude_min": zone.altitude_min,
                        "altitude_max": zone.altitude_max,
                        "active": zone.active,
                    }
                    self.zones_cache[zone.name] = zone_dict
                    self.monitor.register_zone(zone.name, zone_dict)

                logger.info(f"✅ Loaded {len(self.zones_cache)} geofence zones")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Failed to load zones: {e}")

    async def create_zone(self, name: str, polygon: Dict, altitude_min: float = 0.0,
                         altitude_max: Optional[float] = None) -> Dict:
        """Create a new geofence zone."""
        try:
            if name in self.zones_cache:
                return {"success": False, "error": f"Zone {name} already exists"}

            zone_dict = {
                "id": str(uuid.uuid4()),
                "name": name,
                "polygon": polygon,
                "altitude_min": altitude_min,
                "altitude_max": altitude_max,
                "active": True,
            }

            # Save to database
            if self._db:
                session = self._db()
                try:
                    zone = NoFlyZone(
                        name=name,
                        polygon=polygon,
                        altitude_min=altitude_min,
                        altitude_max=altitude_max or float('inf'),
                        active=True,
                    )
                    session.add(zone)
                    session.commit()
                    zone_id = str(zone.id)
                except Exception as e:
                    session.rollback()
                    logger.error(f"Database error: {e}")
                    zone_id = zone_dict["id"]
                finally:
                    session.close()
            else:
                zone_id = zone_dict["id"]

            # Add to cache and monitor
            self.zones_cache[name] = zone_dict
            self.monitor.register_zone(name, zone_dict)

            logger.info(f"✅ Created geofence zone: {name}")
            return {
                "success": True,
                "message": f"Zone {name} created",
                "zone_id": zone_id,
                "zone": zone_dict,
            }

        except Exception as e:
            logger.error(f"Create zone error: {e}")
            return {"success": False, "error": str(e)}

    async def get_zone(self, name: str) -> Dict:
        """Get zone details."""
        try:
            if name not in self.zones_cache:
                return {"success": False, "error": f"Zone {name} not found"}

            return {
                "success": True,
                "zone": self.zones_cache[name],
            }

        except Exception as e:
            logger.error(f"Get zone error: {e}")
            return {"success": False, "error": str(e)}

    async def list_zones(self, active_only: bool = True) -> Dict:
        """List all zones."""
        try:
            zones = [
                z for z in self.zones_cache.values()
                if not active_only or z.get("active", True)
            ]

            return {
                "success": True,
                "count": len(zones),
                "zones": zones,
            }

        except Exception as e:
            logger.error(f"List zones error: {e}")
            return {"success": False, "error": str(e)}

    async def update_zone(self, name: str, polygon: Dict = None, altitude_min: float = None,
                         altitude_max: Optional[float] = None, active: bool = None) -> Dict:
        """Update zone configuration."""
        try:
            if name not in self.zones_cache:
                return {"success": False, "error": f"Zone {name} not found"}

            zone = self.zones_cache[name]

            if polygon is not None:
                zone["polygon"] = polygon
            if altitude_min is not None:
                zone["altitude_min"] = altitude_min
            if altitude_max is not None:
                zone["altitude_max"] = altitude_max
            if active is not None:
                zone["active"] = active

            # Update in database
            if self._db:
                session = self._db()
                try:
                    db_zone = session.query(NoFlyZone).filter_by(name=name).first()
                    if db_zone:
                        if polygon is not None:
                            db_zone.polygon = polygon
                        if altitude_min is not None:
                            db_zone.altitude_min = altitude_min
                        if altitude_max is not None:
                            db_zone.altitude_max = altitude_max or float('inf')
                        if active is not None:
                            db_zone.active = active
                        db_zone.updated_at = datetime.utcnow()
                        session.commit()
                except Exception as e:
                    session.rollback()
                    logger.error(f"Database error: {e}")
                finally:
                    session.close()

            logger.info(f"✅ Updated geofence zone: {name}")
            return {
                "success": True,
                "message": f"Zone {name} updated",
                "zone": zone,
            }

        except Exception as e:
            logger.error(f"Update zone error: {e}")
            return {"success": False, "error": str(e)}

    async def delete_zone(self, name: str) -> Dict:
        """Delete a geofence zone."""
        try:
            if name not in self.zones_cache:
                return {"success": False, "error": f"Zone {name} not found"}

            # Remove from database
            if self._db:
                session = self._db()
                try:
                    db_zone = session.query(NoFlyZone).filter_by(name=name).first()
                    if db_zone:
                        session.delete(db_zone)
                        session.commit()
                except Exception as e:
                    session.rollback()
                    logger.error(f"Database error: {e}")
                finally:
                    session.close()

            del self.zones_cache[name]

            logger.info(f"✅ Deleted geofence zone: {name}")
            return {
                "success": True,
                "message": f"Zone {name} deleted",
            }

        except Exception as e:
            logger.error(f"Delete zone error: {e}")
            return {"success": False, "error": str(e)}

    async def validate_mission(self, waypoints: List[Dict]) -> Dict:
        """Validate mission waypoints against all active zones."""
        try:
            active_zones = [z for z in self.zones_cache.values() if z.get("active", True)]

            if not active_zones:
                return {
                    "success": True,
                    "valid": True,
                    "violation_count": 0,
                    "violations": [],
                }

            result = await self.monitor.validate_mission(waypoints, active_zones)

            return {
                "success": True,
                **result,
            }

        except Exception as e:
            logger.error(f"Mission validation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "valid": False,
                "violations": [],
            }

    async def check_position(self, drone_id: str, position: Dict) -> Dict:
        """Check drone position against all active zones."""
        try:
            active_zones = [z for z in self.zones_cache.values() if z.get("active", True)]

            if not active_zones:
                return {
                    "success": True,
                    "safe": True,
                    "violations": [],
                }

            violations = await self.monitor.monitor_drone(drone_id, position, active_zones)

            return {
                "success": True,
                "safe": len(violations) == 0,
                "violation_count": len(violations),
                "violations": [
                    {
                        "type": v.violation_type,
                        "zone": v.zone_name,
                        "message": v.message,
                        "action": v.action_taken,
                    }
                    for v in violations
                ],
            }

        except Exception as e:
            logger.error(f"Position check error: {e}")
            return {
                "success": False,
                "error": str(e),
                "safe": False,
            }

    async def get_violations(self, zone_name: str, limit: int = 100) -> Dict:
        """Get violation history for a zone."""
        try:
            violations = self.monitor.get_violations(zone_name, limit)

            return {
                "success": True,
                "zone": zone_name,
                "violation_count": len(violations),
                "violations": violations,
            }

        except Exception as e:
            logger.error(f"Get violations error: {e}")
            return {"success": False, "error": str(e)}
