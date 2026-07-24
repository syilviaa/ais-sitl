#!/usr/bin/env python3
"""
Veha 3 Complete Flight Example

Demonstrates full integration of:
- Drone flight control (Zhanel)
- Telemetry collection (10 Hz)
- Mission planning & execution
- Failsafe monitoring (battery + link loss)
- Geofence validation

Scenario:
1. Connect to PX4 SITL
2. Start telemetry collection (10 Hz)
3. Start failsafe monitoring
4. Plan mission (3 waypoints)
5. Upload mission
6. Execute mission
7. Monitor progress
8. Handle failsafe events (battery low → RTL)
9. Log all events

Timeline: Veha 3 (July 21-25, 2026)
Owner: Мерей + Жанель integration
Status: Complete end-to-end example
"""

import asyncio
import logging
from datetime import datetime

from src.autopilot.plane import Drone
from src.autopilot.geofence import GeofenceValidator
from src.telemetry import TelemetryCollector
from src.mission import MissionService
from src.failsafe import FailsafeMonitor
from src.models import Waypoint, FailsafeReason

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class VehaSurveyMission:
    """Complete Veha 3 flight mission with all systems integrated."""

    def __init__(self):
        """Initialize all systems."""
        self.drone = None
        self.telemetry_collector = None
        self.mission_service = None
        self.failsafe_monitor = None
        self.geofence_validator = None

        self.mission_waypoints = []
        self.flight_events = []
        self.start_time = None

    async def initialize_systems(self):
        """Initialize drone and all subsystems."""
        logger.info("=" * 60)
        logger.info("🚀 Veha 3 Complete Flight - Initialization")
        logger.info("=" * 60)

        # 1. Initialize Drone (Zhanel)
        logger.info("\n[1/5] Initializing Drone control system...")
        self.drone = Drone(host="127.0.0.1", port=14540)

        # 2. Connect to SITL
        logger.info("[2/5] Connecting to PX4 SITL...")
        try:
            connected = await self.drone.connect(timeout_s=10.0)
            if not connected:
                raise Exception("Failed to connect to PX4 SITL")
            logger.info("✅ Connected to PX4 SITL")
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise

        # 3. Wait for ready state (GPS, home position)
        logger.info("[3/5] Waiting for GPS fix and home position...")
        try:
            await self.drone.wait_until_ready(timeout_s=30.0)
            logger.info("✅ GPS locked and home position set")
        except Exception as e:
            logger.error(f"❌ Ready state failed: {e}")
            raise

        # 4. Initialize Telemetry Collector (Merey)
        logger.info("[4/5] Starting telemetry collection (10 Hz)...")
        self.telemetry_collector = TelemetryCollector(
            system=self.drone._system,
            rate_hz=10.0,
            history_size=100,
        )
        await self.telemetry_collector.start()
        logger.info("✅ Telemetry collector running")

        # 5. Initialize systems
        logger.info("[5/5] Initializing mission and failsafe systems...")

        # Mission Service
        self.mission_service = MissionService(system=self.drone._system)
        logger.info("  ✓ Mission Service ready")

        # Geofence Validator
        self.geofence_validator = GeofenceValidator()
        if self.geofence_validator.load_nfz_zones("config/nfz_zones.geojson"):
            logger.info("  ✓ Geofence validator loaded")
        else:
            logger.warning("  ⚠ No geofence zones loaded (optional)")

        # Failsafe Monitor
        self.failsafe_monitor = FailsafeMonitor(
            drone=self.drone,
            telemetry_collector=self.telemetry_collector,
            battery_warning_percent=20.0,
            battery_critical_percent=5.0,
            link_loss_timeout_sec=3.0,
        )

        async def on_failsafe(reason: FailsafeReason):
            """Handle failsafe events."""
            logger.critical(f"🚨 FAILSAFE TRIGGERED: {reason.value}")
            self.flight_events.append({
                'time': self._elapsed_time(),
                'type': 'failsafe',
                'reason': reason.value,
            })

        self.failsafe_monitor.on_failsafe(on_failsafe)
        logger.info("  ✓ Failsafe Monitor configured")

        logger.info("\n✅ All systems initialized and ready!")
        self.start_time = datetime.now()

    async def plan_mission(self):
        """Plan a simple 3-waypoint survey mission."""
        logger.info("\n" + "=" * 60)
        logger.info("📋 Mission Planning")
        logger.info("=" * 60)

        # Define waypoints (Zurich area example)
        self.mission_waypoints = [
            Waypoint(
                lat=47.3977,
                lon=8.5455,
                altitude_m=50.0,
                speed_m_s=5.0,
                wait_time_s=2.0,
                take_photo=True,
                gimbal_pitch_deg=-30.0,
            ),
            Waypoint(
                lat=47.3985,
                lon=8.5465,
                altitude_m=60.0,
                speed_m_s=5.0,
                wait_time_s=2.0,
                take_photo=True,
                gimbal_pitch_deg=-30.0,
            ),
            Waypoint(
                lat=47.3977,
                lon=8.5455,
                altitude_m=0.0,  # Return to home and land
                speed_m_s=3.0,
            ),
        ]

        logger.info(f"Planned {len(self.mission_waypoints)} waypoints:")
        for i, wp in enumerate(self.mission_waypoints, 1):
            logger.info(
                f"  {i}. [{wp.lat:.4f}, {wp.lon:.4f}] @ {wp.altitude_m}m"
            )

        # Validate mission against geofence
        logger.info("\n🔍 Validating mission against No-Fly Zones...")
        waypoint_tuples = [
            (wp.lat, wp.lon, wp.altitude_m)
            for wp in self.mission_waypoints
        ]

        is_valid = self.geofence_validator.validate_mission(waypoint_tuples)
        if is_valid:
            logger.info("✅ Mission clears all No-Fly Zones")
        else:
            logger.error("❌ Mission violates No-Fly Zone!")
            raise Exception("Mission validation failed")

        logger.info("✅ Mission planning complete")

    async def execute_mission(self):
        """Execute the planned mission."""
        logger.info("\n" + "=" * 60)
        logger.info("✈️  Mission Execution")
        logger.info("=" * 60)

        # Arm motors
        logger.info("\n[1/4] Arming motors...")
        try:
            await self.drone.arm()
            logger.info("✅ Motors armed")
            self.flight_events.append({
                'time': self._elapsed_time(),
                'type': 'armed',
                'message': 'Motors armed',
            })
        except Exception as e:
            logger.error(f"❌ Arm failed: {e}")
            raise

        # Takeoff
        logger.info("[2/4] Taking off to 50m...")
        try:
            await self.drone.takeoff(50.0)
            logger.info("✅ Takeoff complete")
            self.flight_events.append({
                'time': self._elapsed_time(),
                'type': 'takeoff',
                'message': 'Reached 50m altitude',
            })
        except Exception as e:
            logger.error(f"❌ Takeoff failed: {e}")
            raise

        # Upload mission
        logger.info("[3/4] Uploading mission...")
        try:
            success = await self.mission_service.upload_mission(
                self.mission_waypoints
            )
            if not success:
                raise Exception("Mission upload failed")
            logger.info("✅ Mission uploaded to autopilot")
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            raise

        # Start failsafe monitoring
        logger.info("[4/4] Starting failsafe monitoring...")
        failsafe_task = asyncio.create_task(self.failsafe_monitor.start())
        logger.info("✅ Failsafe monitoring active")

        # Execute mission
        logger.info("\n🚀 Starting mission execution...")
        self.flight_events.append({
            'time': self._elapsed_time(),
            'type': 'mission_start',
            'message': 'Mission execution started',
        })

        try:
            # Monitor mission progress
            max_duration = 600  # 10 minutes max
            start_time = asyncio.get_running_loop().time()

            while True:
                # Get latest telemetry
                telemetry = self.telemetry_collector.get_latest()
                if not telemetry:
                    await asyncio.sleep(1.0)
                    continue

                # Get mission progress
                progress = self.mission_service.get_progress()

                # Log status
                logger.info(
                    f"  Waypoint {progress['current']}/{progress['total']} | "
                    f"Alt: {telemetry.altitude_m:.1f}m | "
                    f"Battery: {telemetry.battery_percent:.1f}% | "
                    f"GPS: {telemetry.satellites} sats"
                )

                # Check if mission finished
                if progress['finished']:
                    logger.info("✅ Mission completed!")
                    self.flight_events.append({
                        'time': self._elapsed_time(),
                        'type': 'mission_complete',
                        'message': 'All waypoints completed',
                    })
                    break

                # Check timeout
                if asyncio.get_running_loop().time() - start_time > max_duration:
                    logger.error("❌ Mission timeout!")
                    break

                await asyncio.sleep(1.0)

        except Exception as e:
            logger.error(f"❌ Mission execution error: {e}")

        finally:
            # Stop failsafe monitoring
            await self.failsafe_monitor.stop()
            failsafe_task.cancel()
            try:
                await failsafe_task
            except asyncio.CancelledError:
                pass

    async def land_safely(self):
        """Land the drone safely."""
        logger.info("\n" + "=" * 60)
        logger.info("🛬 Landing")
        logger.info("=" * 60)

        try:
            logger.info("Initiating landing sequence...")
            await self.drone.land()
            logger.info("✅ Landed safely")
            self.flight_events.append({
                'time': self._elapsed_time(),
                'type': 'landed',
                'message': 'Landed safely',
            })
        except Exception as e:
            logger.error(f"❌ Landing failed: {e}")

    async def cleanup(self):
        """Stop all systems and disconnect."""
        logger.info("\nCleaning up...")

        # Stop telemetry
        if self.telemetry_collector:
            await self.telemetry_collector.stop()
            logger.info("  ✓ Telemetry collector stopped")

        # Disconnect drone
        if self.drone:
            await self.drone.disconnect()
            logger.info("  ✓ Drone disconnected")

        logger.info("✅ Cleanup complete")

    async def print_flight_summary(self):
        """Print mission summary and statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("📊 Flight Summary")
        logger.info("=" * 60)

        duration = self._elapsed_time()
        logger.info(f"\nTotal flight time: {duration:.1f} seconds")
        logger.info(f"Total events: {len(self.flight_events)}")

        logger.info("\nEvent log:")
        for event in self.flight_events:
            logger.info(
                f"  [{event['time']:6.1f}s] {event['type']:20} | "
                f"{event.get('message', event.get('reason', ''))}"
            )

        # Get final telemetry
        final_telemetry = self.telemetry_collector.get_latest()
        if final_telemetry:
            logger.info("\nFinal telemetry:")
            logger.info(f"  Position: [{final_telemetry.lat:.4f}, "
                       f"{final_telemetry.lon:.4f}]")
            logger.info(f"  Altitude: {final_telemetry.altitude_m:.1f}m AGL")
            logger.info(f"  Battery: {final_telemetry.battery_percent:.1f}%")
            logger.info(f"  GPS: {final_telemetry.satellites} satellites "
                       f"({final_telemetry.gps_fix})")
            logger.info(f"  Flight mode: {final_telemetry.flight_mode}")

        # Statistics
        history = self.telemetry_collector.get_history(count=100)
        if history:
            altitudes = [t.altitude_m for t in history if t]
            speeds = [t.speed_m_s for t in history if t]
            batteries = [t.battery_percent for t in history if t]

            logger.info("\nFlight statistics:")
            logger.info(f"  Max altitude: {max(altitudes):.1f}m")
            logger.info(f"  Max speed: {max(speeds):.1f} m/s")
            logger.info(f"  Battery drain: {batteries[0]:.1f}% → "
                       f"{batteries[-1]:.1f}%")

        logger.info("\n" + "=" * 60)
        logger.info("✅ Flight Summary Complete")
        logger.info("=" * 60)

    def _elapsed_time(self) -> float:
        """Get elapsed time since mission start."""
        if not self.start_time:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()


async def main():
    """Run complete Veha 3 flight mission."""
    mission = VehaSurveyMission()

    try:
        # Initialize all systems
        await mission.initialize_systems()

        # Plan mission
        await mission.plan_mission()

        # Execute mission (includes failsafe monitoring)
        await mission.execute_mission()

        # Land safely
        await mission.land_safely()

        # Print summary
        await mission.print_flight_summary()

    except KeyboardInterrupt:
        logger.info("\n⚠️  Mission interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Mission failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always cleanup
        await mission.cleanup()

    logger.info("\n🎉 Veha 3 Complete Flight Example - Done!")


if __name__ == "__main__":
    asyncio.run(main())
