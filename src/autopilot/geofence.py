"""
Geofencing validation for No-Fly Zones.

Loads GeoJSON NFZ zones and validates missions/positions against them.
Uses Shapely for polygon intersection detection.

Status: [VEHA 3] Implementation begins July 23, 2026
"""

import json
import logging
from typing import List, Tuple
from shapely.geometry import Point, Polygon, LineString


logger = logging.getLogger(__name__)


class GeofenceValidator:
    """Validates missions and positions against No-Fly Zones."""

    def __init__(self):
        self.zones = []
        self.active_zones = []

    def load_nfz_zones(self, filepath: str) -> bool:
        """
        Load No-Fly Zone definitions from GeoJSON file.

        Args:
            filepath: Path to GeoJSON file

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(filepath) as f:
                data = json.load(f)
                self.zones = data.get("features", [])
                self.active_zones = [z for z in self.zones if z["properties"].get("active", True)]
                logger.info(f"Loaded {len(self.zones)} zones ({len(self.active_zones)} active)")
                return True
        except Exception as e:
            logger.error(f"Failed to load NFZ zones: {e}")
            return False

    def validate_mission(self, waypoints: List[Tuple[float, float, float]]) -> bool:
        """
        Validate mission waypoints against NFZ.

        Checks each segment of the mission path for intersection with active NFZ polygons.

        Args:
            waypoints: List of (lat, lon, altitude) tuples

        Returns:
            True if mission valid (no NFZ crossing), False otherwise
        """
        if len(waypoints) < 2:
            return False

        logger.debug(f"Validating mission with {len(waypoints)} waypoints...")

        # Check each segment between consecutive waypoints
        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]

            if not self._validate_segment(wp1, wp2):
                logger.warning(f"Segment {i}-{i+1} crosses NFZ")
                return False

        logger.info("Mission validation passed")
        return True

    def _validate_segment(self, wp1: Tuple[float, float, float], wp2: Tuple[float, float, float]) -> bool:
        """Check if segment between two waypoints crosses any NFZ."""
        lat1, lon1, alt1 = wp1
        lat2, lon2, alt2 = wp2

        # Convert to (lon, lat) for Shapely (which expects (x, y))
        segment = LineString([(lon1, lat1), (lon2, lat2)])

        for zone in self.active_zones:
            try:
                coords = zone["geometry"]["coordinates"][0]
                poly = Polygon(coords)

                if poly.intersects(segment):
                    zone_name = zone["properties"].get("name", "Unknown")
                    logger.warning(f"Segment intersects NFZ: {zone_name}")
                    return False
            except Exception as e:
                logger.error(f"Error checking zone: {e}")

        return True

    def check_point_in_nfz(self, lat: float, lon: float, alt: float = 0.0) -> Tuple[bool, str]:
        """
        Check if a single point is inside any NFZ.

        Args:
            lat: Latitude (degrees)
            lon: Longitude (degrees)
            alt: Altitude (meters) — optional altitude-based checks

        Returns:
            Tuple of (in_nfz: bool, zone_name: str or empty)
        """
        point = Point(lon, lat)

        for zone in self.active_zones:
            try:
                coords = zone["geometry"]["coordinates"][0]
                poly = Polygon(coords)

                # Check altitude constraints if defined
                max_alt = zone["properties"].get("max_altitude")
                min_alt = zone["properties"].get("min_altitude", 0.0)

                if max_alt and alt > max_alt:
                    continue  # Above zone altitude

                if alt < min_alt:
                    continue  # Below zone altitude

                if poly.contains(point):
                    zone_name = zone["properties"].get("name", "Unknown")
                    logger.warning(f"Point in NFZ: {zone_name}")
                    return (True, zone_name)
            except Exception as e:
                logger.error(f"Error checking zone: {e}")

        return (False, "")

    def get_buffer_zone(self, buffer_distance: float = 10.0) -> List[Polygon]:
        """
        Get buffered zones (expanded by buffer distance).

        Useful for creating safety margins around NFZ.

        Args:
            buffer_distance: Buffer distance in meters

        Returns:
            List of buffered Polygon objects
        """
        buffered = []
        for zone in self.active_zones:
            try:
                coords = zone["geometry"]["coordinates"][0]
                poly = Polygon(coords)
                buffered_poly = poly.buffer(buffer_distance / 111000)  # Convert m to degrees (approx)
                buffered.append(buffered_poly)
            except Exception as e:
                logger.error(f"Error buffering zone: {e}")

        return buffered

    def get_safe_corridor(self) -> List[Polygon]:
        """
        Get designated safe flight zones from GeoJSON.

        Returns:
            List of safe corridor Polygons
        """
        safe_zones = []
        for zone in self.zones:
            if zone["properties"].get("type") == "safe_zone":
                try:
                    coords = zone["geometry"]["coordinates"][0]
                    safe_zones.append(Polygon(coords))
                except Exception as e:
                    logger.error(f"Error parsing safe zone: {e}")

        return safe_zones
