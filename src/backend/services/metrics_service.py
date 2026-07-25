"""
Metrics Service - Prometheus metrics collection and export.

Provides:
- Fleet status metrics (drone count, battery, connectivity)
- Mission metrics (success rate, duration, distance)
- Telemetry metrics (update rate, capture rate)
- Geofence metrics (violation count, zone status)
"""

import logging
from typing import Dict
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for collecting and exporting metrics."""

    def __init__(self):
        """Initialize metrics service."""
        self.fleet_size = 0
        self.connected_drones = 0
        self.total_battery_percent = 0.0
        self.min_battery_percent = 100.0
        self.max_battery_percent = 0.0

        self.missions_total = 0
        self.missions_completed = 0
        self.missions_failed = 0
        self.total_mission_duration = 0.0
        self.total_mission_distance = 0.0

        self.telemetry_updates = 0
        self.telemetry_rate_hz = 0.0

        self.geofence_violations_total = 0
        self.geofence_zones_active = 0

        self.start_time = datetime.utcnow()

    def update_fleet_metrics(self, fleet_status: Dict):
        """Update fleet-level metrics."""
        try:
            drones = fleet_status.get("drones", {})
            self.fleet_size = len(drones)
            self.connected_drones = sum(1 for d in drones.values() if d.get("connected", False))

            batteries = [d.get("battery_percent", 0) for d in drones.values()]
            if batteries:
                self.total_battery_percent = sum(batteries) / len(batteries)
                self.min_battery_percent = min(batteries)
                self.max_battery_percent = max(batteries)
            else:
                self.total_battery_percent = 0.0
                self.min_battery_percent = 100.0
                self.max_battery_percent = 0.0

            logger.debug(f"Fleet metrics: {self.fleet_size} drones, {self.connected_drones} connected")

        except Exception as e:
            logger.error(f"Fleet metrics update error: {e}")

    def update_mission_metrics(self, missions_data: Dict):
        """Update mission-level metrics."""
        try:
            self.missions_total = missions_data.get("total", 0)
            self.missions_completed = missions_data.get("completed", 0)
            self.missions_failed = missions_data.get("failed", 0)
            self.total_mission_duration = missions_data.get("total_duration", 0.0)
            self.total_mission_distance = missions_data.get("total_distance", 0.0)

            logger.debug(f"Mission metrics: {self.missions_total} total, {self.missions_completed} completed")

        except Exception as e:
            logger.error(f"Mission metrics update error: {e}")

    def update_telemetry_metrics(self, telemetry_stats: Dict):
        """Update telemetry-level metrics."""
        try:
            self.telemetry_updates = telemetry_stats.get("update_count", 0)
            self.telemetry_rate_hz = telemetry_stats.get("actual_rate_hz", 0.0)

            logger.debug(f"Telemetry metrics: {self.telemetry_updates} updates at {self.telemetry_rate_hz} Hz")

        except Exception as e:
            logger.error(f"Telemetry metrics update error: {e}")

    def update_geofence_metrics(self, geofence_data: Dict):
        """Update geofence-level metrics."""
        try:
            self.geofence_violations_total = geofence_data.get("violations_total", 0)
            self.geofence_zones_active = geofence_data.get("zones_active", 0)

            logger.debug(f"Geofence metrics: {self.geofence_zones_active} zones, {self.geofence_violations_total} violations")

        except Exception as e:
            logger.error(f"Geofence metrics update error: {e}")

    def record_mission_completion(self, duration_seconds: float, distance_meters: float, success: bool):
        """Record a completed mission."""
        self.missions_total += 1
        self.total_mission_duration += duration_seconds
        self.total_mission_distance += distance_meters

        if success:
            self.missions_completed += 1
        else:
            self.missions_failed += 1

    def record_geofence_violation(self):
        """Record a geofence violation."""
        self.geofence_violations_total += 1

    def get_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        avg_mission_duration = (
            self.total_mission_duration / self.missions_completed
            if self.missions_completed > 0
            else 0.0
        )
        avg_mission_distance = (
            self.total_mission_distance / self.missions_completed
            if self.missions_completed > 0
            else 0.0
        )
        mission_success_rate = (
            (self.missions_completed / self.missions_total * 100)
            if self.missions_total > 0
            else 0.0
        )

        metrics = f"""# HELP ais_sitl_uptime_seconds Application uptime in seconds
# TYPE ais_sitl_uptime_seconds gauge
ais_sitl_uptime_seconds {uptime_seconds}

# HELP ais_sitl_fleet_size_total Total number of drones in fleet
# TYPE ais_sitl_fleet_size_total gauge
ais_sitl_fleet_size_total {self.fleet_size}

