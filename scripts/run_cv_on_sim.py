#!/usr/bin/env python3
"""Run CV on live Gazebo frames from the backend video relay.

Pulls JPEG snapshots from /api/video/snapshot, detects Person/Car/Truck,
publishes VisionEvent alerts, and overlays stay on /api/video/mjpeg in the UI.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.geo.geo_calculator import GeoCalculator  # noqa: E402
from src.backend.services.vision_contracts import VisionTelemetry  # noqa: E402
from src.vision.detector import UltralyticsBackend, VisionDetector  # noqa: E402
from src.vision.pipeline import VisionPipeline  # noqa: E402


def fetch_snapshot(backend_url: str, session: requests.Session, timeout=3.0):
    url = f"{backend_url.rstrip('/')}/api/video/snapshot"
    response = session.get(url, timeout=timeout)
    if response.status_code == 503:
        return None
    response.raise_for_status()
    arr = np.frombuffer(response.content, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame


def publish_event(event, backend_url, session):
    endpoint = f"{backend_url.rstrip('/')}/api/vision/events"
    response = session.post(endpoint, json=event.to_dict(), timeout=5)
    response.raise_for_status()


def run(args):
    telemetry = VisionTelemetry.from_dict(
        json.loads(Path(args.telemetry).read_text(encoding="utf-8"))
    )
    Path(args.snapshots).mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    detector = VisionDetector(
        UltralyticsBackend(args.model, device=args.device),
        confidence_threshold=args.confidence,
    )
    pipeline = VisionPipeline(
        detector,
        GeoCalculator(),
        args.snapshots,
    )

    print(
        f"Waiting for Gazebo frames at {args.backend_url}/api/video/snapshot ...",
        flush=True,
    )
    warmed = False
    processed = 0
    published = 0
    idle_rounds = 0

    while args.max_frames is None or processed < args.max_frames:
        try:
            frame = fetch_snapshot(args.backend_url, session)
        except requests.RequestException as exc:
            idle_rounds += 1
            if idle_rounds % 10 == 1:
                print(f"snapshot error: {exc}", flush=True)
            time.sleep(args.poll_s)
            continue

        if frame is None:
            idle_rounds += 1
            if idle_rounds % 10 == 1:
                print("no Gazebo frame yet (is PX4/Gazebo running?)", flush=True)
            time.sleep(args.poll_s)
            continue

        idle_rounds = 0
        if not warmed:
            detector.warmup(frame)
            warmed = True
            print(
                f"warmup ok, frame={frame.shape[1]}x{frame.shape[0]}",
                flush=True,
            )
            continue

        events = pipeline.process_frame(
            frame,
            telemetry,
            source_id="gazebo:/api/video/mjpeg",
        )
        processed += 1
        for event in events:
            publish_event(event, args.backend_url, session)
            published += 1
            print(
                f"alert {event.class_name} {event.confidence:.0%} "
                f"lat={event.latitude:.6f} lon={event.longitude:.6f}",
                flush=True,
            )
        if processed % 20 == 0:
            timing = pipeline.last_timing or {}
            print(
                f"processed={processed} published={published} "
                f"latency_ms={timing.get('latency_ms')}",
                flush=True,
            )
        time.sleep(args.poll_s)

    return {
        "processed_frames": processed,
        "published_events": published,
        "last_timing": pipeline.last_timing,
    }


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument(
        "--telemetry",
        default=str(ROOT / "config/vision/fixtures/telemetry_valid.json"),
    )
    p.add_argument("--backend-url", default="http://127.0.0.1:5001")
    p.add_argument("--snapshots", default=str(ROOT / "snapshots"))
    p.add_argument("--device", default="cpu")
    p.add_argument("--confidence", type=float, default=0.65)
    p.add_argument("--poll-s", type=float, default=0.2)
    p.add_argument("--max-frames", type=int)
    return p


def main():
    report = run(build_parser().parse_args())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
