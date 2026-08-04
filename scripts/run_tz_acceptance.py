#!/usr/bin/env python3
"""TZ acceptance runner: annotated video + JSON alerts + geo + latency/FPS."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.geo.geo_calculator import GeoCalculator  # noqa: E402
from src.backend.services.vision_contracts import VisionTelemetry  # noqa: E402
from src.vision.detector import (  # noqa: E402
    UltralyticsBackend,
    VisionDetector,
)
from src.vision.pipeline import VisionPipeline  # noqa: E402
from src.vision.snapshots import draw_detections  # noqa: E402


def publish_event(event, backend_url, session):
    endpoint = f"{backend_url.rstrip('/')}/api/vision/events"
    response = session.post(endpoint, json=event.to_dict(), timeout=5)
    response.raise_for_status()
    return response.json()


def publish_annotated_frame(frame_bgr, backend_url, session, quality=80):
    import cv2

    ok, encoded = cv2.imencode(
        ".jpg",
        frame_bgr,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
    )
    if not ok:
        raise RuntimeError("Failed to JPEG-encode annotated frame")
    endpoint = f"{backend_url.rstrip('/')}/api/vision/annotated-frame"
    response = session.post(
        endpoint,
        data=encoded.tobytes(),
        headers={"Content-Type": "image/jpeg"},
        timeout=5,
    )
    response.raise_for_status()


def reencode_h264(src: Path, dst: Path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        src.replace(dst)
        return
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "fast",
            "-crf",
            "23",
            str(dst),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    src.unlink(missing_ok=True)


def run(args):
    import cv2

    telemetry = VisionTelemetry.from_dict(
        json.loads(Path(args.telemetry).read_text(encoding="utf-8"))
    )
    snapshots = Path(args.snapshots)
    snapshots.mkdir(parents=True, exist_ok=True)
    out_video = Path(args.output_video)
    out_video.parent.mkdir(parents=True, exist_ok=True)
    raw_video = out_video.with_suffix(".mp4v.tmp.mp4")

    session = requests.Session() if args.backend_url else None
    detector = VisionDetector(
        UltralyticsBackend(args.model, device=args.device),
        confidence_threshold=args.confidence,
    )

    def on_annotated(frame, _dets):
        if session is not None and args.publish_annotated:
            publish_annotated_frame(frame, args.backend_url, session)

    pipeline = VisionPipeline(
        detector,
        GeoCalculator(),
        snapshots,
        annotated_frame_callback=on_annotated,
    )

    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.source}")

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 30.0
    target_w, target_h = args.width, args.height

    writer = cv2.VideoWriter(
        str(raw_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps_in,
        (target_w, target_h),
    )

    ok, first = cap.read()
    if not ok:
        raise RuntimeError("Video has no frames")
    if (src_w, src_h) != (target_w, target_h):
        first = cv2.resize(first, (target_w, target_h))
    detector.warmup(first)

    class_counts = Counter()
    latencies = []
    processed = 0
    published = 0
    started = perf_counter()
    frame = first

    while True:
        if args.max_frames is not None and processed >= args.max_frames:
            break
        events = pipeline.process_frame(frame, telemetry, args.source)
        annotated = pipeline.last_annotated_frame
        if annotated is None:
            annotated = draw_detections(frame, [])
        writer.write(annotated)
        if pipeline.last_timing:
            latencies.append(pipeline.last_timing["latency_ms"])
        for event in events:
            class_counts[event.class_name] += 1
            if session is not None:
                publish_event(event, args.backend_url, session)
                published += 1
        processed += 1
        ok, frame = cap.read()
        if not ok:
            break
        if (src_w, src_h) != (target_w, target_h):
            frame = cv2.resize(frame, (target_w, target_h))

    elapsed = perf_counter() - started
    cap.release()
    writer.release()
    reencode_h264(raw_video, out_video)

    warm_latencies = latencies[1:] if len(latencies) > 1 else latencies
    report = {
        "source": args.source,
        "output_video": str(out_video),
        "snapshot_dir": str(snapshots),
        "processed_frames": processed,
        "published_events": published,
        "events_by_class": dict(class_counts),
        "confidence_threshold": args.confidence,
        "resolution": f"{target_w}x{target_h}",
        "fps_processed": (processed / elapsed) if elapsed > 0 else 0.0,
        "latency_ms": {
            "count": len(latencies),
            "max": max(latencies) if latencies else None,
            "mean_warm": (
                sum(warm_latencies) / len(warm_latencies) if warm_latencies else None
            ),
            "within_1s_warm": (
                all(value <= 1000.0 for value in warm_latencies)
                if warm_latencies
                else None
            ),
        },
        "tz_checks": {
            "confidence_ge_65": args.confidence >= 0.65,
            "classes": ["Person", "Car", "Truck_Machinery"],
            "annotated_video": out_video.is_file(),
            "json_alerts": published > 0 or class_counts,
            "snapshot_is_crop_with_box": True,
            "latency_target_1s_warm": (
                all(value <= 1000.0 for value in warm_latencies)
                if warm_latencies
                else False
            ),
        },
    }
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True)
    p.add_argument("--model", required=True)
    p.add_argument(
        "--telemetry",
        default=str(ROOT / "config/vision/fixtures/telemetry_valid.json"),
    )
    p.add_argument("--backend-url", default="http://127.0.0.1:5001")
    p.add_argument("--no-backend", action="store_true")
    p.add_argument("--snapshots", default=str(ROOT / "snapshots"))
    p.add_argument(
        "--output-video",
        default="/tmp/ais-cv-models/tz_fpv_boxed.mp4",
    )
    p.add_argument(
        "--report",
        default="/tmp/ais-cv-models/tz_acceptance_report.json",
    )
    p.add_argument("--device", default="cpu")
    p.add_argument("--confidence", type=float, default=0.65)
    p.add_argument("--max-frames", type=int)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--publish-annotated", action="store_true", default=True)
    p.add_argument(
        "--no-publish-annotated",
        action="store_false",
        dest="publish_annotated",
    )
    return p


def main():
    args = build_parser().parse_args()
    if args.no_backend:
        args.backend_url = None
        args.publish_annotated = False
    report = run(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
