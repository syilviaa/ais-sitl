"""Unit tests for CV benchmark calculations."""

import pytest

from scripts.benchmark_cv import calculate_fps, detect_device


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
