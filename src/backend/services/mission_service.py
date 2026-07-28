"""
Mission Service - Wrapper around MissionService for REST API.

Provides:
- Mission upload and validation
- Mission execution control
- Progress tracking
- Mission history
"""

import logging
from typing import Optional, List, Dict, Any

from src.mission import MissionService
from src.models import Waypoint, MissionProgress
from src.autopilot.geofence import GeofenceValidator
from src.mission_plan import waypoints_to_plan

logger = logging.getLogger(__name__)

_geofence_validator = GeofenceValidator()


def _readable_upload_error(detail: Optional[str]) -> tuple[str, Optional[str]]:
    """Turn raw MAVSDK/gRPC failures into a message plus a machine-readable type."""
    if not detail:
        return "Upload failed", None
    if "UNAVAILABLE" in detail or "Connection refused" in detail:
        return (
            "Связь с MAVSDK потеряна (mavsdk_server недоступен). "
            "Нажмите «Подключить SITL» и повторите загрузку.",
            "link_lost",
        )
    if "DENIED" in detail.upper():
        return (
            "PX4 отклонил миссию. Переведите дрон в Hold/на землю "
            "и повторите загрузку.",
            "rejected",
        )
    return detail, None


class MissionServiceAPI:
    """Service layer for mission operations."""

    def __init__(self, mavsdk_system=None):
        """Initialize mission service."""
        self.service = MissionService(system=mavsdk_system)
        self.mission_history: List[Dict[str, Any]] = []
        self.current_mission_id: Optional[str] = None

    async def validate_mission(self, waypoints: List[Dict[str, float]]) -> Dict[str, Any]:
        """Validate mission waypoints."""
        try:
            logger.info(f"Validating {len(waypoints)} waypoints...")

            # Convert dicts to Waypoint objects
            wp_objects = []
            for i, wp in enumerate(waypoints):
                try:
                    waypoint = Waypoint(
                        lat=wp["lat"],
                        lon=wp["lon"],
                        altitude_m=wp.get("altitude", wp.get("alt", 50.0)),
                        speed_m_s=wp.get("speed", 5.0),
                        wait_time_s=wp.get("wait_time", 0.0),
                        gimbal_pitch_deg=wp.get("gimbal_pitch", 0.0),
                        gimbal_yaw_deg=wp.get("gimbal_yaw", 0.0),
                        take_photo=wp.get("take_photo", False),
                    )
                    wp_objects.append(waypoint)
                except KeyError as e:
                    return {
                        "valid": False,
                        "error": f"Waypoint {i}: missing field {e}",
                    }

            # Validate coordinates
            for i, wp in enumerate(wp_objects):
                if not (-90 <= wp.lat <= 90):
                    return {
                        "valid": False,
                        "error": f"Waypoint {i}: invalid latitude {wp.lat}",
                    }
                if not (-180 <= wp.lon <= 180):
                    return {
                        "valid": False,
                        "error": f"Waypoint {i}: invalid longitude {wp.lon}",
                    }
                if not (0 <= wp.altitude_m <= 10000):
                    return {
                        "valid": False,
                        "error": f"Waypoint {i}: altitude {wp.altitude_m} out of range",
                    }
                if not (0 <= wp.speed_m_s <= 30):
                    return {
                        "valid": False,
                        "error": f"Waypoint {i}: speed {wp.speed_m_s} out of range",
                    }

            # NFZ pre-flight validation (TZ §2.3)
            if not _geofence_validator.loaded:
                _geofence_validator.load_nfz_zones()
            nfz_path = [
                (wp.lat, wp.lon, wp.altitude_m) for wp in wp_objects
            ]
            if _geofence_validator.loaded and not _geofence_validator.validate_mission(nfz_path):
                return {
                    "valid": False,
                    "error": "Mission path intersects a No-Fly Zone (NFZ)",
                    "nfz_blocked": True,
                }

            logger.info("✅ Mission validation passed")
            return {
                "valid": True,
                "waypoints_count": len(wp_objects),
                "error": None,
            }

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                "valid": False,
                "error": str(e),
            }

    async def upload_mission(
        self, waypoints: List[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Upload mission to drone."""
        try:
            logger.info(f"Uploading mission with {len(waypoints)} waypoints...")

            # Validate first
            validation = await self.validate_mission(waypoints)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": validation["error"],
                    "mission_id": None,
                }

            # Convert to Waypoint objects
            wp_objects = [
                Waypoint(
                    lat=wp["lat"],
                    lon=wp["lon"],
                    altitude_m=wp.get("altitude", wp.get("alt", 50.0)),
                    speed_m_s=wp.get("speed", 5.0),
                    wait_time_s=wp.get("wait_time", 0.0),
                )
                for wp in waypoints
            ]

            # Upload
            success = await self.service.upload_mission(wp_objects)

            if success:
                # Generate mission ID
                import uuid
                mission_id = str(uuid.uuid4())[:8]
                self.current_mission_id = mission_id

                # Record in history
                self.mission_history.append({
                    "mission_id": mission_id,
                    "waypoints": len(wp_objects),
                    "status": "uploaded",
                })

                logger.info(f"✅ Mission uploaded (ID: {mission_id})")
                return {
                    "success": True,
                    "mission_id": mission_id,
                    "waypoints": len(wp_objects),
                    "error": None,
                }
            else:
                detail = getattr(self.service, "_last_upload_error", None)
                message, error_type = _readable_upload_error(detail)
                return {
                    "success": False,
                    "error": message,
                    "error_type": error_type,
                    "mission_id": None,
                }

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return {
                "success": False,
                "error": str(e),
                "mission_id": None,
            }

    async def start_mission(self) -> Dict[str, Any]:
        """Start mission execution."""
        try:
            logger.info("Starting mission...")
            await self.service.start_mission()

            if self.current_mission_id:
                for m in self.mission_history:
                    if m["mission_id"] == self.current_mission_id:
                        m["status"] = "running"

            logger.info("✅ Mission started")
            return {
                "success": True,
                "mission_id": self.current_mission_id,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Start error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def pause_mission(self) -> Dict[str, Any]:
        """Pause mission."""
        try:
            logger.info("Pausing mission...")
            await self.service.pause_mission()

            if self.current_mission_id:
                for m in self.mission_history:
                    if m["mission_id"] == self.current_mission_id:
                        m["status"] = "paused"

            logger.info("✅ Mission paused")
            return {
                "success": True,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Pause error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def resume_mission(self) -> Dict[str, Any]:
        """Resume mission."""
        try:
            logger.info("Resuming mission...")
            await self.service.resume_mission()

            if self.current_mission_id:
                for m in self.mission_history:
                    if m["mission_id"] == self.current_mission_id:
                        m["status"] = "running"

            logger.info("✅ Mission resumed")
            return {
                "success": True,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Resume error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def abort_mission(self) -> Dict[str, Any]:
        """Abort mission."""
        try:
            logger.info("Aborting mission...")
            await self.service.abort_mission()

            if self.current_mission_id:
                for m in self.mission_history:
                    if m["mission_id"] == self.current_mission_id:
                        m["status"] = "aborted"

            logger.info("✅ Mission aborted")
            return {
                "success": True,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Abort error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_progress(self) -> Dict[str, Any]:
        """Get mission progress."""
        try:
            progress = await self.service.get_progress()
            if progress:
                return {
                    "current": progress.current_waypoint,
                    "total": progress.total_waypoints,
                    "percent": progress.percent_complete,
                    "finished": progress.is_mission_finished,
                    "mission_id": self.current_mission_id,
                }
            total = len(getattr(self.service, "_current_mission_items", []))
            return {
                "current": 0,
                "total": total,
                "percent": 0,
                "finished": False,
                "mission_id": self.current_mission_id,
            }
        except Exception as e:
            logger.error(f"Progress error: {e}")
            return {
                "current": 0,
                "total": 0,
                "percent": 0,
                "error": str(e),
            }

    async def export_plan(self, waypoints: List[Dict[str, float]], name: str = "AIS Mission") -> Dict[str, Any]:
        """Export mission as QGroundControl .plan JSON."""
        validation = await self.validate_mission(waypoints)
        if not validation["valid"]:
            return {"success": False, "error": validation["error"]}
        return {
            "success": True,
            "plan": waypoints_to_plan(waypoints, name=name),
        }

    async def get_history(self) -> Dict[str, Any]:
        """Get mission history."""
        return {
            "missions": self.mission_history,
            "total": len(self.mission_history),
            "current_mission_id": self.current_mission_id,
        }
