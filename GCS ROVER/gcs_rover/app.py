from __future__ import annotations

import queue
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from . import __app_name__, __version__
from .comms import ConnectionEvent, RoverClient
from .protocol import RoverTelemetry
from .video import MjpegStream


BG = "#0b1018"
PANEL = "#111927"
PANEL_2 = "#162235"
TEXT = "#e6edf7"
MUTED = "#8da2bd"
ACCENT = "#16c7b7"
WARN = "#ffcc66"
DANGER = "#ff5d73"
OK = "#63d471"


class RoverGCS(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{__app_name__} {__version__}")
        self.geometry("1280x780")
        self.minsize(1120, 700)
        self.configure(bg=BG)

        self.events: queue.Queue[ConnectionEvent] = queue.Queue()
        self.video_events: queue.Queue[str] = queue.Queue()
        self.frames: queue.Queue[Image.Image] = queue.Queue()
        self.client = RoverClient(self.events)
        self.video = MjpegStream(self.frames, self.video_events)

        self.host_var = tk.StringVar(value="192.168.4.1")
        self.ws_port_var = tk.IntVar(value=8765)
        self.cam_port_var = tk.IntVar(value=9000)
        self.status_var = tk.StringVar(value="Offline")
        self.mode_var = tk.StringVar(value="manual")
        self.speed_var = tk.IntVar(value=55)
        self.servo_var = tk.IntVar(value=90)
        self.lamp_var = tk.BooleanVar(value=False)
        self.left_power = tk.IntVar(value=0)
        self.right_power = tk.IntVar(value=0)

        self._keys: set[str] = set()
        self._keyboard_was_driving = False
        self._photo: ImageTk.PhotoImage | None = None
        self._last_telemetry = RoverTelemetry()

        self._setup_style()
        self._build()
        self._bind_controls()
        self.after(50, self._poll_events)
        self.after(20, self._drive_from_keys)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL, borderwidth=0)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground=TEXT)
        style.configure("Tile.TLabel", background=PANEL, font=("Segoe UI", 18, "bold"), foreground=TEXT)
        style.configure("TileName.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9, "bold"))
        style.configure("TButton", padding=(14, 8), background=PANEL_2, foreground=TEXT)
        style.map("TButton", background=[("active", "#20314a")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#061013")
        style.configure("Danger.TButton", background=DANGER, foreground="#130407")
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.configure("Horizontal.TScale", background=PANEL, troughcolor="#263752")

    def _build(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text="GCS ROVER", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Galaxy RVR laptop ground station", style="Muted.TLabel").pack(side="left", padx=14)
        ttk.Label(header, textvariable=self.status_var, foreground=ACCENT).pack(side="right")

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True, pady=(16, 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=360)
        body.rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)

    def _build_left(self, parent: ttk.Frame) -> None:
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        video_panel = ttk.Frame(left, style="Panel.TFrame", padding=12)
        video_panel.grid(row=0, column=0, sticky="nsew")
        video_panel.rowconfigure(1, weight=1)
        video_panel.columnconfigure(0, weight=1)
        ttk.Label(video_panel, text="Live Camera", background=PANEL, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.video_label = tk.Label(
            video_panel,
            text="Camera offline\nConnect video to view /mjpg",
            bg="#080d14",
            fg=MUTED,
            font=("Segoe UI", 18),
            bd=0,
        )
        self.video_label.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        telemetry = ttk.Frame(left)
        telemetry.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        for index in range(4):
            telemetry.columnconfigure(index, weight=1)
        self.battery_value = self._tile(telemetry, 0, "BATTERY", "-- V")
        self.distance_value = self._tile(telemetry, 1, "ULTRASONIC", "-- cm")
        self.left_obs_value = self._tile(telemetry, 2, "LEFT IR", "--")
        self.right_obs_value = self._tile(telemetry, 3, "RIGHT IR", "--")

    def _build_right(self, parent: ttk.Frame) -> None:
        right = ttk.Frame(parent, style="Panel.TFrame", padding=16)
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(right, text="Connection", background=PANEL, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        form = ttk.Frame(right, style="Panel.TFrame")
        form.pack(fill="x", pady=(10, 14))
        for index in range(3):
            form.columnconfigure(index, weight=1)
        self._entry(form, "Rover IP", self.host_var, 0, width=16)
        self._entry(form, "WS", self.ws_port_var, 1, width=7)
        self._entry(form, "Cam", self.cam_port_var, 2, width=7)
        row = ttk.Frame(right, style="Panel.TFrame")
        row.pack(fill="x", pady=(0, 12))
        ttk.Button(row, text="Connect Control", style="Accent.TButton", command=self.connect_control).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(row, text="Connect Video", command=self.connect_video).pack(side="left", fill="x", expand=True)
        ttk.Button(right, text="EMERGENCY STOP", style="Danger.TButton", command=self.stop).pack(fill="x", pady=(0, 16))

        self._section(right, "Drive")
        pad = ttk.Frame(right, style="Panel.TFrame")
        pad.pack(pady=(8, 10))
        self._drive_button(pad, "Forward", 65, 65).grid(row=0, column=1, padx=4, pady=4)
        self._drive_button(pad, "Left", -55, 55).grid(row=1, column=0, padx=4, pady=4)
        ttk.Button(pad, text="Stop", style="Danger.TButton", command=self.stop).grid(row=1, column=1, padx=4, pady=4)
        self._drive_button(pad, "Right", 55, -55).grid(row=1, column=2, padx=4, pady=4)
        self._drive_button(pad, "Back", -55, -55).grid(row=2, column=1, padx=4, pady=4)

        self._slider(right, "Speed limit", self.speed_var, 20, 100)
        self._slider(right, "Camera servo", self.servo_var, 0, 140, self.set_servo)

        bars = ttk.Frame(right, style="Panel.TFrame")
        bars.pack(fill="x", pady=(0, 12))
        self.left_bar = ttk.Progressbar(bars, maximum=200, value=100)
        self.right_bar = ttk.Progressbar(bars, maximum=200, value=100)
        ttk.Label(bars, text="Left motor", background=PANEL, style="Muted.TLabel").pack(anchor="w")
        self.left_bar.pack(fill="x", pady=(2, 8))
        ttk.Label(bars, text="Right motor", background=PANEL, style="Muted.TLabel").pack(anchor="w")
        self.right_bar.pack(fill="x", pady=(2, 0))

        self._section(right, "Mission Modes")
        ttk.Radiobutton(right, text="Manual control", value="manual", variable=self.mode_var, command=self.set_mode).pack(anchor="w", pady=2)
        ttk.Radiobutton(right, text="Obstacle avoidance", value="avoid", variable=self.mode_var, command=self.set_mode).pack(anchor="w", pady=2)
        ttk.Radiobutton(right, text="Obstacle following", value="follow", variable=self.mode_var, command=self.set_mode).pack(anchor="w", pady=2)
        ttk.Checkbutton(right, text="Camera lamp", variable=self.lamp_var, command=self.set_lamp).pack(anchor="w", pady=(8, 12))

        speech = ttk.Frame(right, style="Panel.TFrame")
        speech.pack(fill="x", pady=(0, 12))
        self.speech_var = tk.StringVar(value="forward")
        ttk.Entry(speech, textvariable=self.speech_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(speech, text="Send Voice Cmd", command=self.send_speech).pack(side="left")

        ttk.Label(right, text="Event Log", background=PANEL, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.log = tk.Text(right, height=8, bg="#0a0f17", fg=TEXT, insertbackground=TEXT, bd=0, padx=10, pady=8)
        self.log.pack(fill="both", expand=True, pady=(8, 0))

    def _tile(self, parent: ttk.Frame, column: int, title: str, value: str) -> ttk.Label:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(frame, text=title, style="TileName.TLabel").pack(anchor="w")
        label = ttk.Label(frame, text=value, style="Tile.TLabel")
        label.pack(anchor="w", pady=(4, 0))
        return label

    def _entry(self, parent: ttk.Frame, label: str, variable: tk.Variable, column: int, width: int) -> None:
        ttk.Label(parent, text=label, background=PANEL, style="Muted.TLabel").grid(row=0, column=column, sticky="w")
        ttk.Entry(parent, textvariable=variable, width=width).grid(row=1, column=column, sticky="ew", padx=(0, 8), pady=(4, 0))

    def _drive_button(self, parent: ttk.Frame, text: str, left: int, right: int) -> ttk.Button:
        button = ttk.Button(parent, text=text)
        button.bind("<ButtonPress-1>", lambda _: self.drive(left, right))
        button.bind("<ButtonRelease-1>", lambda _: self.stop())
        button.bind("<Leave>", lambda _: self.stop())
        return button

    def _section(self, parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text, background=PANEL, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(8, 0))

    def _slider(self, parent: ttk.Frame, label: str, variable: tk.IntVar, start: int, end: int, command=None) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill="x", pady=(6, 10))
        ttk.Label(frame, text=label, background=PANEL, style="Muted.TLabel").pack(anchor="w")
        ttk.Scale(frame, from_=start, to=end, variable=variable, command=lambda _: command() if command else None).pack(fill="x")

    def _bind_controls(self) -> None:
        self.bind("<KeyPress>", self._key_down)
        self.bind("<KeyRelease>", self._key_up)
        self.bind("<space>", lambda _: self.stop())
        self.bind("<Escape>", lambda _: self.stop())

    def connect_control(self) -> None:
        self.client.connect(self.host_var.get().strip(), int(self.ws_port_var.get()))

    def connect_video(self) -> None:
        self.video.start(self.host_var.get().strip(), int(self.cam_port_var.get()))
        self.after(80, self._poll_video)

    def drive(self, left: int, right: int) -> None:
        self.mode_var.set("manual")
        self.left_power.set(left)
        self.right_power.set(right)
        self.left_bar["value"] = left + 100
        self.right_bar["value"] = right + 100
        self.client.set_state(lambda state: self._apply_drive(state, left, right))

    def stop(self) -> None:
        self.left_power.set(0)
        self.right_power.set(0)
        self.left_bar["value"] = 100
        self.right_bar["value"] = 100
        self.mode_var.set("manual")
        self.client.send_stop()
        self._log("Stop command sent")

    def set_mode(self) -> None:
        mode = self.mode_var.get()
        self.client.set_state(
            lambda state: (
                setattr(state, "obstacle_avoidance", mode == "avoid"),
                setattr(state, "obstacle_following", mode == "follow"),
                setattr(state, "left_throttle", 0),
                setattr(state, "right_throttle", 0),
            )
        )
        self._log(f"Mode: {mode}")

    def set_servo(self) -> None:
        angle = int(self.servo_var.get())
        self.client.set_state(lambda state: setattr(state, "servo_angle", angle))

    def set_lamp(self) -> None:
        enabled = bool(self.lamp_var.get())
        self.client.set_state(lambda state: setattr(state, "lamp", enabled))
        self._log(f"Camera lamp {'on' if enabled else 'off'}")

    def send_speech(self) -> None:
        text = self.speech_var.get().strip()
        self.client.set_state(lambda state: setattr(state, "speech", text))
        self.after(350, lambda: self.client.set_state(lambda state: setattr(state, "speech", "")))
        self._log(f"Voice command: {text}")

    def _apply_drive(self, state, left: int, right: int) -> None:
        state.obstacle_avoidance = False
        state.obstacle_following = False
        state.left_throttle = left
        state.right_throttle = right

    def _key_down(self, event: tk.Event) -> None:
        self._keys.add(event.keysym.lower())

    def _key_up(self, event: tk.Event) -> None:
        self._keys.discard(event.keysym.lower())

    def _drive_from_keys(self) -> None:
        speed = int(self.speed_var.get())
        left = right = 0
        keys = self._keys
        if "w" in keys or "up" in keys:
            left += speed
            right += speed
        if "s" in keys or "down" in keys:
            left -= speed
            right -= speed
        if "a" in keys or "left" in keys:
            left -= speed
            right += speed
        if "d" in keys or "right" in keys:
            left += speed
            right -= speed
        left = max(-100, min(100, left))
        right = max(-100, min(100, right))
        keyboard_has_drive = any(key in keys for key in ("w", "a", "s", "d", "up", "down", "left", "right"))
        if keyboard_has_drive and (left != self.left_power.get() or right != self.right_power.get()):
            self.drive(left, right)
            self._keyboard_was_driving = True
        elif not keyboard_has_drive and self._keyboard_was_driving:
            self.drive(0, 0)
            self._keyboard_was_driving = False
        self.after(20, self._drive_from_keys)

    def _poll_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event.kind in {"connected", "disconnected", "error", "status"}:
                self.status_var.set(event.message)
                self._log(event.message)
            if event.kind == "telemetry" and event.telemetry:
                self._last_telemetry = event.telemetry
                self._update_telemetry(event.telemetry)
        while True:
            try:
                self._log(self.video_events.get_nowait())
            except queue.Empty:
                break
        self.after(80, self._poll_events)

    def _poll_video(self) -> None:
        try:
            frame = self.frames.get_nowait()
        except queue.Empty:
            if self.video._running.is_set():
                self.after(80, self._poll_video)
            return
        width = max(640, self.video_label.winfo_width())
        height = max(360, self.video_label.winfo_height())
        frame.thumbnail((width, height))
        canvas = Image.new("RGB", (width, height), "#080d14")
        x = (width - frame.width) // 2
        y = (height - frame.height) // 2
        canvas.paste(frame, (x, y))
        self._photo = ImageTk.PhotoImage(canvas)
        self.video_label.configure(image=self._photo, text="")
        self.after(35, self._poll_video)

    def _update_telemetry(self, telemetry: RoverTelemetry) -> None:
        self.battery_value.configure(text="-- V" if telemetry.battery_voltage is None else f"{telemetry.battery_voltage:.2f} V")
        self.distance_value.configure(text="-- cm" if telemetry.ultrasonic_cm is None else f"{telemetry.ultrasonic_cm:.1f} cm")
        self.left_obs_value.configure(text=_clear_text(telemetry.left_obstacle))
        self.right_obs_value.configure(text=_clear_text(telemetry.right_obstacle))

    def _log(self, message: str) -> None:
        if not message:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{stamp}] {message}\n")
        self.log.see("end")

    def _on_close(self) -> None:
        try:
            self.stop()
            self.video.stop()
            self.client.disconnect()
        finally:
            self.destroy()


def _clear_text(value: bool | None) -> str:
    if value is None:
        return "--"
    return "BLOCKED" if value else "Clear"


def main() -> None:
    try:
        app = RoverGCS()
        app.mainloop()
    except Exception as exc:
        messagebox.showerror("GCS ROVER", str(exc))
