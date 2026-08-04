"""Unit tests for CV benchmark calculations."""

import pytest

from scripts.benchmark_cv import (
    build_parser,
    calculate_fps,
    detect_device,
    run_benchmark,
)


def test_calculate_fps():
    assert calculate_fps(20, 2.5) == pytest.approx(8.0)


@pytest.mark.parametrize(
    ("processed_frames", "elapsed_seconds"),
    [(-1, 1.0), (1, 0.0), (1, -0.1)],
)
def test_calculate_fps_rejects_invalid_values(
    processed_frames,
    elapsed_seconds,
):
    with pytest.raises(ValueError):
        calculate_fps(processed_frames, elapsed_seconds)


def test_explicit_device_is_preserved():
    assert detect_device("cpu") == "cpu"
    assert detect_device("mps") == "mps"


def test_benchmark_uses_one_warmup_frame_by_default():
    args = build_parser().parse_args([
        "--source",
        "demo.mp4",
        "--model",
        "yolov8n.pt",
    ])

    assert args.warmup_frames == 1


def test_benchmark_rejects_missing_video_and_model(tmp_path):
    missing_video = tmp_path / "missing.mp4"
    missing_model = tmp_path / "missing.pt"

    with pytest.raises(FileNotFoundError, match="Video source"):
        run_benchmark(missing_video, missing_model, 1, "cpu")

    fake_video = tmp_path / "video.mp4"
    fake_video.write_bytes(b"not opened because model validation is first")
    with pytest.raises(FileNotFoundError, match="YOLO model"):
        run_benchmark(fake_video, missing_model, 1, "cpu")
