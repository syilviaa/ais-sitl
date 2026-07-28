"""Safe MAVSDK import with Python 3.10+ compatibility."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any, Optional, Tuple

System: Any = None
MissionItem: Any = None
MissionPlan: Any = None
MAVSDK_AVAILABLE = False
IMPORT_ERROR: Optional[str] = None


def _patch_python_version_tuple_for_mavsdk() -> None:
    """MAVSDK uses float(version) < 3.6; broken for '3.10'→3.1 and '3.11'→3.11<3.6."""
    original = platform.python_version_tuple

    def patched() -> Tuple[str, ...]:
        major, minor, *_rest = original()
        if major == "3" and minor.isdigit() and int(minor) >= 10:
            # Must parse as >= 3.6, e.g. float("3.60") == 3.6
            return (major, "60", "0")
        return original()

    platform.python_version_tuple = patched  # type: ignore[method-assign]


def _load_mavsdk() -> None:
    global System, MissionItem, MissionPlan, MAVSDK_AVAILABLE, IMPORT_ERROR

    try:
        _patch_python_version_tuple_for_mavsdk()
        from mavsdk import System as _System
        from mavsdk.mission import MissionItem as _MissionItem, MissionPlan as _MissionPlan

        System = _System
        MissionItem = _MissionItem
        MissionPlan = _MissionPlan
        MAVSDK_AVAILABLE = True
    except BaseException as exc:
        IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


_load_mavsdk()

MavsdkServerHint = (
    "MAVSDK server binary missing for this platform (common on Mac ARM). "
    "Use Python 3.11, install mavsdk, and ensure PX4 SITL is running on UDP 14540."
)


def resolve_mavsdk_server_path() -> Optional[Path]:
    """Locate mavsdk_server: env override, pip bundle, or Homebrew."""
    override = os.environ.get("MAVSDK_SERVER_PATH", "").strip()
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path

    if MAVSDK_AVAILABLE:
        try:
            import mavsdk

            base = Path(mavsdk.__file__).resolve().parent / "bin"
            candidates = [
                base / "mavsdk_server",
                base / platform.machine() / "mavsdk_server",
                base / "arm64" / "mavsdk_server",
                base / "x86_64" / "mavsdk_server",
            ]
            for candidate in candidates:
                if candidate.is_file():
                    return candidate
        except Exception:
            pass

    for brew_path in (
        Path("/opt/homebrew/bin/mavsdk_server"),
        Path("/usr/local/bin/mavsdk_server"),
    ):
        if brew_path.is_file():
            return brew_path

    return None


def mavsdk_server_available() -> bool:
    """Return True when mavsdk_server can be launched on this platform."""
    if not MAVSDK_AVAILABLE:
        return False
    return resolve_mavsdk_server_path() is not None
