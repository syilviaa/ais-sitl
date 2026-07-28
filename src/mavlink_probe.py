"""
MAVLink probe utilities (TZ §2 — pymavlink alongside MAVSDK).

Listens for HEARTBEAT on a UDP port and estimates link RTT from
inter-message intervals (proxy for MAVLink frame timing).
"""

from __future__ import annotations

import logging
import socket
import time
from typing import Optional

logger = logging.getLogger(__name__)


def probe_mavlink_udp(
    host: str = "127.0.0.1",
    port: int = 14550,
    timeout_s: float = 2.0,
) -> dict:
    """
    Sample MAVLink traffic on UDP and return link statistics.

    Returns dict with keys: available, packets, avg_interval_ms, rtt_ok.
    """
    result = {
        "available": False,
        "packets": 0,
        "avg_interval_ms": None,
        "rtt_ok": None,
        "error": None,
    }
    try:
        from pymavlink import mavutil
    except ImportError as exc:
        result["error"] = str(exc)
        return result

    conn = None
    try:
        conn = mavutil.mavlink_connection(f"udpin:{host}:{port}")
        intervals: list[float] = []
        last_at: Optional[float] = None
        deadline = time.monotonic() + timeout_s

        while time.monotonic() < deadline:
            msg = conn.recv_match(blocking=True, timeout=0.3)
            if msg is None:
                continue
            now = time.monotonic()
            result["packets"] += 1
            if last_at is not None:
                intervals.append((now - last_at) * 1000.0)
            last_at = now
            if result["packets"] >= 5:
                break

        result["available"] = result["packets"] > 0
        if intervals:
            avg = sum(intervals) / len(intervals)
            result["avg_interval_ms"] = round(avg, 2)
            result["rtt_ok"] = avg < 50.0
    except (OSError, socket.error) as exc:
        result["error"] = str(exc)
    finally:
        if conn is not None and hasattr(conn, "close"):
            try:
                conn.close()
            except OSError:
                pass

    return result
