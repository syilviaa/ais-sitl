"""
Failsafe Monitoring and Emergency Response

RTL triggered by:
- Low battery (< 20%)
- Link loss (> 3 seconds without telemetry)

Timeline: Veha 3 (July 24-25, 2026)
Owner: Мерей
"""

import asyncio
import logging
import time
from typing import Optional, Callable

from src.models import FailsafeReason, FailsafeEvent

logger = logging.getLogger(__name__)


class FailsafeMonitor:
    """
    Monitors drone health and triggers RTL on emergency.

    Thresholds:
    - Battery warning: 20%
    - Battery critical: 5%
    - Link loss timeout: 3.0 seconds
    """

    def __init__(
        self,
        drone,
        telemetry_collector,
        battery_warning_percent: float = 20.0,
        battery_critical_percent: float = 5.0,
        link_loss_timeout_sec: float = 3.0,
    ):
        """
        Initialize failsafe monitor.

        Args:
            drone: Drone instance (for RTL command)
            telemetry_collector: TelemetryCollector (for monitoring)
            battery_warning_percent: Warning threshold (%)
            battery_critical_percent: Critical threshold (%)
            link_loss_timeout_sec: Timeout for link loss detection (seconds)
        """
        self.drone = drone
        self.telemetry_collector = telemetry_collector
        self.battery_warning = battery_warning_percent
        self.battery_critical = battery_critical_percent
        self.link_loss_timeout = link_loss_timeout_sec

        self._monitoring = False
        self._rtl_triggered = False
        self._last_telemetry_time = time.time()
        self._on_failsafe_callback: Optional[Callable] = None

        logger.info(f"FailsafeMonitor initialized")
        logger.info(f"  Battery warning: {battery_warning_percent}%")
        logger.info(f"  Battery critical: {battery_critical_percent}%")
        logger.info(f"  Link loss timeout: {link_loss_timeout_sec}s")

    def on_failsafe(self, callback: Callable[[FailsafeReason], None]):
        """Register callback for failsafe events."""
        self._on_failsafe_callback = callback

    async def start(self):
        """Start background failsafe monitoring."""
        if self._monitoring:
            logger.warning("Failsafe monitoring already active")
            return

        logger.info("🚨 Failsafe monitoring started")
        self._monitoring = True
        self._rtl_triggered = False

        try:
            while self._monitoring:
                await self._check_conditions()
                await asyncio.sleep(0.1)  # Check every 100ms
        except Exception as e:
            logger.error(f"Failsafe monitor error: {e}")
        finally:
            self._monitoring = False

    async def stop(self):
        """Stop failsafe monitoring."""
        logger.info("Failsafe monitoring stopped")
        self._monitoring = False

    async def _check_conditions(self):
        """Check battery and link health."""
        # Get latest telemetry
        telemetry = self.telemetry_collector.get_latest()

        if telemetry is None:
            # No telemetry yet
            return

        # Update last telemetry time
        self._last_telemetry_time = telemetry.timestamp

        # Check battery
        await self._check_battery(telemetry.battery_percent)

        # Check link health
        await self._check_link_health()

    async def _check_battery(self, battery_percent: float):
        """Monitor battery level."""
        if self._rtl_triggered:
            return  # Already triggered

        # Critical battery - immediate land
        if battery_percent < self.battery_critical:
            logger.critical(f"🔴 CRITICAL BATTERY: {battery_percent}%")
            await self._trigger_rtl(FailsafeReason.BATTERY_CRITICAL)
            return

        # Low battery - trigger RTL
        if battery_percent < self.battery_warning:
            logger.warning(f"⚠️  LOW BATTERY: {battery_percent}%")
            await self._trigger_rtl(FailsafeReason.BATTERY_LOW)
            return

    async def _check_link_health(self):
        """Monitor MAVLink connection health."""
        if self._rtl_triggered:
            return  # Already triggered

        elapsed = time.time() - self._last_telemetry_time

        if elapsed > self.link_loss_timeout:
            logger.critical(f"🔴 LINK LOSS: {elapsed:.1f}s without telemetry")
            await self._trigger_rtl(FailsafeReason.LINK_LOSS)

    async def _trigger_rtl(self, reason: FailsafeReason):
        """Trigger Return to Launch."""
        if self._rtl_triggered:
            return  # Already triggered once

        self._rtl_triggered = True
        logger.critical(f"⚠️ FAILSAFE TRIGGERED: {reason.value}")

        # Callback notification
        if self._on_failsafe_callback:
            try:
                if asyncio.iscoroutinefunction(self._on_failsafe_callback):
                    await self._on_failsafe_callback(reason)
                else:
                    self._on_failsafe_callback(reason)
            except Exception as e:
                logger.error(f"Failsafe callback error: {e}")

        # Execute RTL sequence
        try:
            logger.info("Executing RTL sequence...")

            # 1. Hold position first (safety)
            logger.info("Step 1: Hold position")
            await self.drone.hold_position()
            await asyncio.sleep(1.0)

            # 2. RTL command
            logger.info("Step 2: Return to launch")
            await self.drone.return_to_launch(reason.value)

            # 3. Wait for landing (max 60 seconds)
            logger.info("Step 3: Waiting for landing...")
            for i in range(60):
                telemetry = self.telemetry_collector.get_latest()
                if telemetry and telemetry.altitude_m < 0.5:
                    logger.info("✅ Landed safely")
                    break
                await asyncio.sleep(1.0)

            logger.info("✅ RTL sequence complete")

        except Exception as e:
            logger.error(f"RTL execution failed: {e}")


class LinkMonitor:
    """Lightweight link health monitor."""

    def __init__(self, timeout_sec: float = 3.0):
        self.timeout = timeout_sec
        self._last_heartbeat = time.time()
        self._link_lost = False

    def update_heartbeat(self):
        """Call when heartbeat/telemetry received."""
        self._last_heartbeat = time.time()
        self._link_lost = False

    def is_link_healthy(self) -> bool:
        """Check if link is still healthy."""
        elapsed = time.time() - self._last_heartbeat

        if elapsed > self.timeout and not self._link_lost:
            self._link_lost = True
            logger.warning(f"Link loss detected ({elapsed:.1f}s)")

        return elapsed < self.timeout

    def get_link_status(self) -> dict:
        """Get detailed link status."""
        elapsed = time.time() - self._last_heartbeat
        return {
            "healthy": self.is_link_healthy(),
            "elapsed_sec": elapsed,
            "timeout_sec": self.timeout,
        }


class BatteryMonitor:
    """Lightweight battery health monitor."""

    def __init__(
        self,
        warning_percent: float = 20.0,
        critical_percent: float = 5.0,
    ):
        self.warning = warning_percent
        self.critical = critical_percent
        self._last_level = 100.0

    def check(self, battery_percent: float) -> Optional[FailsafeReason]:
        """
        Check battery and return failsafe reason if needed.

        Returns:
            None if OK
            FailsafeReason if emergency
        """
        self._last_level = battery_percent

        if battery_percent < self.critical:
            return FailsafeReason.BATTERY_CRITICAL

        if battery_percent < self.warning:
            return FailsafeReason.BATTERY_LOW

        return None

    def get_battery_status(self) -> dict:
        """Get detailed battery status."""
        status = "OK"
        if self._last_level < self.critical:
            status = "CRITICAL"
        elif self._last_level < self.warning:
            status = "WARNING"

        return {
            "percent": self._last_level,
            "status": status,
            "warning_threshold": self.warning,
            "critical_threshold": self.critical,
        }
