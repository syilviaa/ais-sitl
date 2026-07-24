"""
SQLAlchemy ORM models for Veha 5 multi-drone platform.

Models:
- Drone: Physical drone with connection info
- Mission: Flight mission with waypoints
- TelemetryRecord: Time-series telemetry data
- FailsafeEvent: Emergency events log
- NoFlyZone: Restricted airspace
- User: User accounts & permissions
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean,
    DateTime, ForeignKey, JSON, Enum, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.backend.database import Base


class Drone(Base):
    """Physical drone with connection info."""

    __tablename__ = "drones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    status = Column(String(20), default="disconnected")  # connected/disconnected/error
    battery_percent = Column(Float, default=100.0)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    missions = relationship("Mission", back_populates="drone", cascade="all, delete-orphan")
    telemetry_records = relationship("TelemetryRecord", back_populates="drone", cascade="all, delete-orphan")
    failsafe_events = relationship("FailsafeEvent", back_populates="drone", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Drone {self.name} ({self.status})>"


class Mission(Base):
    """Flight mission with waypoints."""

    __tablename__ = "missions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    name = Column(String(255), nullable=True)
    waypoints = Column(JSON, nullable=False)  # Array of waypoint dicts
    status = Column(String(20), default="planned")  # planned/uploaded/running/completed/aborted
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    distance_meters = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    drone = relationship("Drone", back_populates="missions")
    telemetry_records = relationship("TelemetryRecord", back_populates="mission")
    mission_recording = relationship("MissionRecording", back_populates="mission", uselist=False)

    # Indexes for queries
    __table_args__ = (
        Index("idx_mission_drone_id", "drone_id"),
        Index("idx_mission_status", "status"),
        Index("idx_mission_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Mission {self.name or self.id} ({self.status})>"


class TelemetryRecord(Base):
    """Time-series telemetry data."""

    __tablename__ = "telemetry_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    drone_id = Column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    mission_id = Column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=True)

    # Position
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)

    # Velocity (NED)
    vx = Column(Float, nullable=True)
    vy = Column(Float, nullable=True)
    vz = Column(Float, nullable=True)

    # Attitude
    roll = Column(Float, nullable=True)
    pitch = Column(Float, nullable=True)
    yaw = Column(Float, nullable=True)

    # Status
    battery_percent = Column(Float, nullable=True)
    satellites = Column(Integer, nullable=True)
    gps_fix = Column(String(20), nullable=True)
    flight_mode = Column(String(20), nullable=True)
    armed = Column(Boolean, nullable=True)

    # Relationships
    drone = relationship("Drone", back_populates="telemetry_records")
    mission = relationship("Mission", back_populates="telemetry_records")

    # Composite index for time-series queries
    __table_args__ = (
        Index("idx_telemetry_drone_timestamp", "drone_id", "timestamp"),
        Index("idx_telemetry_mission_timestamp", "mission_id", "timestamp"),
    )

    def __repr__(self):
        return f"<Telemetry {self.drone_id} @ {self.timestamp}>"


class FailsafeEvent(Base):
    """Emergency events log."""

    __tablename__ = "failsafe_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    reason = Column(String(50), nullable=False)  # battery_low, link_loss, geofence_breach, etc
    action_taken = Column(String(100), nullable=True)  # hold, rtl, land, divert
    battery_percent = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    # Relationships
    drone = relationship("Drone", back_populates="failsafe_events")

    __table_args__ = (
        Index("idx_failsafe_drone_timestamp", "drone_id", "timestamp"),
    )

    def __repr__(self):
        return f"<Failsafe {self.drone_id} {self.reason}>"


class NoFlyZone(Base):
    """Restricted airspace."""

    __tablename__ = "noflyZones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    polygon = Column(JSON, nullable=False)  # GeoJSON polygon
    altitude_min = Column(Float, default=0.0)
    altitude_max = Column(Float, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_nfz_active", "active"),
    )

    def __repr__(self):
        return f"<NoFlyZone {self.name}>"


class MissionRecording(Base):
    """Recorded flight data for playback."""

    __tablename__ = "mission_recordings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id = Column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=False, unique=True)
    telemetry_data = Column(JSON, nullable=False)  # Compressed telemetry array
    duration_seconds = Column(Float, nullable=True)
    distance_meters = Column(Float, nullable=True)
    max_altitude = Column(Float, nullable=True)
    battery_start = Column(Float, nullable=True)
    battery_end = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    mission = relationship("Mission", back_populates="mission_recording")

    def __repr__(self):
        return f"<Recording {self.mission_id}>"


class User(Base):
    """User accounts with permissions."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_user_username", "username"),
        Index("idx_user_email", "email"),
    )

    def __repr__(self):
        return f"<User {self.username}>"
