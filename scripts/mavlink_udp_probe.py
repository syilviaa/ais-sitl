#!/usr/bin/env python3
"""Check whether MAVLink UDP packets reach a local port (PX4 → remote port)."""

import argparse
import socket
import sys
import time


def probe(port: int, seconds: float) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(0.5)
    count = 0
    sources = set()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        count += 1
        sources.add(addr)
    sock.close()
    print(f"port {port}: {count} datagram(s) in {seconds}s from {sorted(sources)}")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=14540)
    parser.add_argument("--seconds", type=float, default=3.0)
    args = parser.parse_args()
    count = probe(args.port, args.seconds)
    if count == 0:
        print(
            "No UDP on this port — PX4 traffic is not reaching the host "
            "(Docker network? wrong IP? start probe before MAVSDK).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
