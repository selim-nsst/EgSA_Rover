from __future__ import annotations

import json
from dataclasses import dataclass, field


REGIONS = tuple(chr(ord("A") + index) for index in range(26))


@dataclass
class ControlState:
    servo_angle: int = 90
    obstacle_avoidance: bool = False
    obstacle_following: bool = False
    stop_button: bool = False
    speech: str = ""
    left_throttle: int = 0
    right_throttle: int = 0
    lamp: bool = False

    def clamp(self) -> None:
        self.servo_angle = max(0, min(140, int(self.servo_angle)))
        self.left_throttle = max(-100, min(100, int(self.left_throttle)))
        self.right_throttle = max(-100, min(100, int(self.right_throttle)))

    def to_regions(self) -> dict[str, object]:
        self.clamp()
        payload: dict[str, object] = {region: None for region in REGIONS}
        payload["D"] = self.servo_angle
        payload["E"] = self.obstacle_avoidance
        payload["F"] = self.obstacle_following
        payload["I"] = self.stop_button
        payload["J"] = self.speech
        payload["K"] = self.left_throttle
        payload["M"] = self.lamp
        payload["Q"] = self.right_throttle
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_regions(), separators=(",", ":"))

    def to_motion_json(self) -> str:
        self.clamp()
        payload: dict[str, object] = {region: None for region in REGIONS}
        payload["K"] = self.left_throttle
        payload["Q"] = self.right_throttle
        payload["I"] = self.stop_button
        return json.dumps(payload, separators=(",", ":"))

    def stopped(self) -> "ControlState":
        clone = ControlState(
            servo_angle=self.servo_angle,
            obstacle_avoidance=False,
            obstacle_following=False,
            stop_button=True,
            speech="",
            left_throttle=0,
            right_throttle=0,
            lamp=self.lamp,
        )
        clone.clamp()
        return clone


@dataclass
class RoverTelemetry:
    battery_voltage: float | None = None
    left_obstacle: bool | None = None
    right_obstacle: bool | None = None
    ultrasonic_cm: float | None = None
    speech_ack: bool = False
    raw: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_message(cls, message: str) -> "RoverTelemetry | None":
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        return cls(
            battery_voltage=_float_or_none(data.get("BV")),
            left_obstacle=_bool_or_none(data.get("N")),
            right_obstacle=_bool_or_none(data.get("P")),
            ultrasonic_cm=_float_or_none(data.get("O")),
            speech_ack=bool(data.get("J", False)),
            raw=data,
        )


def _float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)