# HELP ais_sitl_fleet_connected_drones Number of connected drones
# TYPE ais_sitl_fleet_connected_drones gauge
ais_sitl_fleet_connected_drones {self.connected_drones}

# HELP ais_sitl_fleet_battery_percent_avg Average battery level across fleet
# TYPE ais_sitl_fleet_battery_percent_avg gauge
ais_sitl_fleet_battery_percent_avg {self.total_battery_percent:.2f}

# HELP ais_sitl_fleet_battery_percent_min Minimum battery level in fleet
# TYPE ais_sitl_fleet_battery_percent_min gauge
ais_sitl_fleet_battery_percent_min {self.min_battery_percent:.2f}

# HELP ais_sitl_fleet_battery_percent_max Maximum battery level in fleet
# TYPE ais_sitl_fleet_battery_percent_max gauge
ais_sitl_fleet_battery_percent_max {self.max_battery_percent:.2f}

# HELP ais_sitl_missions_total Total number of missions executed
# TYPE ais_sitl_missions_total counter
ais_sitl_missions_total {self.missions_total}

# HELP ais_sitl_missions_completed Total number of completed missions
# TYPE ais_sitl_missions_completed counter
ais_sitl_missions_completed {self.missions_completed}

# HELP ais_sitl_missions_failed Total number of failed missions
# TYPE ais_sitl_missions_failed counter
ais_sitl_missions_failed {self.missions_failed}

# HELP ais_sitl_mission_success_rate_percent Mission success rate
# TYPE ais_sitl_mission_success_rate_percent gauge
ais_sitl_mission_success_rate_percent {mission_success_rate:.2f}

# HELP ais_sitl_mission_duration_seconds_total Total mission duration
# TYPE ais_sitl_mission_duration_seconds_total counter
ais_sitl_mission_duration_seconds_total {self.total_mission_duration:.2f}

# HELP ais_sitl_mission_duration_seconds_avg Average mission duration
# TYPE ais_sitl_mission_duration_seconds_avg gauge
ais_sitl_mission_duration_seconds_avg {avg_mission_duration:.2f}

# HELP ais_sitl_mission_distance_meters_total Total mission distance
# TYPE ais_sitl_mission_distance_meters_total counter
ais_sitl_mission_distance_meters_total {self.total_mission_distance:.2f}

# HELP ais_sitl_mission_distance_meters_avg Average mission distance
# TYPE ais_sitl_mission_distance_meters_avg gauge
ais_sitl_mission_distance_meters_avg {avg_mission_distance:.2f}

# HELP ais_sitl_telemetry_updates_total Total telemetry updates received
# TYPE ais_sitl_telemetry_updates_total counter
ais_sitl_telemetry_updates_total {self.telemetry_updates}

# HELP ais_sitl_telemetry_rate_hz Telemetry update rate in Hz
# TYPE ais_sitl_telemetry_rate_hz gauge
ais_sitl_telemetry_rate_hz {self.telemetry_rate_hz:.2f}

# HELP ais_sitl_geofence_violations_total Total geofence violations
# TYPE ais_sitl_geofence_violations_total counter
ais_sitl_geofence_violations_total {self.geofence_violations_total}

# HELP ais_sitl_geofence_zones_active Number of active geofence zones
# TYPE ais_sitl_geofence_zones_active gauge
ais_sitl_geofence_zones_active {self.geofence_zones_active}
"""
        return metrics

    def get_metrics_summary(self) -> Dict:
        """Get a summary of current metrics."""
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()

        mission_success_rate = (
            (self.missions_completed / self.missions_total * 100)
            if self.missions_total > 0
            else 0.0
        )

        avg_mission_duration = (
            self.total_mission_duration / self.missions_completed
            if self.missions_completed > 0
            else 0.0
        )

        return {
            "uptime_seconds": uptime_seconds,
            "fleet": {
                "size": self.fleet_size,
                "connected": self.connected_drones,
                "battery_avg": self.total_battery_percent,
                "battery_min": self.min_battery_percent,
                "battery_max": self.max_battery_percent,
            },
            "missions": {
                "total": self.missions_total,
                "completed": self.missions_completed,
                "failed": self.missions_failed,
                "success_rate_percent": mission_success_rate,
                "avg_duration_seconds": avg_mission_duration,
                "total_distance_meters": self.total_mission_distance,
            },
            "telemetry": {
                "updates_total": self.telemetry_updates,
                "rate_hz": self.telemetry_rate_hz,
            },
            "geofence": {
                "violations_total": self.geofence_violations_total,
                "zones_active": self.geofence_zones_active,
            },
        }
