"""PX4 SITL readiness checks for dashboard initialize."""

from __future__ import annotations

import socket
import subprocess
import time
from typing import Optional


def _docker_container_running(name: str = "ais-px4-gazebo") -> bool:
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip().lower() == "true"
    except (OSError, subprocess.TimeoutExpired):
        return False


def _udp_packet_count(port: int, seconds: float = 1.5) -> int:
    """Count datagrams on a UDP port without holding it long."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    count = 0
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.settimeout(0.25)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                sock.recvfrom(4096)
                count += 1
            except socket.timeout:
                continue
    except OSError:
        return -1
    finally:
        sock.close()
    return count


def _port_in_use(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def check_sitl_ready(container: str = "ais-px4-gazebo") -> dict:
    """
    Quick SITL health before MAVSDK connect.

    Returns dict: ready, docker_running, mavlink_packets, hints.
    """
    hints: list[str] = []
    docker_ok = _docker_container_running(container)

    if not docker_ok:
        hints.append(
            f"Контейнер {container} не запущен. "
            "Выполните: ./scripts/start-px4-gazebo.sh"
        )

    # GCS port 14550 is published and usually free on the host
    mavlink_gcs = _udp_packet_count(14550, seconds=2.0)
    if mavlink_gcs == -1:
        hints.append("Порт UDP 14550 занят — закройте QGroundControl или другой GCS.")
    elif mavlink_gcs == 0 and docker_ok:
        hints.append(
            "PX4 ещё загружается или MAVLink не доходит до хоста. "
            "Подождите 20–30 с после start-px4-gazebo.sh."
        )

    if _port_in_use(14540):
        hints.append(
            "Порт 14540 занят (часто stale mavsdk_server). "
            "Перезапустите backend: ./scripts/start-backend.sh"
        )

    ready = docker_ok and mavlink_gcs > 0
    return {
        "ready": ready,
        "docker_running": docker_ok,
        "container": container,
        "mavlink_packets_gcs_port": mavlink_gcs,
        "port_14540_in_use": _port_in_use(14540),
        "hints": hints,
    }
