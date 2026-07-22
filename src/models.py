"""
Data Models for AIS SITL Platform

Shared data structures used across:
- telemetry.py (TelemetrySnapshot)
- mission.py (Waypoint, MissionItem)
- failsafe.py (FailsafeReason)
- drone.py (DroneState)

Owner: Мерей
Status: Veha 2-3 (July 21-25, 2026)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional
import time


class GPSFixType(Enum):
    """GPS fix quality."""
    NO_FIX = "no_fix"         # No GPS
    GPS_2D = "2d"             # 2D fix (latitude, longitude)
    GPS_3D = "3d"             # 3D fix (lat, lon, alt)


class FlightMode(Enum):
    """PX4 flight modes."""
    MANUAL = "manual"
    ALTCTL = "altctl"
    POSCTL = "posctl"
    AUTO = "auto"
    ACRO = "acro"
    OFFBOARD = "offboard"
    STABILIZED = "stabilized"
    RTL = "rtl"                # Return to Launch
    LAND = "land"


# ============================================================================
# Telemetry Models
# ============================================================================

@dataclass
class TelemetrySnapshot:
    """
    Single telemetry snapshot (10 Hz = 0.1s interval).

    Captured from:
    - PX4 SITL via MAVLink
    - MAVSDK Telemetry streams
    """
    # Timestamp
    timestamp: float = field(default_factory=time.time)  # Unix time (seconds)

    # Position (GPS)
    lat: float = 0.0                # Latitude (degrees)
    lon: float = 0.0                # Longitude (degrees)
    altitude_m: float = 0.0          # Altitude AGL (meters)
    altitude_msl_m: float = 0.0      # Altitude MSL (meters) - optional

    # Velocity
    vx: float = 0.0                 # Forward velocity (m/s)
    vy: float = 0.0                 # Right velocity (m/s)
    vz: float = 0.0                 # Down velocity (m/s)
    speed_m_s: float = 0.0           # Horizontal speed (m/s)

    # Attitude (Euler angles)
    roll_deg: float = 0.0            # Roll (degrees) -180..180
    pitch_deg: float = 0.0           # Pitch (degrees) -90..90
    yaw_deg: float = 0.0             # Yaw/heading (degrees) 0..360

    # Health
    battery_percent: float = 100.0   # Battery charge (0-100%)
    battery_voltage_v: float = 0.0   # Battery voltage (volts)
    battery_current_a: float = 0.0   # Battery current (amps) - optional

    # GPS
    gps_fix: str = "no_fix"          # "no_fix", "2d", "3d"
    satellites: int = 0              # Number of GPS satellites

    # Drone state
    armed: bool = False              # Motors armed?
    flight_mode: str = "manual"      # Current flight mode
    in_air: bool = False             # In flight?

    # Ground distance
    ground_distance_m: float = 0.0   # Distance from home (meters)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "position": {
                "lat": self.lat,
                "lon": self.lon,
                "alt_agl": self.altitude_m,
                "alt_msl": self.altitude_msl_m,
            },
            "velocity": {
                "vx": self.vx,
                "vy": self.vy,
                "vz": self.vz,
                "speed": self.speed_m_s,
            },
            "attitude": {
                "roll": self.roll_deg,
                "pitch": self.pitch_deg,
                "yaw": self.yaw_deg,
            },
            "battery": {
                "percent": self.battery_percent,
                "voltage": self.battery_voltage_v,
                "current": self.battery_current_a,
            },
            "gps": {
                "fix": self.gps_fix,
                "satellites": self.satellites,
            },
            "state": {
                "armed": self.armed,
                "flight_mode": self.flight_mode,
                "in_air": self.in_air,
                "ground_distance": self.ground_distance_m,
            },
        }


# ============================================================================
# Mission Models
# ============================================================================

@dataclass
class Waypoint:
    """
    Single waypoint for mission.

    Converted to MAVSDK MissionItem for upload to PX4.
    """
    lat: float                       # Latitude (degrees)
    lon: float                       # Longitude (degrees)
    altitude_m: float                # Altitude AGL (meters)

    # Waypoint behavior
    speed_m_s: float = 5.0           # Cruise speed (m/s)
    wait_time_s: float = 0.0         # Hover time at waypoint (seconds)
    acceptance_radius_m: float = 5.0  # Distance to accept waypoint (meters)

    # Camera/gimbal (optional)
    gimbal_pitch_deg: float = 0.0    # Gimbal pitch (degrees)
    gimbal_yaw_deg: float = 0.0      # Gimbal yaw (degrees)
    take_photo: bool = False         # Take photo at waypoint?

    # Yaw behavior
    yaw_deg: Optional[float] = None  # Target yaw angle (degrees)
    yaw_mode: str = "auto"           # "auto" (toward next), "manual"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "position": (self.lat, self.lon, self.altitude_m),
            "speed": self.speed_m_s,
            "wait": self.wait_time_s,
            "acceptance": self.acceptance_radius_m,
            "gimbal": (self.gimbal_pitch_deg, self.gimbal_yaw_deg),
            "yaw": self.yaw_deg,
        }

    @staticmethod
    def from_tuple(lat: float, lon: float, alt: float) -> "Waypoint":
        """Create waypoint from (lat, lon, alt) tuple."""
        return Waypoint(lat=lat, lon=lon, altitude_m=alt)


@dataclass
class MissionItem:
    """
    MAVSDK-compatible mission item.

    Converted from Waypoint for upload to PX4.
    """
    latitude_deg: float
    longitude_deg: float
    relative_altitude_m: float
    speed_m_s: float = 5.0
    is_fly_through: bool = True
    gimbal_pitch_degree: float = 0.0
    gimbal_yaw_degree: float = 0.0
    camera_action: str = "none"      # "none", "take_photo", "start_video", "stop_video"
    loiter_time_s: float = 0.0
    camera_photo_interval_s: float = 0.0

    @staticmethod
    def from_waypoint(wp: Waypoint) -> "MissionItem":
        """Convert Waypoint to MissionItem."""
        camera_action = "take_photo" if wp.take_photo else "none"
        return MissionItem(
            latitude_deg=wp.lat,
            longitude_deg=wp.lon,
            relative_altitude_m=wp.altitude_m,
            speed_m_s=wp.speed_m_s,
            is_fly_through=wp.wait_time_s == 0.0,
            gimbal_pitch_degree=wp.gimbal_pitch_deg,
            gimbal_yaw_degree=wp.gimbal_yaw_deg,
            camera_action=camera_action,
            loiter_time_s=wp.wait_time_s,
        )


@dataclass
class MissionProgress:
    """Mission execution progress."""
    current_waypoint: int            # Current waypoint index (0-based)
    total_waypoints: int             # Total waypoints
    is_mission_finished: bool = False # Mission complete?

    @property
    def percent_complete(self) -> float:
        """Progress as percentage (0-100)."""
        if self.total_waypoints == 0:
            return 0.0
        return (self.current_waypoint / self.total_waypoints) * 100.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "current": self.current_waypoint,
            "total": self.total_waypoints,
            "percent": self.percent_complete,
            "finished": self.is_mission_finished,
        }


# ============================================================================
# Geofencing Models
# ============================================================================

@dataclass
class NoFlyZone:
    """
    No-Fly Zone (NFZ) - restricted airspace.

    Used by:
    - GeofenceValidator (Жанель)
    - FailsafeMonitor (Мерей)
    """
    name: str                        # Zone name
    polygon: List[Tuple[float, float]]  # [(lat, lon), ...] vertices
    max_altitude_m: float            # Max altitude in zone (meters)
    min_altitude_m: float = 0.0      # Min altitude in zone (meters)
    active: bool = True              # Is zone active?
    buffer_m: float = 0.0            # Safety buffer (meters)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "polygon": self.polygon,
            "max_altitude": self.max_altitude_m,
            "min_altitude": self.min_altitude_m,
            "active": self.active,
            "buffer": self.buffer_m,
        }


# ============================================================================
# Failsafe Models
# ============================================================================

class FailsafeReason(Enum):
    """Why failsafe was triggered."""
    BATTERY_LOW = "battery_low"           # < 20%
    BATTERY_CRITICAL = "battery_critical"  # < 5%
    LINK_LOSS = "link_loss"               # > 3s without telemetry
    MANUAL_RTL = "manual_rtl"             # Operator command
    GEOFENCE_BREACH = "geofence_breach"   # Entered NFZ
    GPS_LOST = "gps_lost"                 # No GPS fix


@dataclass
class FailsafeEvent:
    """Failsafe event log entry."""
    timestamp: float = field(default_factory=time.time)
    reason: FailsafeReason = FailsafeReason.MANUAL_RTL
    battery_percent: Optional[float] = None
    altitude_m: Optional[float] = None
    position: Optional[Tuple[float, float]] = None  # (lat, lon)
    message: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "reason": self.reason.value,
            "battery": self.battery_percent,
            "altitude": self.altitude_m,
            "position": self.position,
            "message": self.message,
        }


# ============================================================================
# System Models
# ============================================================================

@dataclass
class SystemHealth:
    """Overall system health status."""
    connected: bool = False          # Connected to SITL?
    armed: bool = False              # Motors armed?
    gps_ok: bool = False             # GPS lock?
    battery_ok: bool = False         # Battery healthy?
    link_ok: bool = False            # MAVLink link healthy?
    failsafe_active: bool = False    # Failsafe monitoring running?

    @property
    def is_ready_for_flight(self) -> bool:
        """Ready to arm and fly?"""
        return (
            self.connected
            and self.gps_ok
            and self.battery_ok
            and self.link_ok
            and not self.failsafe_active
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "connected": self.connected,
            "armed": self.armed,
            "gps": self.gps_ok,
            "battery": self.battery_ok,
            "link": self.link_ok,
            "failsafe": self.failsafe_active,
            "ready_to_fly": self.is_ready_for_flight,
        }
