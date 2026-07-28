"""Tests for the production GeoJSON no-fly-zone validator (Astana Training Field)."""

import json

import pytest

from src.autopilot.geofence import GeofenceValidator, NoFlyZone

# Astana NFZ A: lat 51.170–51.173, lon 71.452–71.456, max_alt 200 m
NFZ_INTERIOR = (51.1715, 71.4540, 50.0)
NFZ_BOUNDARY = (51.1700, 71.4520, 50.0)
SAFE_MISSION = [
    (51.1680, 71.4460, 50.0),
    (51.1690, 71.4480, 50.0),
]
CROSSING_MISSION = [
    (51.1680, 71.4460, 50.0),
    (51.1720, 71.4540, 50.0),
]


@pytest.fixture
def validator():
    instance = GeofenceValidator()
    assert instance.load_nfz_zones()
    return instance


def test_loads_geojson_zones(validator):
    """The project GeoJSON is parsed into named NoFlyZone objects."""
    assert validator.loaded
    assert all(isinstance(zone, NoFlyZone) for zone in validator.zones)
    assert len(validator.zones) == 2
    assert len(validator.active_zones) == 1


def test_point_inside_active_zone_is_blocked(validator):
    blocked, name = validator.check_point_in_nfz(*NFZ_INTERIOR)
    assert blocked
    assert "NFZ" in name or "Учебная" in name


def test_point_on_active_zone_boundary_is_blocked(validator):
    blocked, _name = validator.check_point_in_nfz(*NFZ_BOUNDARY)
    assert blocked


def test_safe_route_is_allowed(validator):
    assert validator.validate_mission(SAFE_MISSION)


def test_route_crossing_active_nfz_is_blocked(validator):
    assert not validator.validate_mission(CROSSING_MISSION)


def test_empty_mission_is_rejected(validator):
    assert not validator.validate_mission([])


@pytest.mark.parametrize(
    "mission",
    [
        [None],
        [(True, 8.5, 50.0)],
        ["not-a-waypoint"],
    ],
)
def test_invalid_waypoint_is_rejected_without_exception(validator, mission):
    assert not validator.validate_mission(mission)


def test_one_dangerous_waypoint_is_rejected(validator):
    assert not validator.validate_mission([NFZ_INTERIOR])


def test_altitude_band_is_respected(validator):
    lat, lon, _ = NFZ_INTERIOR
    assert not validator.check_point_in_nfz(lat, lon, 201.0)[0]
    assert validator.check_point_in_nfz(lat, lon, 200.0)[0]


def test_failed_load_blocks_validation(tmp_path):
    validator = GeofenceValidator()
    assert not validator.load_nfz_zones(str(tmp_path / "missing.geojson"))
    assert not validator.validate_mission(SAFE_MISSION)


def test_custom_inactive_zone_does_not_block(tmp_path):
    path = tmp_path / "zones.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "disabled", "active": False},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [71.44, 51.167],
                                    [71.45, 51.167],
                                    [71.45, 51.168],
                                    [71.44, 51.168],
                                    [71.44, 51.167],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    validator = GeofenceValidator()
    assert validator.load_nfz_zones(str(path))
    assert validator.validate_mission([(51.1675, 71.445, 20.0)])
