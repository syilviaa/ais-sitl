"""
Telemetry Service - Real-time telemetry streaming for WebSocket.

Provides:
- 10 Hz telemetry collection
- WebSocket broadcast
- Client subscription management
- Telemetry history
"""

import asyncio
import logging
from typing import Optional, Callable, Set
from collections import deque

from src.telemetry import TelemetryCollector

logger = logging.getLogger(__name__)


class TelemetryServiceAPI:
    """Service layer for telemetry operations."""

    def __init__(self, mavsdk_system=None):
        """Initialize telemetry service."""
        self.collector = TelemetryCollector(
            system=mavsdk_system,
            rate_hz=10.0,
            history_size=100,
        )
        self.clients: Set[str] = set()
        self.broadcast_callback: Optional[Callable] = None
        self._running = False

    async def start(self):
        """Start telemetry collection."""
        if self._running:
            return

        try:
            logger.info("Starting telemetry service...")
            self._running = True

            # Start collector
            await self.collector.start()

            # Setup callback for broadcasting
            async def on_telemetry(snapshot):
                if self.broadcast_callback:
                    try:
                        await self.broadcast_callback(snapshot)
                    except Exception as e:
                        logger.error(f"Broadcast error: {e}")

            self.collector.on_telemetry(on_telemetry)
            logger.info("✅ Telemetry service started")

        except Exception as e:
            logger.error(f"Start error: {e}")
            self._running = False
            raise

    async def stop(self):
        """Stop telemetry collection."""
        try:
            logger.info("Stopping telemetry service...")
            self._running = False
            await self.collector.stop()
            logger.info("✅ Telemetry service stopped")
        except Exception as e:
            logger.error(f"Stop error: {e}")

    async def get_latest(self) -> dict:
        """Get latest telemetry snapshot."""
        try:
            snapshot = self.collector.get_latest()
            if snapshot:
                return snapshot.to_dict()
            return None
        except Exception as e:
            logger.error(f"Get latest error: {e}")
            raise

    async def get_history(self, count: int = 10) -> list:
        """Get telemetry history."""
        try:
            history = self.collector.get_history(count=count)
            return [
                s.to_dict() if s else None
                for s in history
            ]
        except Exception as e:
            logger.error(f"Get history error: {e}")
            raise

    async def get_statistics(self) -> dict:
        """Get telemetry collection statistics."""
        try:
            stats = self.collector.get_statistics()
            return {
                "update_count": stats.get("update_count", 0),
                "target_rate_hz": stats.get("target_rate_hz", 10.0),
                "actual_rate_hz": stats.get("actual_rate_hz", 0.0),
                "history_size": len(self.collector.get_history(count=100)),
            }
        except Exception as e:
            logger.error(f"Statistics error: {e}")
            return {}

    def register_client(self, client_id: str):
        """Register WebSocket client."""
        self.clients.add(client_id)
        logger.info(f"Client registered: {client_id} (total: {len(self.clients)})")

    def unregister_client(self, client_id: str):
        """Unregister WebSocket client."""
        self.clients.discard(client_id)
        logger.info(f"Client unregistered: {client_id} (total: {len(self.clients)})")

    def has_clients(self) -> bool:
        """Check if there are connected clients."""
        return len(self.clients) > 0

    async def set_broadcast_callback(self, callback: Callable):
        """Set callback for telemetry broadcast."""
        self.broadcast_callback = callback

    def is_running(self) -> bool:
        """Check if telemetry service is running."""
        return self._running
