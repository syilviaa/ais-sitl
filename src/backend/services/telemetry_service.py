"""
Telemetry Service - Real-time telemetry streaming for WebSocket.

Provides:
- 10 Hz telemetry collection
- WebSocket broadcast
- Client subscription management
- Telemetry history
"""

import asyncio
import inspect
import json
import logging
import time
from typing import Optional, Callable, Set

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
        self._stop_event = asyncio.Event()
        self._last_broadcast_time = 0.0

    async def start(self):
        """Start telemetry collection."""
        if self._running:
            return

        try:
            logger.info("Starting telemetry service...")
            self._running = True

            # Setup callback for broadcasting
            async def on_telemetry(snapshot):
                await self._broadcast_snapshot(snapshot)

            self.collector.on_telemetry(on_telemetry)
            await self.collector.start()
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
            self._stop_event.set()
            await self.collector.stop()
            logger.info("✅ Telemetry service stopped")
        except Exception as e:
            logger.error(f"Stop error: {e}")

    async def run_forever(self):
        """Keep the collector on a dedicated background event loop."""
        await self.start()
        await self._stop_event.wait()

    async def get_latest(self) -> dict:
        """Get latest telemetry snapshot."""
        try:
            snapshot = self.collector.get_latest()
            if snapshot:
                return snapshot.to_api_dict()
            return None
        except Exception as e:
            logger.error(f"Get latest error: {e}")
            raise

    async def get_history(self, count: int = 10) -> list:
        """Get telemetry history."""
        try:
            history = self.collector.get_history(count=count)
            return [
                s.to_api_dict() if s else None
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
                "update_count": stats.get("update_count", stats.get("updates", 0)),
                "target_rate_hz": stats.get("target_rate_hz", 10.0),
                "actual_rate_hz": stats.get("actual_rate_hz", 0.0),
                "avg_latency_ms": stats.get("avg_latency_ms", 0.0),
                "max_latency_ms": stats.get("max_latency_ms", 0.0),
                "rtt_target_ms": stats.get("rtt_target_ms", 50.0),
                "rtt_ok": stats.get("rtt_ok", True),
                "history_size": len(self.collector.get_history(count=100)),
            }
        except Exception as e:
            logger.error(f"Statistics error: {e}")
            return {}

    def register_client(self, client_id: str):
        """Register WebSocket client."""
        self.clients.add(client_id)
        logger.info(
            f"Client registered: {client_id} (total: {len(self.clients)})"
        )

    def unregister_client(self, client_id: str):
        """Unregister WebSocket client."""
        self.clients.discard(client_id)
        logger.info(
            f"Client unregistered: {client_id} (total: {len(self.clients)})"
        )

    def has_clients(self) -> bool:
        """Check if there are connected clients."""
        return len(self.clients) > 0

    def set_broadcast_callback(self, callback: Callable):
        """Set callback for telemetry broadcast."""
        self.broadcast_callback = callback

    def is_running(self) -> bool:
        """Check if telemetry service is running."""
        return self._running

    async def _broadcast_snapshot(self, snapshot) -> None:
        """Broadcast a received snapshot at no more than 10 Hz."""
        if not self.broadcast_callback or not self.has_clients():
            return
        now = time.monotonic()
        if now - self._last_broadcast_time < 0.1:
            return
        payload = (
            snapshot if isinstance(snapshot, dict) else snapshot.to_dict()
        )
        try:
            payload = json.loads(json.dumps(payload, allow_nan=False))
            result = self.broadcast_callback(payload)
            if inspect.isawaitable(result):
                await result
            self._last_broadcast_time = now
        except (TypeError, ValueError, AttributeError) as error:
            logger.error("Telemetry broadcast skipped: %s", error)
