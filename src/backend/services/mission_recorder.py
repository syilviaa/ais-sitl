"""
Mission Recorder - Capture and playback flight telemetry.

Provides:
- Real-time telemetry capture during missions
- Compressed storage in database
- Mission playback and analysis
- Flight statistics (duration, distance, battery)
"""

import asyncio
import logging
import json
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TelemetrySnapshot:
    """Single telemetry frame."""

    timestamp: float
    lat: float
    lon: float
    altitude: float
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    battery: float = 100.0
    satellites: int = 0
    armed: bool = False
    mode: str = "UNKNOWN"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "t": self.timestamp,
            "lat": self.lat,
            "lon": self.lon,
            "alt": self.altitude,
            "vx": self.vx,
            "vy": self.vy,
            "vz": self.vz,
            "roll": self.roll,
            "pitch": self.pitch,
            "yaw": self.yaw,
            "bat": self.battery,
            "sat": self.satellites,
            "arm": self.armed,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: Dict):
        """Create from dictionary."""
        return cls(
            timestamp=data.get("t", 0),
            lat=data.get("lat", 0),
            lon=data.get("lon", 0),
            altitude=data.get("alt", 0),
            vx=data.get("vx", 0),
            vy=data.get("vy", 0),
            vz=data.get("vz", 0),
            roll=data.get("roll", 0),
            pitch=data.get("pitch", 0),
            yaw=data.get("yaw", 0),
            battery=data.get("bat", 100),
            satellites=data.get("sat", 0),
            armed=data.get("arm", False),
            mode=data.get("mode", "UNKNOWN"),
        )


class MissionRecorder:
    """Records and manages mission flight data."""

    def __init__(self, mission_id: str):
        """Initialize recorder for a mission."""
        self.mission_id = mission_id
        self.snapshots: List[TelemetrySnapshot] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.is_recording = False

    async def start(self):
        """Start recording."""
        if self.is_recording:
            return

        self.is_recording = True
        self.start_time = datetime.utcnow().timestamp()
        self.snapshots = []
        logger.info(f"✅ Mission {self.mission_id} recording started")

    async def stop(self):
        """Stop recording."""
        if not self.is_recording:
            return

        self.is_recording = False
        self.end_time = datetime.utcnow().timestamp()
        logger.info(f"✅ Mission {self.mission_id} recording stopped ({len(self.snapshots)} frames)")

    async def add_snapshot(self, snapshot: TelemetrySnapshot):
        """Record a telemetry snapshot."""
        if not self.is_recording:
            return

        self.snapshots.append(snapshot)

    def get_duration(self) -> float:
        """Get mission duration in seconds."""
        if not self.start_time or not self.end_time:
            return 0.0
        return self.end_time - self.start_time

    def get_distance(self) -> float:
        """Calculate total distance traveled in meters using Haversine."""
        if len(self.snapshots) < 2:
            return 0.0

        from math import radians, cos, sin, asin, sqrt

        total_distance = 0.0

        for i in range(len(self.snapshots) - 1):
            s1 = self.snapshots[i]
            s2 = self.snapshots[i + 1]

            lat1, lon1 = radians(s1.lat), radians(s1.lon)
            lat2, lon2 = radians(s2.lat), radians(s2.lon)

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            distance = 6371000 * c  # Earth radius in meters

            total_distance += distance

        return total_distance

    def get_max_altitude(self) -> float:
        """Get maximum altitude during mission."""
        if not self.snapshots:
            return 0.0
        return max(s.altitude for s in self.snapshots)

    def get_battery_range(self) -> Dict:
        """Get battery usage range."""
        if not self.snapshots:
            return {"start": 0.0, "end": 0.0, "min": 0.0, "max": 0.0}

        batteries = [s.battery for s in self.snapshots]
        return {
            "start": batteries[0],
            "end": batteries[-1],
            "min": min(batteries),
            "max": max(batteries),
        }

    def get_statistics(self) -> Dict:
        """Get mission flight statistics."""
        return {
            "mission_id": self.mission_id,
            "frame_count": len(self.snapshots),
            "duration_seconds": self.get_duration(),
            "distance_meters": self.get_distance(),
            "max_altitude": self.get_max_altitude(),
            "battery": self.get_battery_range(),
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    def get_compressed_data(self) -> str:
        """Get compressed telemetry data for storage."""
        data = [s.to_dict() for s in self.snapshots]
        return json.dumps(data)

    @classmethod
    def from_compressed_data(cls, mission_id: str, compressed: str):
        """Recreate recorder from compressed data."""
        recorder = cls(mission_id)

        try:
            data = json.loads(compressed)
            recorder.snapshots = [TelemetrySnapshot.from_dict(d) for d in data]

            if recorder.snapshots:
                recorder.start_time = recorder.snapshots[0].timestamp
                recorder.end_time = recorder.snapshots[-1].timestamp
        except Exception as e:
            logger.error(f"Failed to decompress mission data: {e}")

        return recorder

    def playback_timeline(self, playback_speed: float = 1.0) -> List[Dict]:
        """Generate playback timeline with adjusted timestamps."""
        if not self.snapshots:
            return []

        base_time = self.snapshots[0].timestamp
        timeline = []

        for snapshot in self.snapshots:
            adjusted_time = (snapshot.timestamp - base_time) / playback_speed
            frame = snapshot.to_dict()
            frame["playback_time"] = adjusted_time
            timeline.append(frame)

        return timeline
