"""
Drone Service - Wrapper around Drone class for REST API.

Provides high-level operations:
- Connection management
- Flight control (arm, takeoff, land, RTL)
- Mission execution
- Telemetry streaming
- State management
"""

import logging
import asyncio
from typing import Optional, Dict, Any

from src.autopilot.plane import Drone, DroneState

logger = logging.getLogger(__name__)


class DroneService:
    """Service layer for drone operations."""

    def __init__(self):
        """Initialize drone service."""
        self.drone: Optional[Drone] = None
        self._lock = asyncio.Lock()

    async def initialize(self, host: str = "127.0.0.1", port: int = 14540):
        """Initialize and connect to drone."""
        async with self._lock:
            if self.drone is not None:
                return True

            try:
                logger.info(f"Initializing Drone at {host}:{port}...")
                self.drone = Drone(host=host, port=port)

                if not await self.drone.connect():
                    raise Exception("Failed to connect to SITL")

                logger.info("✅ Drone initialized")
                return True

            except Exception as e:
                logger.error(f"❌ Initialization failed: {e}")
                self.drone = None
                raise

    async def disconnect(self):
        """Disconnect from drone."""
        async with self._lock:
            if self.drone:
                try:
                    await self.drone.disconnect()
                    logger.info("✅ Drone disconnected")
                except Exception as e:
                    logger.error(f"Disconnect error: {e}")
                finally:
                    self.drone = None

    async def get_status(self) -> Dict[str, Any]:
        """Get current drone status."""
        if not self.drone:
            return {
                "connected": False,
                "state": "disconnected",
                "error": "Drone not initialized",
            }

        try:
            telemetry = await self.drone.get_telemetry()
            return {
                "connected": self.drone.is_connected(),
                "state": self.drone.state.value,
                "telemetry": telemetry,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Status error: {e}")
            return {
                "connected": False,
                "state": "error",
                "error": str(e),
            }

    async def wait_until_ready(self, timeout_s: float = 30.0) -> bool:
        """Wait for drone to be ready (GPS + home position)."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            logger.info("Waiting for drone to be ready...")
            result = await self.drone.wait_until_ready(timeout_s=timeout_s)
            logger.info("✅ Drone ready")
            return result
        except Exception as e:
            logger.error(f"Ready timeout: {e}")
            raise

    async def arm(self) -> bool:
        """Arm motors."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            logger.info("Arming...")
            await self.drone.arm()
            logger.info("✅ Armed")
            return True
        except Exception as e:
            logger.error(f"Arm error: {e}")
            raise

    async def disarm(self) -> bool:
        """Disarm motors."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            logger.info("Disarming...")
            await self.drone.disarm()
            logger.info("✅ Disarmed")
            return True
        except Exception as e:
            logger.error(f"Disarm error: {e}")
            raise

    async def takeoff(self, altitude_m: float) -> bool:
        """Takeoff to altitude."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            logger.info(f"Taking off to {altitude_m}m...")
            await self.drone.takeoff(altitude_m)
            logger.info("✅ Takeoff complete")
            return True
        except Exception as e:
            logger.error(f"Takeoff error: {e}")
            raise

    async def land(self) -> bool:
        """Land at current position."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            logger.info("Landing...")
            await self.drone.land()
            logger.info("✅ Landed")
            return True
        except Exception as e:
            logger.error(f"Land error: {e}")
            raise

    async def hold_position(self) -> bool:
        """Hold position (hover)."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            logger.info("Holding position...")
            await self.drone.hold_position()
            logger.info("✅ Holding")
            return True
        except Exception as e:
            logger.error(f"Hold error: {e}")
            raise

    async def return_to_launch(self, reason: str = "api_request") -> bool:
        """Return to launch (RTL)."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            logger.info(f"Returning to launch (reason: {reason})...")
            await self.drone.return_to_launch(reason=reason)
            logger.info("✅ RTL initiated")
            return True
        except Exception as e:
            logger.error(f"RTL error: {e}")
            raise

    async def get_telemetry(self) -> Dict[str, Any]:
        """Get current telemetry snapshot."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            return await self.drone.get_telemetry()
        except Exception as e:
            logger.error(f"Telemetry error: {e}")
            raise

    async def subscribe_telemetry(self, callback, rate_hz: float = 10.0):
        """Subscribe to telemetry updates."""
        if not self.drone:
            raise Exception("Drone not initialized")

        try:
            await self.drone.subscribe_telemetry(callback, rate_hz=rate_hz)
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            raise

    async def unsubscribe_telemetry(self):
        """Unsubscribe from telemetry."""
        if not self.drone:
            return

        try:
            await self.drone.unsubscribe_telemetry()
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")

    def is_ready(self) -> bool:
        """Check if drone is ready for flight."""
        if not self.drone:
            return False
        return self.drone.state in [
            DroneState.READY,
            DroneState.ARMED,
            DroneState.AIRBORNE,
        ]

    def is_connected(self) -> bool:
        """Check if drone is connected."""
        return self.drone is not None and self.drone.is_connected()
