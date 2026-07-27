"""MVP Sprint 1 compliance tests (TZ §2–4)."""

import json
from pathlib import Path

import pytest

from src.autopilot.geofence import GeofenceValidator
from src.mission_plan import waypoints_to_plan
from src.models import TelemetrySnapshot


NFZ_PATH = Path(__file__).resolve().parents[1] / "config" / "nfz_zones.geojson"


class TestGeofenceCompliance:
    """TZ §2.3 — NFZ pre-flight validation."""

    @pytest.fixture
    def validator(self):
        v = GeofenceValidator()
        assert v.load_nfz_zones(str(NFZ_PATH))
        return v

    def test_nfz_zones_load(self, validator):
        assert len(validator.active_zones) >= 1

    def test_safe_mission_passes(self, validator):
        # Route west of Airport NFZ
        waypoints = [
            (47.3950, 8.5300, 50.0),
            (47.3965, 8.5330, 60.0),
            (47.3980, 8.5360, 60.0),
            (47.3950, 8.5300, 0.0),
        ]
        assert validator.validate_mission(waypoints) is True

    def test_mission_through_nfz_blocked(self, validator):
        # Point inside Airport Control Zone
        waypoints = [
            (47.4000, 8.5500, 50.0),
            (47.4010, 8.5510, 50.0),
        ]
        assert validator.validate_mission(waypoints) is False


class TestMissionPlanExport:
    """TZ §3.2 — QGC .plan JSON export."""

    def test_export_plan_format(self):
        waypoints = [
            {"lat": 47.395, "lon": 8.53, "altitude": 50},
            {"lat": 47.396, "lon": 8.535, "altitude": 60},
        ]
        plan = waypoints_to_plan(waypoints)
        assert plan["fileType"] == "Plan"
        assert plan["mission"]["items"]
        assert plan["mission"]["items"][0]["command"] == 16


class TestTelemetryLatency:
    """TZ §2.2 — latency tracking."""

    def test_api_dict_includes_latency(self):
        snap = TelemetrySnapshot(lat=47.0, lon=8.0, latency_ms=12.5)
        data = snap.to_api_dict()
        assert data["latency_ms"] == 12.5
        assert "lat" in data
        assert "battery" in data


class TestNfzGeoJsonFile:
    """TZ §3.1 — NFZ GeoJSON for map."""

    def test_geojson_valid(self):
        with NFZ_PATH.open() as f:
            data = json.load(f)
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 1


class TestSprintExperimentScenario:
    """TZ §4.2 — 4-waypoint mission scenario definition."""

    def test_sprint_waypoints_count(self):
        waypoints = [
            {"lat": 47.3950, "lon": 8.5300, "altitude": 50},
            {"lat": 47.3965, "lon": 8.5330, "altitude": 60},
            {"lat": 47.3980, "lon": 8.5360, "altitude": 60},
            {"lat": 47.3950, "lon": 8.5300, "altitude": 0},
        ]
        assert len(waypoints) == 4

        validator = GeofenceValidator()
        validator.load_nfz_zones(str(NFZ_PATH))
        path = [(w["lat"], w["lon"], w["altitude"]) for w in waypoints]
        assert validator.validate_mission(path)

        plan = waypoints_to_plan(waypoints)
        assert len(plan["mission"]["items"]) == 4
