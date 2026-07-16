"""
Unit tests for geofencing validation.

Tests polygon intersection, mission validation, and runtime NFZ breach detection.
"""

import pytest
import json
from shapely.geometry import Point, Polygon, LineString


class GeofenceValidator:
    """Geofence validation for No-Fly Zones."""

    def __init__(self):
        self.zones = []

    def load_nfz_zones(self, filepath: str):
        """Load GeoJSON NFZ zones."""
        with open(filepath) as f:
            data = json.load(f)
            self.zones = data.get("features", [])

    def validate_mission(self, waypoints: list) -> bool:
        """Check if mission waypoints cross any NFZ."""
        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]

            for zone in self.zones:
                if not zone["properties"].get("active", True):
                    continue

                coords = zone["geometry"]["coordinates"][0]
                poly = Polygon(coords)

                # Check segment intersection
                segment = LineString([(wp1[1], wp1[0]), (wp2[1], wp2[0])])
                if poly.intersects(segment):
                    return False

        return True

    def check_point_in_nfz(self, lat: float, lon: float) -> bool:
        """Check if single point is in NFZ."""
        for zone in self.zones:
            if not zone["properties"].get("active", True):
                continue

            coords = zone["geometry"]["coordinates"][0]
            poly = Polygon(coords)
            point = Point(lon, lat)

            if poly.contains(point):
                return True

        return False


# Tests

def test_geofence_load_zones():
    """Test loading GeoJSON zones."""
    validator = GeofenceValidator()
    validator.load_nfz_zones("config/nfz_zones.geojson")
    assert len(validator.zones) > 0


def test_geofence_point_in_zone():
    """Test point-in-zone detection."""
    validator = GeofenceValidator()
    validator.load_nfz_zones("config/nfz_zones.geojson")

    # Point inside first zone (Zurich Airport)
    assert validator.check_point_in_nfz(47.3990, 8.5520) == True

    # Point outside all zones
    assert validator.check_point_in_nfz(47.0000, 8.0000) == False


def test_geofence_mission_valid():
    """Test valid mission (avoids NFZ)."""
    validator = GeofenceValidator()
    validator.load_nfz_zones("config/nfz_zones.geojson")

    # Mission far from zones
    waypoints = [
        (47.2000, 8.0000, 50.0),
        (47.2100, 8.0100, 50.0),
        (47.2200, 8.0200, 50.0),
    ]

    assert validator.validate_mission(waypoints) == True


def test_geofence_mission_crosses_nfz():
    """Test mission that crosses NFZ."""
    validator = GeofenceValidator()
    validator.load_nfz_zones("config/nfz_zones.geojson")

    # Mission passes through Zurich Airport zone
    waypoints = [
        (47.3800, 8.5400, 50.0),
        (47.4100, 8.5700, 50.0),  # Crosses zone
    ]

    assert validator.validate_mission(waypoints) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
