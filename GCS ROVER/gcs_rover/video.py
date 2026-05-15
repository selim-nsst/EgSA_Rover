from __future__ import annotations

import io
import queue
import threading
import time

import requests
from PIL import Image


class MjpegStream:
    def __init__(self, frames: "queue.Queue[Image.Image]", events: "queue.Queue[str]") -> None:
        self.frames = frames
        self.events = events
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self._url = ""

    def start(self, host: str, port: int = 9000) -> None:
        self.stop()
        self._url = f"http://{host}:{port}/mjpg"
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()

    def _run(self) -> None:
        self.events.put(f"Opening camera stream {self._url}")
        buffer = b""
        try:
            with requests.get(self._url, stream=True, timeout=(3, 8)) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=4096):
                    if not self._running.is_set():
                        break
                    if not chunk:
                        continue
                    buffer += chunk
                    while True:
                        start = buffer.find(b"\xff\xd8")
                        end = buffer.find(b"\xff\xd9")
                        if start == -1 or end == -1 or end < start:
                            break
                        jpg = buffer[start : end + 2]
                        buffer = buffer[end + 2 :]
                        try:
                            frame = Image.open(io.BytesIO(jpg)).convert("RGB")
                            while self.frames.qsize() > 1:
                                self.frames.get_nowait()
                            self.frames.put_nowait(frame)
                        except Exception:
                            pass
        except Exception as exc:
            if self._running.is_set():
                self.events.put(f"Camera stream stopped: {exc}")
        finally:
            self._running.clear()
            time.sleep(0.2)
