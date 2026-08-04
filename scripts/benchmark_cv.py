#!/usr/bin/env python3
"""Measure real YOLO inference FPS on a local 1080p video."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vision.detector import UltralyticsBackend, VisionDetector  # noqa: E402


def detect_device(requested="auto"):
    """Resolve auto to CUDA, Apple MPS or CPU in priority order."""
    if requested != "auto":
        return requested

    import torch

    if torch.cuda.is_available():
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def calculate_fps(processed_frames, elapsed_seconds):
    """Return average processed frames per second."""
    if processed_frames < 0:
        raise ValueError("processed_frames cannot be negative")
    if elapsed_seconds <= 0:
        raise ValueError("elapsed_seconds must be positive")
    return processed_frames / elapsed_seconds


def run_benchmark(
    source,
    model_path,
    max_frames,
    device,
    confidence=0.65,
    warmup_frames=1,
):
    """Run detector inference without sleeping or playback throttling."""
    import cv2

    source_path = Path(source)
    model_file = Path(model_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Video source not found: {source_path}")
    if not model_file.is_file():
        raise FileNotFoundError(f"YOLO model not found: {model_file}")
    if max_frames <= 0:
        raise ValueError("max_frames must be positive")
    if warmup_frames < 0:
        raise ValueError("warmup_frames cannot be negative")

    selected_device = detect_device(device)
    load_started = perf_counter()
    detector = VisionDetector(
        backend=UltralyticsBackend(str(model_file), device=selected_device),
        confidence_threshold=confidence,
    )
    model_load_seconds = perf_counter() - load_started

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video source: {source_path}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    warmed_frames = 0
    warmup_started = perf_counter()
    while warmed_frames < warmup_frames:
        ok, frame = capture.read()
        if not ok:
            break
        detector.warmup(frame)
        warmed_frames += 1
    warmup_seconds = perf_counter() - warmup_started
    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

    processed_frames = 0
    total_detections = 0
    benchmark_started = perf_counter()
    try:
        while processed_frames < max_frames:
            ok, frame = capture.read()
            if not ok:
                break
            result = detector.detect(frame, source_id=str(source_path))
            processed_frames += 1
            total_detections += len(result.detections)
    finally:
        capture.release()
    elapsed_seconds = perf_counter() - benchmark_started

    if processed_frames == 0:
        raise RuntimeError("Video contains no readable frames")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "source": str(source_path),
        "model": str(model_file),
        "confidence_threshold": confidence,
        "device": selected_device,
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "python": platform.python_version(),
        "frame_width": width,
        "frame_height": height,
        "requested_max_frames": max_frames,
        "requested_warmup_frames": warmup_frames,
        "warmed_frames": warmed_frames,
        "processed_frames": processed_frames,
        "total_detections": total_detections,
        "model_load_seconds": round(model_load_seconds, 4),
        "warmup_seconds": round(warmup_seconds, 4),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "average_fps": round(
            calculate_fps(processed_frames, elapsed_seconds), 2
        ),
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Local video path")
    parser.add_argument("--model", required=True, help="YOLO .pt model path")
    parser.add_argument("--max-frames", type=int, default=100)
    parser.add_argument(
        "--device",
        default="auto",
        help="auto, cpu, mps or CUDA device such as 0",
    )
    parser.add_argument("--confidence", type=float, default=0.65)
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=1,
        help="Inference frames excluded from FPS measurement",
    )
    parser.add_argument("--output", help="Optional JSON report path")
    return parser


def main():
    args = build_parser().parse_args()
    report = run_benchmark(
        source=args.source,
        model_path=args.model,
        max_frames=args.max_frames,
        device=args.device,
        confidence=args.confidence,
        warmup_frames=args.warmup_frames,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
