"""Учебная модель батареи — разряд в 5× медленнее PX4, расход при удержании."""

from __future__ import annotations

import time


class BatterySimulator:
    """Display battery for dashboard (independent of fast PX4 SITL drain)."""

    HOLD_MODES = frozenset({"hold", "loiter", "posctl", "position", "altctl"})
    FLIGHT_MODES = frozenset({"auto", "rtl", "takeoff", "mission", "offboard"})

    def __init__(self) -> None:
        self._percent = 100.0
        self._last_ts = time.monotonic()

    def reset(self, percent: float = 100.0) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self._last_ts = time.monotonic()

    def tick(
        self,
        armed: bool,
        mode: str,
        alt_m: float,
    ) -> float:
        now = time.monotonic()
        dt = max(0.0, now - self._last_ts)
        self._last_ts = now

        if not armed:
            return self._percent

        mode_key = (mode or "").lower().split(".")[-1]
        if mode_key in self.HOLD_MODES or (
            mode_key == "unknown" and alt_m > 0.5
        ):
            # Удержание / висение — заметный, но медленный расход
            rate = 0.032
        elif mode_key in self.FLIGHT_MODES or alt_m > 0.5:
            rate = 0.048
        else:
            rate = 0.012

        self._percent = max(0.0, self._percent - rate * dt)
        return round(self._percent, 1)
