"""
Failsafe Service - Emergency monitoring and RTL handling.

Provides:
- Battery monitoring
- Link loss detection
- RTL sequence execution
- Event logging
"""

import asyncio
import logging
from typing import Optional, Callable

from src.failsafe import FailsafeMonitor
from src.models import FailsafeReason

logger = logging.getLogger(__name__)


class FailsafeServiceAPI:
    """Service layer for failsafe operations."""

    def __init__(self, drone=None, telemetry_collector=None):
        """Initialize failsafe service."""
        self.drone = drone
        self.telemetry_collector = telemetry_collector
        self.monitor: Optional[FailsafeMonitor] = None
        self.event_callback: Optional[Callable] = None
        self.events: list = []
        self._running = False

    async def initialize(self, battery_warning: float = 20.0, battery_critical: float = 5.0):
        """Initialize failsafe monitor."""
        if not self.drone or not self.telemetry_collector:
            raise Exception("Drone and telemetry collector required")

        try:
            logger.info("Initializing failsafe monitor...")

            self.monitor = FailsafeMonitor(
                drone=self.drone,
                telemetry_collector=self.telemetry_collector,
                battery_warning_percent=battery_warning,
                battery_critical_percent=battery_critical,
                link_loss_timeout_sec=3.0,
            )

            async def on_failsafe(reason: FailsafeReason):
                """Handle failsafe event."""
                logger.critical(f"🚨 FAILSAFE: {reason.value}")

                # Log event
                event = {
                    "type": "failsafe",
                    "reason": reason.value,
                    "timestamp": asyncio.get_running_loop().time(),
                }
                self.events.append(event)

                # Broadcast to clients
                if self.event_callback:
                    try:
                        await self.event_callback(event)
                    except Exception as e:
                        logger.error(f"Event broadcast error: {e}")

            self.monitor.on_failsafe(on_failsafe)
            logger.info("✅ Failsafe monitor initialized")

        except Exception as e:
            logger.error(f"Initialization error: {e}")
            raise

    async def start(self):
        """Start failsafe monitoring."""
        if not self.monitor:
            raise Exception("Monitor not initialized")

        if self._running:
            return

        try:
            logger.info("Starting failsafe monitoring...")
            self._running = True
            await self.monitor.start()
            logger.info("✅ Failsafe monitoring started")
        except Exception as e:
            logger.error(f"Start error: {e}")
            self._running = False
            raise

    async def stop(self):
        """Stop failsafe monitoring."""
        if not self.monitor:
            return

        try:
            logger.info("Stopping failsafe monitoring...")
            self._running = False
            await self.monitor.stop()
            logger.info("✅ Failsafe monitoring stopped")
        except Exception as e:
            logger.error(f"Stop error: {e}")

    async def get_status(self) -> dict:
        """Get failsafe status."""
        if not self.monitor:
            return {
                "running": False,
                "events": [],
                "error": "Monitor not initialized",
            }

        return {
            "running": self._running,
            "battery_warning": self.monitor.battery_warning,
            "battery_critical": self.monitor.battery_critical,
            "link_loss_timeout": self.monitor.link_loss_timeout,
            "events_total": len(self.events),
            "recent_events": self.events[-5:] if self.events else [],
        }

    async def get_events(self, limit: int = 50) -> dict:
        """Get failsafe events."""
        return {
            "total": len(self.events),
            "events": self.events[-limit:],
        }

    async def set_event_callback(self, callback: Callable):
        """Set callback for failsafe events."""
        self.event_callback = callback

    def is_running(self) -> bool:
        """Check if failsafe monitoring is running."""
        return self._running
