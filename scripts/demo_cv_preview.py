#!/usr/bin/env python3
"""Open a video window and draw live YOLO boxes (no backend needed)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vision.detector import UltralyticsBackend, VisionDetector  # noqa: E402


COLORS = {
    "Person": (40, 180, 40),
    "Car": (40, 160, 255),
    "Truck_Machinery": (0, 140, 255),
}


def draw_detections(frame, detections):
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det.bbox.to_list()]
        label = f"{det.class_name.value} {det.confidence:.0%}"
        color = COLORS.get(det.class_name.value, (0, 255, 0))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(annotated, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, y1), color, -1)
        cv2.putText(
            annotated,
            label,
            (x1 + 3, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
    return annotated


def run(args):
    detector = VisionDetector(
        UltralyticsBackend(args.model, device=args.device),
        confidence_threshold=args.confidence,
    )
    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.source}")

    writer = None
    raw_save_path = None
    if args.save:
        out_path = Path(args.save)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # OpenCV mp4v often shows as green static in QuickTime; write raw then
        # re-encode to H.264 yuv420p at the end when ffmpeg is available.
        raw_save_path = out_path.with_suffix(".mp4v.tmp.mp4")
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(
            str(raw_save_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (w, h),
        )

    ok, first = cap.read()
    if not ok:
        raise RuntimeError("Video has no frames")
    detector.warmup(first)
    frame = first
    processed = 0
    window = "CV demo — press q to quit"

    while True:
        result = detector.detect(frame)
        detections = result.detections
        annotated = draw_detections(frame, detections)
        count = len(detections)
        cv2.putText(
            annotated,
            f"detections: {count}  frame: {processed}",
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        if writer is not None:
            writer.write(annotated)
        if not args.headless:
            cv2.imshow(window, annotated)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
        processed += 1
        if args.max_frames is not None and processed >= args.max_frames:
            break
        ok, frame = cap.read()
        if not ok:
            if args.loop:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            if not ok:
                break

    cap.release()
    if writer is not None:
        writer.release()
        final_path = Path(args.save)
        if raw_save_path is not None:
            import shutil
            import subprocess

            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-i",
                        str(raw_save_path),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        "fast",
                        "-crf",
                        "23",
                        str(final_path),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                raw_save_path.unlink(missing_ok=True)
            else:
                raw_save_path.replace(final_path)
        print(f"saved: {args.save}")
    if not args.headless:
        cv2.destroyAllWindows()
    print(f"processed_frames={processed}")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, help="Video file path")
    p.add_argument("--model", required=True, help="YOLO .pt model")
    p.add_argument("--confidence", type=float, default=0.65)
    p.add_argument("--device", default="cpu")
    p.add_argument("--max-frames", type=int)
    p.add_argument("--loop", action="store_true", help="Replay video until q")
    p.add_argument("--save", help="Optional annotated mp4 path")
    p.add_argument(
        "--headless",
        action="store_true",
        help="No window; only write --save output",
    )
    return p


if __name__ == "__main__":
    run(build_parser().parse_args())
