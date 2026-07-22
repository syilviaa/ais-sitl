"""Tests for the production GeoJSON no-fly-zone validator."""

import json

import pytest

from src.autopilot.geofence import GeofenceValidator, NoFlyZone


@pytest.fixture
def validator():
    instance = GeofenceValidator()
    assert instance.load_nfz_zones()
    return instance


def test_loads_geojson_zones(validator):
    """The project GeoJSON is parsed into named NoFlyZone objects."""
    assert validator.loaded
    assert all(isinstance(zone, NoFlyZone) for zone in validator.zones)
    assert len(validator.zones) == 3
    assert len(validator.active_zones) == 2


def test_point_inside_active_zone_is_blocked(validator):
    blocked, name = validator.check_point_in_nfz(47.3990, 8.5520, 50.0)
    assert blocked
    assert name == "Airport Control Zone"


def test_point_on_active_zone_boundary_is_blocked(validator):
    blocked, name = validator.check_point_in_nfz(47.3977, 8.5520, 50.0)
    assert blocked
    assert name == "Airport Control Zone"


def test_safe_route_is_allowed(validator):
    mission = [(47.2000, 8.0000, 50.0), (47.2200, 8.0200, 50.0)]
    assert validator.validate_mission(mission)


def test_route_crossing_active_nfz_is_blocked(validator):
    mission = [(47.3800, 8.5400, 50.0), (47.4100, 8.5700, 50.0)]
    assert not validator.validate_mission(mission)


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
    assert not validator.validate_mission([(47.3990, 8.5520, 50.0)])


def test_altitude_band_is_respected(validator):
    assert not validator.check_point_in_nfz(47.3990, 8.5520, 151.0)[0]
    assert validator.check_point_in_nfz(47.3990, 8.5520, 150.0)[0]


def test_failed_load_blocks_validation(tmp_path):
    validator = GeofenceValidator()
    assert not validator.load_nfz_zones(str(tmp_path / "missing.geojson"))
    assert not validator.validate_mission([(47.2, 8.0, 50.0)])


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
                                    [8.0, 47.0],
                                    [8.1, 47.0],
                                    [8.1, 47.1],
                                    [8.0, 47.1],
                                    [8.0, 47.0],
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
    assert validator.validate_mission([(47.05, 8.05, 20.0)])
