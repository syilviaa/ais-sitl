"""PX4 SITL quadcopter control using MAVSDK."""

import asyncio
import inspect
import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

from src.mavsdk_import import (
    IMPORT_ERROR,
    MAVSDK_AVAILABLE,
    MissionItem,
    MissionPlan,
    System,
    resolve_mavsdk_server_path,
)

HAS_MAVSDK = MAVSDK_AVAILABLE


logger = logging.getLogger(__name__)


class DroneState(Enum):
    """Lifecycle states exposed by :class:`Drone`."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    READY = "ready"
    ARMED = "armed"
    AIRBORNE = "airborne"
    HOLDING = "holding"
    LANDING = "landing"
    RTL = "rtl"
    ERROR = "error"


@dataclass
class Position:
    """Global position reported by MAVSDK, in metres and degrees."""

    lat: Optional[float] = None
    lon: Optional[float] = None
    absolute_altitude_m: Optional[float] = None
    relative_altitude_m: Optional[float] = None


@dataclass
class Velocity:
    """NED velocity in metres per second."""

    vx: Optional[float] = None
    vy: Optional[float] = None
    vz: Optional[float] = None


@dataclass
class Attitude:
    """Euler attitude in degrees."""

    roll: Optional[float] = None
    pitch: Optional[float] = None
    yaw: Optional[float] = None


@dataclass
class TelemetrySnapshot:
    """Latest live telemetry, with ``None`` used for data not received yet."""

    timestamp: Optional[float] = None
    position: Position = None
    velocity: Velocity = None
    attitude: Attitude = None
    battery_percent: Optional[float] = None
    armed: Optional[bool] = None
    flight_mode: Optional[str] = None
    gps_status: Optional[str] = None
    satellites: Optional[int] = None

    def __post_init__(self) -> None:
        if self.position is None:
            self.position = Position()
        if self.velocity is None:
            self.velocity = Velocity()
        if self.attitude is None:
            self.attitude = Attitude()

    def to_dict(self) -> Dict[str, Any]:
        """Return the backwards-compatible flat telemetry representation."""
        result = asdict(self)
        result.update(result.pop("position"))
        result.update(result.pop("velocity"))
        result.update(result.pop("attitude"))
        result["alt"] = result["relative_altitude_m"]
        result["battery"] = result.pop("battery_percent")
        result["mode"] = result.pop("flight_mode")
        return result


class ConnectionError(Exception):
    """Raised when the PX4 SITL connection cannot be used."""


class DroneTimeoutError(Exception):
    """Raised when PX4 does not report an expected state in time."""


class InvalidStateError(Exception):
    """Raised when a command is unsafe for the current drone state."""


class MissionValidationError(Exception):
    """Raised when a mission is invalid or rejected by the geofence."""


class BatteryLowError(Exception):
    """Kept for compatibility with the documented public API."""


class LinkLossError(Exception):
    """Kept for compatibility with the documented public API."""


class Drone:
    """Safety-focused MAVSDK control interface restricted to local PX4 SITL."""

    MIN_TAKEOFF_ALTITUDE_M = 0.5
    MAX_TAKEOFF_ALTITUDE_M = 120.0
    TELEMETRY_HZ = 10.0

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 14540,
        sitl_port: int = 14580,
        system: Optional[Any] = None,
        geofence_validator: Optional[Any] = None,
        command_timeout_s: float = 30.0,
    ) -> None:
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ConnectionError(
                "Only local PX4 SITL endpoints are permitted"
            )
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("port must be a valid UDP port")
        if not isinstance(sitl_port, int) or not 1 <= sitl_port <= 65535:
            raise ValueError("sitl_port must be a valid UDP port")
        self.host = host
        self.port = port
        self.sitl_port = sitl_port
        self._injected_system = system is not None
        self._system = system
        self._mavsdk_proc: Optional[subprocess.Popen] = None
        self._mavsdk_log_path: Optional[str] = None
        self._mavsdk_log_handle: Optional[Any] = None
        self._grpc_port = 50051
        self._geofence_validator = geofence_validator
        self._command_timeout_s = command_timeout_s
        self._connected = False
        self._state = DroneState.DISCONNECTED
        self._lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None
        self._telemetry = TelemetrySnapshot()
        self._telemetry_callback: Optional[
            Callable[[Dict[str, Any]], Any]
        ] = None
        self._telemetry_tasks: List[asyncio.Task] = []
        self._callback_task: Optional[asyncio.Task] = None
        self._mission_task: Optional[asyncio.Task] = None
        self._mission_progress = {"current": 0, "total": 0}

    def _get_lock(self) -> asyncio.Lock:
        """Bind lock to the current running event loop."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    @property
    def state(self) -> DroneState:
        """Return the current controller state."""
        return self._state

    def is_connected(self) -> bool:
        """Return whether a local SITL connection has been established."""
        return self._connected

    def _bind_host(self) -> str:
        if self.host in {"127.0.0.1", "localhost", "::1"}:
            return "127.0.0.1"
        return self.host

    def connection_urls(self, prefer_listen: bool = False) -> List[str]:
        """MAVSDK connection URLs to try (initiate to PX4 onboard port first).

        PX4 onboard mavlink binds UDP ``sitl_port`` (14580) and sends TO
        ``port`` (14540). Passive listen on 14540 alone often never completes
        MAVSDK discovery — we must send heartbeats to 14580 first
        (``udp://127.0.0.1:14580`` client mode per MAVSDK docs).

        When a UDP probe already sees MAVLink on ``port`` (typical with
        ``px4io/px4-sitl`` on Docker Desktop), listen mode succeeds first.
        """
        host = self._bind_host()
        listen = f"udp://:{self.port}"
        initiate = f"udp://{host}:{self.sitl_port}"
        listen_in = f"udpin://0.0.0.0:{self.port}"
        if prefer_listen:
            return [listen, initiate, listen_in]
        return [initiate, listen, listen_in]

    @staticmethod
    def _probe_udp_port(port: int, seconds: float = 2.0) -> tuple[int, set[tuple[str, int]]]:
        """Count MAVLink datagrams reaching a local UDP port."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sources: set[tuple[str, int]] = set()
        count = 0
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sock.settimeout(0.25)
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                try:
                    _, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                count += 1
                sources.add(addr)
        except OSError as error:
            logger.warning(
                "UDP probe could not bind port %s (%s) — port may be in use",
                port,
                error,
            )
            return -1, sources
        finally:
            sock.close()
        return count, sources

    def _stop_mavsdk_server(self) -> None:
        if self._mavsdk_proc is not None:
            self._mavsdk_proc.kill()
            self._mavsdk_proc.wait(timeout=2)
            self._mavsdk_proc = None
        if self._mavsdk_log_handle is not None:
            self._mavsdk_log_handle.close()
            self._mavsdk_log_handle = None

    def _read_mavsdk_server_log(self) -> str:
        if not self._mavsdk_log_path or not os.path.isfile(self._mavsdk_log_path):
            return ""
        try:
            with open(self._mavsdk_log_path, encoding="utf-8", errors="replace") as handle:
                return handle.read()[-4000:]
        except OSError:
            return ""

    def _start_mavsdk_server(self, urls: List[str], grpc_port: int) -> None:
        """Launch mavsdk_server with stderr captured for diagnostics."""
        backend = resolve_mavsdk_server_path()
        if backend is None:
            raise ConnectionError(
                "mavsdk_server binary not found. Run ./scripts/setup-dev.sh "
                "or set MAVSDK_SERVER_PATH."
            )

        self._stop_mavsdk_server()
        log_fd, self._mavsdk_log_path = tempfile.mkstemp(
            prefix="mavsdk_server_", suffix=".log"
        )
        os.close(log_fd)
        self._mavsdk_log_handle = open(
            self._mavsdk_log_path, "w", encoding="utf-8"
        )

        args = [os.fspath(backend), "-p", str(grpc_port), *urls]
        logger.info("Starting mavsdk_server: %s", " ".join(args[1:]))
        self._mavsdk_proc = subprocess.Popen(
            args,
            stdout=self._mavsdk_log_handle,
            stderr=subprocess.STDOUT,
        )

    async def _try_connect(self, address: str, timeout_s: float, grpc_port: int) -> None:
        """Connect one MAVSDK endpoint and wait for PX4 heartbeat."""
        if self._injected_system:
            if self._system is None:
                raise ConnectionError("Injected MAVSDK system is missing")
            await self._system.connect(system_address=address)
        else:
            self._start_mavsdk_server([address], grpc_port)
            await asyncio.sleep(0.75)
            self._system = System(
                mavsdk_server_address="localhost",
                port=grpc_port,
            )
            await self._system.connect(system_address=None)

        await self._wait_for_stream(
            self._system.core.connection_state,
            lambda item: item.is_connected,
            timeout_s,
        )

    async def connect(self, timeout_s: float = 15.0) -> bool:
        """Connect to local PX4 SITL — initiate on sitl_port, then listen on port."""
        async with self._get_lock():
            if self._connected:
                return True

            if not self._injected_system:
                packet_count, sources = self._probe_udp_port(self.port, seconds=2.0)
                logger.info(
                    "MAVLink UDP probe on port %s: %s datagram(s) from %s",
                    self.port,
                    packet_count,
                    sorted(sources) if sources else "none",
                )
            else:
                packet_count, sources = 0, set()

            urls = self.connection_urls(prefer_listen=packet_count > 0)
            last_error: Optional[Exception] = None
            attempt_timeout = min(12.0, timeout_s)

            for index, address in enumerate(urls):
                grpc_port = self._grpc_port + index
                try:
                    logger.info("MAVSDK connect attempt %s: %s", index + 1, address)
                    await self._try_connect(address, attempt_timeout, grpc_port)
                    self._connected = True
                    self._state = DroneState.CONNECTED
                    self._start_telemetry_collection()
                    logger.info("Connected to PX4 SITL via %s", address)
                    return True
                except (asyncio.TimeoutError, Exception) as error:
                    last_error = error
                    server_log = self._read_mavsdk_server_log()
                    if server_log:
                        logger.warning(
                            "mavsdk_server log (attempt %s):\n%s",
                            index + 1,
                            server_log,
                        )
                    logger.warning(
                        "MAVSDK connect failed for %s: %s", address, error
                    )
                    if not self._injected_system:
                        self._stop_mavsdk_server()
                        self._system = None

            self._state = DroneState.ERROR
            probe_hint = (
                f"UDP probe saw {packet_count} datagram(s) on port {self.port}. "
                if packet_count
                else (
                    f"No UDP datagrams reached port {self.port} — if SITL runs in Docker, "
                    "use --network host or map UDP 14540 to the host. "
                )
            )
            if isinstance(last_error, asyncio.TimeoutError):
                raise DroneTimeoutError(
                    "Timed out waiting for PX4 MAVSDK discovery. "
                    f"{probe_hint}"
                    f"Tried: {', '.join(urls)}. "
                    "Restart PX4 SITL after backend connect failures (PX4 caches UDP peer)."
                ) from last_error
            if isinstance(last_error, (SystemExit, KeyboardInterrupt)):
                raise ConnectionError(
                    "MAVSDK server unavailable on this platform"
                ) from last_error
            message = str(last_error).strip() if last_error else "unknown error"
            raise ConnectionError(
                f"Could not connect to local PX4 SITL: {message}"
            ) from last_error

    async def disconnect(self) -> None:
        """Stop local subscriptions and mark the controller disconnected."""
        async with self._get_lock():
            await self.unsubscribe_telemetry()
            self._cancel_task(self._mission_task)
            self._mission_task = None
            self._connected = False
            self._state = DroneState.DISCONNECTED
            if not self._injected_system:
                self._stop_mavsdk_server()
                self._system = None

    async def wait_until_ready(self, timeout_s: float = 30.0) -> bool:
        """Wait until PX4 reports both a valid global GPS and home position."""
        self._require_connected()
        try:
            await self._wait_for_stream(
                self._system.telemetry.health,
                lambda health: (
                    health.is_global_position_ok and health.is_home_position_ok
                ),
                timeout_s,
            )
            await self._wait_for_stream(
                self._system.telemetry.home,
                lambda home: home is not None,
                timeout_s,
            )
        except asyncio.TimeoutError as error:
            raise DroneTimeoutError(
                "GPS or home position did not become ready"
            ) from error
        self._state = DroneState.READY
        return True

    async def arm(self, timeout_s: Optional[float] = None) -> bool:
        """Arm motors and wait until telemetry confirms the armed state."""
        async with self._get_lock():
            self._require_state(DroneState.READY)
            await self._system.action.arm()
            await self._wait_for_stream(
                self._system.telemetry.armed,
                lambda armed: armed,
                timeout_s or self._command_timeout_s,
            )
            self._state = DroneState.ARMED
            return True

    async def disarm(self, timeout_s: Optional[float] = None) -> bool:
        """Disarm motors and wait for telemetry confirmation."""
        async with self._get_lock():
            self._require_connected()
            await self._system.action.disarm()
            await self._wait_for_stream(
                self._system.telemetry.armed,
                lambda armed: not armed,
                timeout_s or self._command_timeout_s,
            )
            self._state = DroneState.READY
            return True

    async def takeoff(
        self, altitude_m: float, timeout_s: Optional[float] = None
    ) -> bool:
        """Take off to a valid relative altitude after arming."""
        if not isinstance(altitude_m, (float, int)) or isinstance(
            altitude_m, bool
        ):
            raise ValueError("altitude_m must be a number")
        if not (
            self.MIN_TAKEOFF_ALTITUDE_M
            <= altitude_m
            <= self.MAX_TAKEOFF_ALTITUDE_M
        ):
            raise ValueError("altitude_m must be between 0.5 and 120 metres")
        async with self._get_lock():
            self._require_state(DroneState.ARMED)
            await self._system.action.set_takeoff_altitude(float(altitude_m))
            await self._system.action.takeoff()
            try:
                await self._wait_for_stream(
                    self._system.telemetry.position,
                    lambda position: position.relative_altitude_m
                    >= altitude_m - 0.3,
                    timeout_s or self._command_timeout_s,
                )
            except asyncio.TimeoutError as error:
                self._state = DroneState.ERROR
                raise DroneTimeoutError(
                    "Target takeoff altitude was not reached"
                ) from error
            self._state = DroneState.AIRBORNE
            return True

    async def land(self, timeout_s: Optional[float] = None) -> bool:
        """Land and wait for PX4 telemetry to report motors disarmed."""
        async with self._get_lock():
            self._require_connected()
            self._state = DroneState.LANDING
            await self._system.action.land()
            try:
                await self._wait_for_stream(
                    self._system.telemetry.armed,
                    lambda armed: not armed,
                    timeout_s or self._command_timeout_s,
                )
            except asyncio.TimeoutError as error:
                self._state = DroneState.ERROR
                raise DroneTimeoutError(
                    "PX4 did not disarm after landing"
                ) from error
            self._state = DroneState.READY
            return True

    async def hold_position(self) -> bool:
        """Command PX4 to hold its current position."""
        async with self._get_lock():
            self._require_state(DroneState.AIRBORNE, DroneState.HOLDING)
            await self._system.action.hold()
            self._state = DroneState.HOLDING
            return True

    async def return_to_launch(self, reason: str = "operator request") -> bool:
        """Request PX4 return-to-launch; failsafe policy remains external."""
        async with self._get_lock():
            self._require_state(DroneState.AIRBORNE, DroneState.HOLDING)
            logger.warning("Return to launch requested: %s", reason)
            await self._system.action.return_to_launch()
            self._state = DroneState.RTL
            return True

    async def validate_mission(
        self, waypoints: List[Tuple[float, float, float]]
    ) -> bool:
        """Validate points through the external geofence dependency."""
        self._validate_waypoints(waypoints)
        validator = self._geofence_validator
        if validator is None:
            from .geofence import GeofenceValidator

            validator = GeofenceValidator()
            if not validator.load_nfz_zones():
                raise MissionValidationError(
                    "NFZ data could not be loaded; mission rejected"
                )
        elif getattr(validator, "loaded", True) is False:
            raise MissionValidationError(
                "NFZ data is unavailable; mission rejected"
            )
        result = validator.validate_mission(waypoints)
        if inspect.isawaitable(result):
            result = await result
        if not result:
            raise MissionValidationError(
                "Mission violates the configured geofence"
            )
        return True

    async def fly_mission(
        self, waypoints: List[Tuple[float, float, float]]
    ) -> bool:
        """Validate, upload, and start a MAVSDK mission, exposing progress."""
        self._require_connected()
        await self.validate_mission(waypoints)
        items = [
            MissionItem(
                latitude_deg=lat,
                longitude_deg=lon,
                relative_altitude_m=altitude,
                speed_m_s=5.0,
                is_fly_through=True,
                gimbal_pitch_deg=float("nan"),
                gimbal_yaw_deg=float("nan"),
                camera_action=MissionItem.CameraAction.NONE,
                loiter_time_s=float("nan"),
                camera_photo_interval_s=float("nan"),
                acceptance_radius_m=5.0,
                yaw_deg=float("nan"),
                camera_photo_distance_m=float("nan"),
                vehicle_action=MissionItem.VehicleAction.NONE,
            )
            for lat, lon, altitude in waypoints
        ]
        await self._system.mission.upload_mission(MissionPlan(items))
        self._mission_progress = {"current": 0, "total": len(items)}
        await self._system.mission.start_mission()
        self._cancel_task(self._mission_task)
        self._mission_task = asyncio.create_task(
            self._collect_mission_progress()
        )
        return True

    async def get_telemetry(self) -> Dict[str, Any]:
        """Return a flat snapshot derived from received MAVSDK telemetry."""
        return self._telemetry.to_dict()

    async def subscribe_telemetry(
        self, callback: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """Subscribe to live telemetry; callbacks are rate-limited to 10 Hz."""
        self._telemetry_callback = callback
        self._start_telemetry_collection()
        if self._callback_task is None or self._callback_task.done():
            self._callback_task = asyncio.create_task(
                self._publish_telemetry()
            )

    async def unsubscribe_telemetry(self) -> None:
        """Stop telemetry collection and callback delivery."""
        self._telemetry_callback = None
        self._cancel_task(self._callback_task)
        self._callback_task = None
        for task in self._telemetry_tasks:
            self._cancel_task(task)
        self._telemetry_tasks = []

    async def get_mission_progress(self) -> Dict[str, int]:
        """Return the latest mission item progress reported by MAVSDK."""
        return dict(self._mission_progress)

    def _require_connected(self) -> None:
        if not self._connected:
            raise ConnectionError("Not connected to local PX4 SITL")

    def _require_state(self, *states: DroneState) -> None:
        self._require_connected()
        if self._state not in states:
            names = ", ".join(state.name for state in states)
            message = "Expected state {}, got {}".format(
                names, self._state.name
            )
            raise InvalidStateError(message)

    async def _wait_for_stream(
        self,
        stream_factory: Callable[[], AsyncIterator[Any]],
        predicate: Callable[[Any], bool],
        timeout_s: float,
    ) -> Any:
        iterator = stream_factory().__aiter__()
        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError()
            item = await asyncio.wait_for(iterator.__anext__(), remaining)
            if predicate(item):
                return item

    def _start_telemetry_collection(self) -> None:
        if self._telemetry_tasks or not self._connected:
            return
        self._telemetry_tasks = [
            asyncio.create_task(self._consume_position()),
            asyncio.create_task(self._consume_velocity()),
            asyncio.create_task(self._consume_attitude()),
            asyncio.create_task(self._consume_battery()),
            asyncio.create_task(self._consume_armed()),
            asyncio.create_task(self._consume_mode()),
            asyncio.create_task(self._consume_gps()),
        ]

    async def _consume_position(self) -> None:
        async for item in self._system.telemetry.position():
            self._telemetry.position = Position(
                item.latitude_deg,
                item.longitude_deg,
                item.absolute_altitude_m,
                item.relative_altitude_m,
            )
            self._telemetry.timestamp = time.time()

    async def _consume_velocity(self) -> None:
        async for item in self._system.telemetry.velocity_ned():
            self._telemetry.velocity = Velocity(
                item.north_m_s,
                item.east_m_s,
                item.down_m_s,
            )
            self._telemetry.timestamp = time.time()

    async def _consume_attitude(self) -> None:
        async for item in self._system.telemetry.attitude_euler():
            self._telemetry.attitude = Attitude(
                item.roll_deg,
                item.pitch_deg,
                item.yaw_deg,
            )
            self._telemetry.timestamp = time.time()

    async def _consume_battery(self) -> None:
        async for item in self._system.telemetry.battery():
            self._telemetry.battery_percent = item.remaining_percent
            self._telemetry.timestamp = time.time()

    async def _consume_armed(self) -> None:
        async for item in self._system.telemetry.armed():
            self._telemetry.armed = item
            self._telemetry.timestamp = time.time()

    async def _consume_mode(self) -> None:
        async for item in self._system.telemetry.flight_mode():
            self._telemetry.flight_mode = str(item)
            self._telemetry.timestamp = time.time()

    async def _consume_gps(self) -> None:
        async for item in self._system.telemetry.gps_info():
            self._telemetry.gps_status = str(item.fix_type)
            self._telemetry.satellites = item.num_satellites
            self._telemetry.timestamp = time.time()

    async def _publish_telemetry(self) -> None:
        while self._telemetry_callback is not None:
            callback = self._telemetry_callback
            result = callback(await self.get_telemetry())
            if inspect.isawaitable(result):
                await result
            await asyncio.sleep(1.0 / self.TELEMETRY_HZ)

    async def _collect_mission_progress(self) -> None:
        async for progress in self._system.mission.mission_progress():
            self._mission_progress = {
                "current": progress.current,
                "total": progress.total,
            }

    @staticmethod
    def _cancel_task(task: Optional[asyncio.Task]) -> None:
        if task is not None and not task.done():
            task.cancel()

    @staticmethod
    def _validate_waypoints(
        waypoints: List[Tuple[float, float, float]]
    ) -> None:
        if not isinstance(waypoints, (list, tuple)):
            raise MissionValidationError(
                "Mission waypoints must be a list or tuple"
            )
        if len(waypoints) < 2:
            raise MissionValidationError(
                "Mission requires at least two waypoints"
            )
        for waypoint in waypoints:
            if not isinstance(waypoint, (list, tuple)):
                raise MissionValidationError(
                    "Each waypoint must be a list or tuple"
                )
            if len(waypoint) != 3:
                raise MissionValidationError(
                    "Each waypoint must be (lat, lon, altitude)"
                )
            lat, lon, altitude = waypoint
            if any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                for value in waypoint
            ):
                raise MissionValidationError(
                    "Waypoint coordinates must be numeric values"
                )
            if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
                raise MissionValidationError(
                    "Waypoint latitude or longitude is invalid"
                )
            if altitude < 0:
                raise MissionValidationError("Waypoint altitude is invalid")


class Plane(Drone):
    """Compatibility alias for :class:`Drone`."""
