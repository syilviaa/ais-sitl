"""No-fly-zone loading and validation for local SITL missions."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)

Coordinate = Tuple[float, float]
Waypoint = Tuple[float, float, float]
EPSILON = 1e-10


@dataclass(frozen=True)
class NoFlyZone:
    """An NFZ polygon and the inclusive altitude band it blocks."""

    name: str
    polygon: Tuple[Coordinate, ...]
    min_altitude: float = 0.0
    max_altitude: Optional[float] = None
    active: bool = True

    def applies_at_altitude(self, altitude: float) -> bool:
        """Return whether the zone blocks the supplied altitude."""
        if altitude < self.min_altitude:
            return False
        return self.max_altitude is None or altitude <= self.max_altitude


class GeofenceValidator:
    """Validates points and paths against active GeoJSON no-fly zones."""

    DEFAULT_NFZ_PATH = (
        Path(__file__).resolve().parents[2] / "config" / "nfz_zones.geojson"
    )

    def __init__(self) -> None:
        self.zones: List[NoFlyZone] = []
        self.active_zones: List[NoFlyZone] = []
        self.loaded = False

    def load_nfz_zones(self, filepath: Optional[str] = None) -> bool:
        """Load Polygon GeoJSON features, returning ``False`` on failure."""
        path = (
            Path(filepath) if filepath is not None else self.DEFAULT_NFZ_PATH
        )
        self.zones = []
        self.active_zones = []
        self.loaded = False
        try:
            with path.open(encoding="utf-8") as source:
                features = json.load(source).get("features", [])
            self.zones = [self._parse_zone(feature) for feature in features]
        except (OSError, ValueError, KeyError, TypeError) as error:
            logger.error("Failed to load NFZ zones from %s: %s", path, error)
            return False
        self.active_zones = [zone for zone in self.zones if zone.active]
        self.loaded = True
        logger.info(
            "Loaded %d NFZ zones (%d active)",
            len(self.zones),
            len(self.active_zones),
        )
        return True

    def validate_mission(self, waypoints: Sequence[Waypoint]) -> bool:
        """Return whether every point and segment clears each active NFZ."""
        if not self.loaded or not waypoints:
            return False
        if any(not self._valid_waypoint(point) for point in waypoints):
            return False
        if any(self._point_is_blocked(*point) for point in waypoints):
            return False
        return all(
            self._segment_is_safe(first, second)
            for first, second in zip(waypoints, waypoints[1:])
        )

    def check_point_in_nfz(
        self, lat: float, lon: float, alt: float = 0.0
    ) -> Tuple[bool, str]:
        """Return whether an active NFZ contains or touches this point."""
        if not self.loaded:
            return True, "NFZ data unavailable"
        for zone in self.active_zones:
            if zone.applies_at_altitude(alt) and _point_in_or_on_polygon(
                (lat, lon), zone.polygon
            ):
                return True, zone.name
        return False, ""

    def get_safe_corridor(self) -> List[NoFlyZone]:
        """Return inactive safe-corridor features for compatibility."""
        return [zone for zone in self.zones if not zone.active]

    def _point_is_blocked(
        self, lat: float, lon: float, altitude: float
    ) -> bool:
        return self.check_point_in_nfz(lat, lon, altitude)[0]

    def _segment_is_safe(self, first: Waypoint, second: Waypoint) -> bool:
        start = (first[0], first[1])
        end = (second[0], second[1])
        for zone in self.active_zones:
            for entry, exit_ in _polygon_contact_intervals(
                start, end, zone.polygon
            ):
                altitudes = (
                    _altitude_at(first, second, entry),
                    _altitude_at(first, second, exit_),
                )
                if _altitude_ranges_overlap(
                    min(altitudes), max(altitudes), zone
                ):
                    return False
        return True

    @staticmethod
    def _parse_zone(feature: dict) -> NoFlyZone:
        geometry = feature["geometry"]
        if geometry.get("type") != "Polygon":
            raise ValueError("Only Polygon NFZ features are supported")
        ring = geometry["coordinates"][0]
        if len(ring) < 4:
            raise ValueError("NFZ polygon requires at least three vertices")
        polygon = tuple((float(lat), float(lon)) for lon, lat in ring)
        properties = feature.get("properties", {})
        minimum = float(properties.get("min_altitude", 0.0))
        maximum = properties.get("max_altitude")
        maximum = float(maximum) if maximum is not None else None
        if maximum is not None and maximum < minimum:
            raise ValueError("NFZ maximum altitude is below minimum altitude")
        return NoFlyZone(
            name=str(properties.get("name", "Unnamed NFZ")),
            polygon=polygon,
            min_altitude=minimum,
            max_altitude=maximum,
            active=bool(properties.get("active", True)),
        )

    @staticmethod
    def _valid_waypoint(waypoint: Waypoint) -> bool:
        if not isinstance(waypoint, (tuple, list)):
            return False
        if len(waypoint) != 3:
            return False
        lat, lon, altitude = waypoint
        return (
            _is_number(lat)
            and _is_number(lon)
            and _is_number(altitude)
            and -90.0 <= lat <= 90.0
            and -180.0 <= lon <= 180.0
        )


def _altitude_at(first: Waypoint, second: Waypoint, fraction: float) -> float:
    return first[2] + (second[2] - first[2]) * fraction


def _is_number(value: object) -> bool:
    """Return whether a value is numeric, excluding bool coordinates."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _altitude_ranges_overlap(
    minimum: float, maximum: float, zone: NoFlyZone
) -> bool:
    zone_maximum = (
        float("inf") if zone.max_altitude is None else zone.max_altitude
    )
    return maximum >= zone.min_altitude and minimum <= zone_maximum


