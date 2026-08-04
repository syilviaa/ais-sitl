#!/usr/bin/env python3
"""Run local/RTSP CV and publish VisionEvent values to the dashboard."""

import argparse
import json
from pathlib import Path
import sys

import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.geo.geo_calculator import GeoCalculator  # noqa: E402
from src.backend.services.vision_contracts import VisionTelemetry  # noqa: E402
from src.vision.detector import (  # noqa: E402
    OpenCVVideoSource,
    UltralyticsBackend,
    VisionDetector,
)
from src.vision.pipeline import VisionPipeline  # noqa: E402


def publish_event(event, backend_url, session=requests):
    """Publish one canonical event and fail on a rejected response."""
    endpoint = f"{backend_url.rstrip('/')}/api/vision/events"
    response = session.post(endpoint, json=event.to_dict(), timeout=5)
    response.raise_for_status()
    return response.json()


def run(args):
    telemetry_payload = json.loads(
        Path(args.telemetry).read_text(encoding="utf-8")
    )
    telemetry = VisionTelemetry.from_dict(telemetry_payload)
    detector = VisionDetector(
        UltralyticsBackend(args.model, device=args.device),
        confidence_threshold=args.confidence,
    )
    pipeline = VisionPipeline(
        detector,
        GeoCalculator(),
        args.snapshots,
    )
    processed_frames = 0
    published_events = 0
    with OpenCVVideoSource(args.source) as video:
        iterator = iter(video)
        try:
            warmup_frame = next(iterator)
        except StopIteration as exc:
            raise RuntimeError("Video contains no readable frames") from exc
        detector.warmup(warmup_frame)

        for frame in iterator:
            if args.max_frames is not None and processed_frames >= args.max_frames:
                break
            events = pipeline.process_frame(frame, telemetry, args.source)
            processed_frames += 1
            for event in events:
                publish_event(event, args.backend_url)
                published_events += 1

    return {
        "processed_frames": processed_frames,
        "published_events": published_events,
        "last_timing": pipeline.last_timing,
        "snapshot_dir": str(Path(args.snapshots)),
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Local path or RTSP URL")
    parser.add_argument("--model", required=True, help="YOLO .pt model")
    parser.add_argument("--telemetry", required=True, help="Telemetry JSON")
    parser.add_argument(
        "--backend-url",
        default="http://127.0.0.1:5001",
    )
    parser.add_argument(
        "--snapshots",
        default="/private/tmp/ais-sitl-vision-snapshots",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--confidence", type=float, default=0.65)
    parser.add_argument("--max-frames", type=int)
    return parser


def main():
    report = run(build_parser().parse_args())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
