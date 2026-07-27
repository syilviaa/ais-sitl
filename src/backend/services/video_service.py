"""Gazebo camera relay: UDP H.264 (port 5600) → MJPEG for browser."""

from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from typing import Generator, Optional

logger = logging.getLogger(__name__)

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"


def find_gst_launch() -> Optional[str]:
    """Locate gst-launch-1.0 binary."""
    path_env = os.environ.get("PATH", "")
    extra_paths = "/opt/homebrew/bin:/usr/local/bin"
    if extra_paths not in path_env:
        os.environ["PATH"] = f"{extra_paths}:{path_env}"

    for candidate in (
        os.environ.get("GST_LAUNCH"),
        shutil.which("gst-launch-1.0"),
        "/opt/homebrew/bin/gst-launch-1.0",
        "/usr/local/bin/gst-launch-1.0",
    ):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def probe_udp_port(port: int, seconds: float = 1.0) -> int:
    """Count datagrams on a UDP port (best-effort)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    count = 0
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.settimeout(0.2)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                sock.recvfrom(65535)
                count += 1
            except socket.timeout:
                continue
    except OSError:
        return -1
    finally:
        sock.close()
    return count


class VideoRelay:
    """Decode Gazebo RTP/H.264 and expose latest JPEG frame."""

    def __init__(self, port: int = 5600):
        self.port = port
        self._gst: Optional[str] = find_gst_launch()
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest: Optional[bytes] = None
        self._running = False
        self._last_frame_at = 0.0
        self._error: Optional[str] = None

    def _ensure_gst(self) -> None:
        """Re-discover gst-launch after brew install without backend restart."""
        if self._gst is None:
            self._gst = find_gst_launch()

    @property
    def gstreamer_available(self) -> bool:
        self._ensure_gst()
        return self._gst is not None

    def status(self) -> dict:
        self._ensure_gst()
        packets = -1 if self._running else probe_udp_port(self.port, seconds=0.5)
        with self._lock:
            has_frame = self._latest is not None
            age = time.time() - self._last_frame_at if has_frame else None
        return {
            "gstreamer_available": self.gstreamer_available,
            "gstreamer_path": self._gst,
            "udp_port": self.port,
            "udp_packets_sample": packets,
            "relay_running": self._running,
            "has_frame": has_frame,
            "frame_age_s": round(age, 2) if age is not None else None,
            "error": self._error,
        }

    def start(self) -> bool:
        if self._running:
            return True
        self._ensure_gst()
        if not self._gst:
            self._error = (
                "GStreamer не установлен. "
                "brew install gstreamer gst-plugins-base gst-plugins-good "
                "gst-plugins-bad gst-libav"
            )
            return False

        args = [
            self._gst,
            "-e",
            "udpsrc",
            f"port={self.port}",
            "do-timestamp=true",
            "caps=application/x-rtp,media=(string)video,clock-rate=(int)90000,encoding-name=(string)H264,payload=(int)96",
            "!",
            "rtph264depay",
            "!",
            "avdec_h264",
            "!",
            "videoconvert",
            "!",
            "jpegenc",
            "quality=85",
            "!",
            "queue",
            "max-size-buffers=2",
            "leaky=downstream",
            "!",
            "fdsink",
            "fd=1",
            "sync=false",
            "async=false",
        ]
        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            self._error = str(exc)
            return False

        self._running = True
        self._error = None
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        threading.Thread(target=self._stderr_loop, daemon=True).start()
        logger.info("Video relay started on UDP %s", self.port)
        return True

    def stop(self) -> None:
        self._running = False
        if self._proc:
            self._proc.kill()
            self._proc.wait(timeout=2)
            self._proc = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        buffer = b""
        try:
            while self._running:
                chunk = self._proc.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while True:
                    start = buffer.find(SOI)
                    if start < 0:
                        buffer = b""
                        break
                    end = buffer.find(EOI, start + 2)
                    if end < 0:
                        buffer = buffer[start:]
                        break
                    frame = buffer[start : end + 2]
                    buffer = buffer[end + 2 :]
                    with self._lock:
                        self._latest = frame
                        self._last_frame_at = time.time()
        except Exception as exc:
            self._error = str(exc)
            logger.warning("Video relay read error: %s", exc)
        finally:
            self._running = False

    def _stderr_loop(self) -> None:
        assert self._proc and self._proc.stderr
        try:
            for line in self._proc.stderr:
                text = line.decode("utf-8", errors="replace").strip()
                if text and "ERROR" in text.upper():
                    logger.warning("gst-launch: %s", text)
                    self._error = text
        except Exception:
            pass

    def get_latest_frame(self) -> Optional[bytes]:
        with self._lock:
            return self._latest

    def ensure_running(self) -> bool:
        """Start relay if GStreamer available."""
        return self.start()

    def get_snapshot_jpeg(self) -> Optional[bytes]:
        """Latest JPEG frame, or None while the Gazebo stream is not ready."""
        self.ensure_running()
        return self.get_latest_frame()

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        """Yield multipart MJPEG chunks for Flask Response."""
        if not self.start():
            return
        boundary = b"frame"
        while self._running:
            frame = self.get_latest_frame()
            if frame is not None:
                yield (
                    b"--"
                    + boundary
                    + b"\r\nContent-Type: image/jpeg\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
            time.sleep(0.066)


_default_port = int(os.environ.get("VIDEO_UDP_PORT", "5600"))
video_relay = VideoRelay(port=_default_port)
