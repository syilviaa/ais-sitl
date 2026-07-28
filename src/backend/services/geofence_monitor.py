"""
Geofence Monitor - Real-time airspace boundary enforcement.

Provides:
- Polygon boundary violation detection
- Altitude ceiling enforcement
- Automatic RTL on geofence breach
- No-Fly Zone (NFZ) pre-flight validation
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GeofenceViolation:
    """Represents a geofence boundary violation."""

    violation_type: str  # "boundary", "altitude", "return_home"
    drone_id: str
    zone_name: str
    timestamp: float
    position: Tuple[float, float, float]  # lat, lon, alt
    action_taken: str  # "hold", "rtl", "land"
    message: str


class GeofenceMonitor:
    """Monitors drone positions against geofence boundaries."""

    def __init__(self):
        """Initialize geofence monitor."""
        self.violations: Dict[str, List[GeofenceViolation]] = {}
        self.violation_callbacks: Dict[str, callable] = {}
        self.is_monitoring = False

    def register_zone(self, zone_name: str, zone_config: Dict):
        """Register a geofence zone for monitoring."""
        if zone_name not in self.violations:
            self.violations[zone_name] = []
        logger.info(f"✅ Registered geofence zone: {zone_name}")

    async def check_position(self, drone_id: str, position: Dict, zone: Dict) -> Optional[GeofenceViolation]:
        """Check if drone position violates geofence boundaries."""
        try:
            lat = position.get("lat", 0)
            lon = position.get("lon", 0)
            alt = position.get("altitude", 0)

            # Check altitude ceiling
            min_alt = zone.get("altitude_min", 0)
            max_alt = zone.get("altitude_max", float('inf'))

            if alt < min_alt:
                violation = GeofenceViolation(
                    violation_type="altitude",
                    drone_id=drone_id,
                    zone_name=zone.get("name", "unknown"),
                    timestamp=datetime.utcnow().timestamp(),
                    position=(lat, lon, alt),
                    action_taken="hold",
                    message=f"Below minimum altitude ({alt}m < {min_alt}m)",
                )
                return violation

            if max_alt is not None and alt > max_alt:
                violation = GeofenceViolation(
                    violation_type="altitude",
                    drone_id=drone_id,
                    zone_name=zone.get("name", "unknown"),
                    timestamp=datetime.utcnow().timestamp(),
                    position=(lat, lon, alt),
                    action_taken="hold",
                    message=f"Above maximum altitude ({alt}m > {max_alt}m)",
                )
                return violation

            # Check polygon boundary (simplified: point-in-polygon check)
            polygon = zone.get("polygon", {})
            coordinates = polygon.get("coordinates", [[]])

            if coordinates and not self._point_in_polygon((lat, lon), coordinates[0]):
                violation = GeofenceViolation(
                    violation_type="boundary",
                    drone_id=drone_id,
                    zone_name=zone.get("name", "unknown"),
                    timestamp=datetime.utcnow().timestamp(),
                    position=(lat, lon, alt),
                    action_taken="rtl",
                    message=f"Outside geofence boundary ({lat}, {lon})",
                )
                return violation

            return None

        except Exception as e:
            logger.error(f"Geofence check error: {e}")
            return None

    async def monitor_drone(self, drone_id: str, position: Dict, zones: List[Dict]) -> List[GeofenceViolation]:
        """Monitor drone against all active zones."""
        violations = []

        for zone in zones:
            if not zone.get("active", True):
                continue

            violation = await self.check_position(drone_id, position, zone)

            if violation:
                violations.append(violation)
                await self._handle_violation(violation)

        return violations

    async def validate_mission(self, waypoints: List[Dict], zones: List[Dict]) -> Dict:
        """Validate mission waypoints against geofence zones."""
        violations = []

        for i, wp in enumerate(waypoints):
            lat = wp.get("lat", 0)
            lon = wp.get("lon", 0)
            alt = wp.get("altitude", 0)

            position = {"lat": lat, "lon": lon, "altitude": alt}

            for zone in zones:
                if not zone.get("active", True):
                    continue

                violation = await self.check_position(f"mission-wp-{i}", position, zone)

                if violation:
                    violations.append({
                        "waypoint_index": i,
                        "waypoint": wp,
                        "zone": zone.get("name", "unknown"),
                        "violation_type": violation.violation_type,
                        "message": violation.message,
                    })

        return {
            "valid": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }

    async def _handle_violation(self, violation: GeofenceViolation):
        """Handle a geofence violation."""
        logger.warning(f"🚨 Geofence violation: {violation.drone_id} - {violation.message}")

        # Trigger callback if registered
        callback_key = f"{violation.drone_id}_{violation.zone_name}"
        if callback_key in self.violation_callbacks:
            try:
                await self.violation_callbacks[callback_key](violation)
            except Exception as e:
                logger.error(f"Violation callback error: {e}")

    def register_violation_callback(self, drone_id: str, zone_name: str, callback: callable):
        """Register a callback for geofence violations."""
        callback_key = f"{drone_id}_{zone_name}"
        self.violation_callbacks[callback_key] = callback
        logger.info(f"Registered violation callback for {drone_id} in {zone_name}")

    @staticmethod
    def _point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
        """Check if point is inside polygon using ray casting algorithm."""
        x, y = point
        n = len(polygon)
        inside = False

        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def get_violations(self, zone_name: str, limit: int = 100) -> List[Dict]:
        """Get violation history for a zone."""
        if zone_name not in self.violations:
            return []

        violations = self.violations[zone_name][-limit:]
        return [
            {
                "violation_type": v.violation_type,
                "drone_id": v.drone_id,
                "timestamp": v.timestamp,
                "position": {"lat": v.position[0], "lon": v.position[1], "alt": v.position[2]},
                "action_taken": v.action_taken,
                "message": v.message,
            }
            for v in violations
        ]

    def clear_violations(self, zone_name: str):
        """Clear violation history for a zone."""
        if zone_name in self.violations:
            self.violations[zone_name] = []
            logger.info(f"Cleared violation history for {zone_name}")
