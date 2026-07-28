"""QGroundControl-compatible .plan mission export (MVP Sprint 1)."""

from typing import List, Dict, Any


def waypoints_to_plan(waypoints: List[Dict[str, Any]], name: str = "AIS Mission") -> Dict[str, Any]:
    """Convert dashboard waypoints to QGC Plan file JSON."""
    items = [
        {
            "AMSLAltAboveTerrain": None,
            "Altitude": wp.get("altitude", 50.0),
            "AltitudeMode": 1,
            "autoContinue": True,
            "command": 16,
            "doJumpId": idx + 1,
            "frame": 3,
            "params": [0, 0, 0, None, wp["lat"], wp["lon"], wp.get("altitude", 50.0)],
            "type": "SimpleItem",
        }
        for idx, wp in enumerate(waypoints)
    ]

    return {
        "fileType": "Plan",
        "geoFence": {"circles": [], "polygons": [], "version": 2},
        "groundStation": "AIS SITL Dashboard",
        "mission": {
            "cruiseSpeed": 5,
            "firmwareType": 12,
            "globalPlanAltitudeMode": 1,
            "hoverSpeed": 5,
            "items": items,
            "plannedHomePosition": [
                waypoints[0]["lat"],
                waypoints[0]["lon"],
                waypoints[0].get("altitude", 50.0),
            ] if waypoints else [47.3977, 8.5300, 0],
            "vehicleType": 2,
            "version": 2,
        },
        "rallyPoints": {"points": [], "version": 2},
        "version": 1,
        "name": name,
    }
