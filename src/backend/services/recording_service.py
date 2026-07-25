"""
Recording Service - Manages mission recording lifecycle and storage.

Provides:
- Recording session management
- Telemetry capture integration
- Database persistence
- Recording retrieval and analysis
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime

from src.backend.services.mission_recorder import MissionRecorder, TelemetrySnapshot
from src.backend.database import SessionLocal
from src.backend.models import Mission, MissionRecording

logger = logging.getLogger(__name__)


class RecordingService:
    """Service for managing mission recordings."""

    def __init__(self):
        """Initialize recording service."""
        self.active_recordings: Dict[str, MissionRecorder] = {}
        self._db = None

    def set_database(self, session_factory):
        """Set database session factory."""
        self._db = session_factory

    async def start_recording(self, mission_id: str) -> Dict:
        """Start recording a mission."""
        try:
            if mission_id in self.active_recordings:
                return {"success": False, "error": f"Recording already active for {mission_id}"}

            recorder = MissionRecorder(mission_id)
            await recorder.start()

            self.active_recordings[mission_id] = recorder

            logger.info(f"✅ Started recording mission {mission_id}")
            return {
                "success": True,
                "message": f"Recording started for mission {mission_id}",
                "mission_id": mission_id,
            }

        except Exception as e:
            logger.error(f"Start recording error: {e}")
            return {"success": False, "error": str(e)}

    async def add_telemetry(self, mission_id: str, snapshot_dict: Dict) -> None:
        """Add telemetry snapshot to active recording."""
        if mission_id not in self.active_recordings:
            return

        try:
            snapshot = TelemetrySnapshot(
                timestamp=snapshot_dict.get("timestamp", 0),
                lat=snapshot_dict.get("lat", 0),
                lon=snapshot_dict.get("lon", 0),
                altitude=snapshot_dict.get("altitude", 0),
                vx=snapshot_dict.get("vx", 0),
                vy=snapshot_dict.get("vy", 0),
                vz=snapshot_dict.get("vz", 0),
                roll=snapshot_dict.get("roll", 0),
                pitch=snapshot_dict.get("pitch", 0),
                yaw=snapshot_dict.get("yaw", 0),
                battery=snapshot_dict.get("battery", 100),
                satellites=snapshot_dict.get("satellites", 0),
                armed=snapshot_dict.get("armed", False),
                mode=snapshot_dict.get("mode", "UNKNOWN"),
            )

            recorder = self.active_recordings[mission_id]
            await recorder.add_snapshot(snapshot)

        except Exception as e:
            logger.error(f"Add telemetry error: {e}")

    async def stop_recording(self, mission_id: str) -> Dict:
        """Stop recording and save to database."""
        try:
            if mission_id not in self.active_recordings:
                return {"success": False, "error": f"No active recording for {mission_id}"}

            recorder = self.active_recordings[mission_id]
            await recorder.stop()

            stats = recorder.get_statistics()
            compressed_data = recorder.get_compressed_data()

            # Save to database
            if self._db:
                session = self._db()
                try:
                    recording = MissionRecording(
                        mission_id=mission_id,
                        telemetry_data=compressed_data,
                        duration_seconds=stats["duration_seconds"],
                        distance_meters=stats["distance_meters"],
                        max_altitude=stats["max_altitude"],
                        battery_start=stats["battery"]["start"],
                        battery_end=stats["battery"]["end"],
                    )
                    session.add(recording)
                    session.commit()
                    recording_id = str(recording.id)
                except Exception as e:
                    session.rollback()
                    logger.error(f"Database save error: {e}")
                    recording_id = None
                finally:
                    session.close()
            else:
                recording_id = None

            del self.active_recordings[mission_id]

            logger.info(f"✅ Stopped recording mission {mission_id}")
            return {
                "success": True,
                "message": f"Recording stopped for mission {mission_id}",
                "mission_id": mission_id,
                "recording_id": recording_id,
                "statistics": stats,
            }

        except Exception as e:
            logger.error(f"Stop recording error: {e}")
            return {"success": False, "error": str(e)}

    async def get_recording(self, mission_id: str) -> Dict:
        """Retrieve a recorded mission."""
        try:
            if self._db:
                session = self._db()
                try:
                    recording = session.query(MissionRecording).filter_by(mission_id=mission_id).first()

                    if not recording:
                        return {"success": False, "error": f"No recording found for {mission_id}"}

                    recorder = MissionRecorder.from_compressed_data(
                        mission_id,
                        recording.telemetry_data
                    )
                    stats = recorder.get_statistics()

                    return {
                        "success": True,
                        "recording_id": str(recording.id),
                        "mission_id": mission_id,
                        "statistics": stats,
                        "frame_count": len(recorder.snapshots),
                    }
                finally:
                    session.close()
            else:
                return {"success": False, "error": "Database not configured"}

        except Exception as e:
            logger.error(f"Get recording error: {e}")
            return {"success": False, "error": str(e)}

    async def list_recordings(self, limit: int = 50) -> Dict:
        """List all recorded missions."""
        try:
            if self._db:
                session = self._db()
                try:
                    recordings = session.query(MissionRecording).order_by(
                        MissionRecording.created_at.desc()
                    ).limit(limit).all()

                    return {
                        "success": True,
                        "count": len(recordings),
                        "recordings": [
                            {
                                "recording_id": str(r.id),
                                "mission_id": str(r.mission_id),
                                "duration_seconds": r.duration_seconds,
                                "distance_meters": r.distance_meters,
                                "max_altitude": r.max_altitude,
                                "battery_start": r.battery_start,
                                "battery_end": r.battery_end,
                                "created_at": r.created_at.isoformat() if r.created_at else None,
                            }
                            for r in recordings
                        ]
                    }
                finally:
                    session.close()
            else:
                return {"success": False, "error": "Database not configured"}

        except Exception as e:
            logger.error(f"List recordings error: {e}")
            return {"success": False, "error": str(e)}

    async def get_playback_timeline(self, mission_id: str, playback_speed: float = 1.0) -> Dict:
        """Get playback timeline for a recorded mission."""
        try:
            if self._db:
                session = self._db()
                try:
                    recording = session.query(MissionRecording).filter_by(mission_id=mission_id).first()

                    if not recording:
                        return {"success": False, "error": f"No recording found for {mission_id}"}

                    recorder = MissionRecorder.from_compressed_data(
                        mission_id,
                        recording.telemetry_data
                    )
                    timeline = recorder.playback_timeline(playback_speed)

                    return {
                        "success": True,
                        "mission_id": mission_id,
                        "playback_speed": playback_speed,
                        "frame_count": len(timeline),
                        "duration_seconds": recorder.get_duration(),
                        "timeline": timeline,
                    }
                finally:
                    session.close()
            else:
                return {"success": False, "error": "Database not configured"}

        except Exception as e:
            logger.error(f"Playback timeline error: {e}")
            return {"success": False, "error": str(e)}

    async def delete_recording(self, mission_id: str) -> Dict:
        """Delete a recorded mission."""
        try:
            if self._db:
                session = self._db()
                try:
                    recording = session.query(MissionRecording).filter_by(mission_id=mission_id).first()

                    if not recording:
                        return {"success": False, "error": f"No recording found for {mission_id}"}

                    session.delete(recording)
                    session.commit()

                    logger.info(f"✅ Deleted recording for mission {mission_id}")
                    return {
                        "success": True,
                        "message": f"Recording deleted for mission {mission_id}",
                    }
                finally:
                    session.close()
            else:
                return {"success": False, "error": "Database not configured"}

        except Exception as e:
            logger.error(f"Delete recording error: {e}")
            return {"success": False, "error": str(e)}
