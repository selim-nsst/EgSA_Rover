from __future__ import annotations

import queue
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable

import websocket

from .protocol import ControlState, RoverTelemetry


@dataclass
class ConnectionEvent:
    kind: str
    message: str = ""
    telemetry: RoverTelemetry | None = None


class RoverClient:
    def __init__(self, events: "queue.Queue[ConnectionEvent]") -> None:
        self.events = events
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._sender: threading.Thread | None = None
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._running = threading.Event()
        self._connected = threading.Event()
        self._send_wake = threading.Event()
        self._state = ControlState()
        self._url = ""
        self._last_payload = ""
        self._last_sent_at = 0.0
        self._stop_frames = 0

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    def connect(self, host: str, port: int = 8765) -> None:
        self.disconnect()
        self._url = f"ws://{host}:{port}"
        self._last_payload = ""
        self._last_sent_at = 0.0
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def disconnect(self) -> None:
        if self._connected.is_set():
            self.send_stop()
            time.sleep(0.03)
        self._running.clear()
        self._send_wake.set()
        self._connected.clear()
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass

    def set_state(self, update: Callable[[ControlState], None]) -> None:
        with self._lock:
            update(self._state)
            self._state.stop_button = False
        self._send_wake.set()

    def send_stop(self) -> None:
        with self._lock:
            self._state.left_throttle = 0
            self._state.right_throttle = 0
            self._state.obstacle_avoidance = False
            self._state.obstacle_following = False
            self._stop_frames = 3
        self._send_wake.set()

    def _run(self) -> None:
        self.events.put(ConnectionEvent("status", f"Connecting to {self._url}"))
        self._ws = websocket.WebSocketApp(
            self._url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        try:
            self._ws.run_forever(
                ping_interval=None,
                reconnect=0,
                sockopt=((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),),
            )
        finally:
            self._connected.clear()
            self._running.clear()

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        try:
            ws.sock.settimeout(0.08)
        except Exception:
            pass
        self._connected.set()
        self.events.put(ConnectionEvent("connected", "Connected"))
        self._sender = threading.Thread(target=self._send_loop, daemon=True)
        self._sender.start()

    def _on_close(self, ws: websocket.WebSocketApp, status: int, message: str) -> None:
        self._connected.clear()
        detail = f"Disconnected ({status})" if status else "Disconnected"
        if message:
            detail += f": {message}"
        self.events.put(ConnectionEvent("disconnected", detail))

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        self.events.put(ConnectionEvent("error", str(error)))

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        if message.startswith("{"):
            telemetry = RoverTelemetry.from_message(message)
            if telemetry:
                self.events.put(ConnectionEvent("telemetry", telemetry=telemetry))
                return
        if message.startswith("pong"):
            return
        if "Name" in message:
            self.events.put(ConnectionEvent("status", message))

    def _send_loop(self) -> None:
        while self._running.is_set() and self._connected.is_set():
            with self._lock:
                if self._stop_frames > 0:
                    payload = self._state.stopped().to_json()
                    self._stop_frames -= 1
                    force = True
                else:
                    payload = self._state.to_json()
                    force = False
            now = time.monotonic()
            is_drive_active = '"K":0' not in payload or '"Q":0' not in payload
            interval = 0.03 if is_drive_active else 0.25
            if force or payload != self._last_payload or now - self._last_sent_at >= interval:
                self._send_now(payload)
            wait_time = 0.01 if is_drive_active else 0.05
            self._send_wake.wait(wait_time)
            self._send_wake.clear()

    def _send_now(self, payload: str) -> None:
        if not self._connected.is_set() or self._ws is None:
            return
        try:
            with self._send_lock:
                self._ws.send(payload)
                self._last_payload = payload
                self._last_sent_at = time.monotonic()
        except Exception as exc:
            self.events.put(ConnectionEvent("error", str(exc)))
