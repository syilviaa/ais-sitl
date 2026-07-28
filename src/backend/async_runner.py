"""Single background asyncio loop for MAVSDK / drone coroutines."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_ready = threading.Event()


def ensure_loop() -> asyncio.AbstractEventLoop:
    """Start (if needed) and return the shared background event loop."""
    global _thread

    if _loop is not None and _loop.is_running():
        return _loop

    _ready.clear()

    def _run() -> None:
        global _loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _loop = loop
        _ready.set()
        logger.info("Background asyncio loop started (MAVSDK)")
        loop.run_forever()

    _thread = threading.Thread(target=_run, name="mavsdk-asyncio", daemon=True)
    _thread.start()

    if not _ready.wait(timeout=10):
        raise RuntimeError("Background asyncio loop failed to start")

    assert _loop is not None
    return _loop


def run_async(coro: Coroutine[Any, Any, T], timeout: float | None = 120) -> T:
    """Run a coroutine on the shared loop from a Flask/SocketIO thread."""
    loop = ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=timeout)
    except TimeoutError as exc:
        raise TimeoutError(
            f"Operation timed out after {timeout}s "
            "(PX4 SITL not responding or MAVSDK server unavailable)"
        ) from exc
    except Exception:
        logger.exception("Coroutine failed on MAVSDK event loop")
        future.cancel()
        raise


def schedule_coroutine(coro: Coroutine[Any, Any, Any]) -> asyncio.Future:
    """Fire-and-forget coroutine on the shared loop."""
    loop = ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop)
