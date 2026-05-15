# GCS ROVER

Professional laptop ground control station for the SunFounder Galaxy RVR firmware in this workspace.

## What it does

- Connects to the rover WebSocket control server at `ws://192.168.4.1:8765`.
- Displays the ESP32-CAM MJPEG stream from `http://192.168.4.1:9000/mjpg`.
- Shows battery voltage, ultrasonic distance, left/right IR obstacle telemetry.
- Controls motors with buttons or keyboard:
  - `W` / Up: forward
  - `S` / Down: reverse
  - `A` / Left: rotate left
  - `D` / Right: rotate right
  - `Space` or `Esc`: emergency stop
- Drive buttons are hold-to-drive and stop on release.
- Controls camera servo angle, camera lamp, obstacle avoidance, obstacle following, and voice-command text.
- Sends a heartbeat and repeated safe control frames while connected.

## Safety firmware

The matching rover firmware in `..\galaxy-rvr\galaxy-rvr.ino` includes a 500 ms app-control timeout. Upload that sketch to the rover so the motors stop automatically if control packets freeze or Wi-Fi drops while moving.

## How to use

1. Power the rover and connect the laptop Wi-Fi to `GalaxyRVR` with password `12345678`.
2. Run `GCS ROVER.exe` from `dist\GCS ROVER\`.
3. Keep the default IP `192.168.4.1`, then click `Connect Control`.
4. Click `Connect Video` when you want the live camera.

## Developer run

```powershell
.\.venv\Scripts\python.exe main.py
```

## Rebuild the EXE

```powershell
.\build_exe.ps1
```

The executable is created at:

```text
dist\GCS ROVER.exe
```