def _point_in_or_on_polygon(
    point: Coordinate, polygon: Sequence[Coordinate]
) -> bool:
    """Use ray casting, treating every polygon edge as forbidden."""
    lat, lon = point
    inside = False
    for first, second in _edges(polygon):
        if _point_on_segment(point, first, second):
            return True
        first_lat, first_lon = first
        second_lat, second_lon = second
        crosses_ray = (first_lon > lon) != (second_lon > lon)
        if crosses_ray:
            at_lat = (second_lat - first_lat) * (lon - first_lon)
            at_lat /= second_lon - first_lon
            at_lat += first_lat
            if lat < at_lat:
                inside = not inside
    return inside


def _polygon_contact_intervals(
    start: Coordinate, end: Coordinate, polygon: Sequence[Coordinate]
) -> Iterable[Tuple[float, float]]:
    """Yield all segment fractions that are in or touch a polygon."""
    fractions = {0.0, 1.0}
    for edge_start, edge_end in _edges(polygon):
        fractions.update(
            _segment_intersection_fractions(start, end, edge_start, edge_end)
        )
    ordered = sorted(
        fraction for fraction in fractions if 0.0 <= fraction <= 1.0
    )
    for fraction in ordered:
        if _point_in_or_on_polygon(
            _interpolate(start, end, fraction), polygon
        ):
            yield fraction, fraction
    for first, second in zip(ordered, ordered[1:]):
        midpoint = (first + second) / 2.0
        if _point_in_or_on_polygon(
            _interpolate(start, end, midpoint), polygon
        ):
            yield first, second


def _segment_intersection_fractions(
    start: Coordinate,
    end: Coordinate,
    edge_start: Coordinate,
    edge_end: Coordinate,
) -> Iterable[float]:
    """Return fractions along ``start`` → ``end`` intersecting one edge."""
    direction = _subtract(end, start)
    edge = _subtract(edge_end, edge_start)
    origin_delta = _subtract(edge_start, start)
    denominator = _cross(direction, edge)
    if abs(denominator) > EPSILON:
        fraction = _cross(origin_delta, edge) / denominator
        edge_fraction = _cross(origin_delta, direction) / denominator
        if -EPSILON <= fraction <= 1.0 + EPSILON and (
            -EPSILON <= edge_fraction <= 1.0 + EPSILON
        ):
            yield min(1.0, max(0.0, fraction))
        return
    if abs(_cross(origin_delta, direction)) <= EPSILON:
        squared_length = _dot(direction, direction)
        if squared_length <= EPSILON:
            return
        for point in (edge_start, edge_end):
            fraction = (
                _dot(_subtract(point, start), direction) / squared_length
            )
            if -EPSILON <= fraction <= 1.0 + EPSILON:
                yield min(1.0, max(0.0, fraction))


def _edges(
    polygon: Sequence[Coordinate],
) -> Iterable[Tuple[Coordinate, Coordinate]]:
    return zip(polygon, polygon[1:] + polygon[:1])


def _point_on_segment(
    point: Coordinate, start: Coordinate, end: Coordinate
) -> bool:
    if abs(_cross(_subtract(point, start), _subtract(end, start))) > EPSILON:
        return False
    return (
        min(start[0], end[0]) - EPSILON
        <= point[0]
        <= max(start[0], end[0]) + EPSILON
        and min(start[1], end[1]) - EPSILON
        <= point[1]
        <= max(start[1], end[1]) + EPSILON
    )


def _interpolate(
    start: Coordinate, end: Coordinate, fraction: float
) -> Coordinate:
    return (
        start[0] + (end[0] - start[0]) * fraction,
        start[1] + (end[1] - start[1]) * fraction,
    )


def _subtract(first: Coordinate, second: Coordinate) -> Coordinate:
    return first[0] - second[0], first[1] - second[1]


def _cross(first: Coordinate, second: Coordinate) -> float:
    return first[0] * second[1] - first[1] * second[0]


def _dot(first: Coordinate, second: Coordinate) -> float:
    return first[0] * second[0] + first[1] * second[1]
