"""In-memory store for the latest CV-annotated JPEG frame."""

from threading import Lock


class AnnotatedFrameStore:
    """Hold one MJPEG-ready annotated frame for dashboard playback."""

    def __init__(self):
        self._lock = Lock()
        self._jpeg = None
        self._updated_at = None
        self._frame_count = 0

    def update(self, jpeg_bytes):
        if not isinstance(jpeg_bytes, (bytes, bytearray)) or not jpeg_bytes:
            raise ValueError("jpeg_bytes must be a non-empty bytes payload")
        with self._lock:
            self._jpeg = bytes(jpeg_bytes)
            self._frame_count += 1
            from datetime import datetime, timezone

            self._updated_at = datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z")
        return self._frame_count

    def get(self):
        with self._lock:
            return self._jpeg

    def meta(self):
        with self._lock:
            return {
                "has_frame": self._jpeg is not None,
                "frame_count": self._frame_count,
                "updated_at": self._updated_at,
                "bytes": 0 if self._jpeg is None else len(self._jpeg),
            }

    def mjpeg_generator(self, boundary=b"frame", idle_sleep_s=0.05):
        """Yield multipart MJPEG chunks; repeats last frame while idle."""
        import time

        while True:
            jpeg = self.get()
            if jpeg is None:
                time.sleep(idle_sleep_s)
                continue
            yield (
                b"--" + boundary + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode("ascii") + b"\r\n\r\n"
                + jpeg + b"\r\n"
            )
            time.sleep(idle_sleep_s)
