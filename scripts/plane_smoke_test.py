"""Manual smoke test for an already-running local PX4 SITL instance."""

import asyncio
import logging

from src.autopilot.plane import Drone


async def run() -> None:
    """Execute the permitted local SITL flight sequence."""
    drone = Drone(host="127.0.0.1", port=14540)
    try:
        await drone.connect()
        await drone.wait_until_ready()
        await drone.arm()
        await drone.takeoff(5.0)
        await drone.hold_position()
        await drone.land()
    except Exception:
        logging.exception("Smoke test failed; attempting a safe PX4 command")
        try:
            if drone.state.name in {"AIRBORNE", "HOLDING"}:
                await drone.return_to_launch("smoke-test failure")
            elif drone.is_connected():
                await drone.land(timeout_s=10.0)
        finally:
            await drone.disconnect()
        raise
    await drone.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
