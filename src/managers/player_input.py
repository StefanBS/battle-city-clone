"""Per-player gameplay input encapsulation (keyboard or controller)."""

from enum import Enum, auto
from typing import Protocol

import pygame

from src.utils.constants import Direction

AXIS_DEADZONE: float = 0.5
"""Threshold on a normalized axis value (range [-1.0, 1.0]) above which the
stick is considered tilted in that direction."""

# pygame's CONTROLLERAXISMOTION events carry int16 values in [-32768, 32767].
AXIS_MAX = 32767


def normalize_axis(raw_value: int) -> float:
    """Normalize an SDL GameController axis int16 value to ``[-1.0, 1.0]``."""
    return raw_value / AXIS_MAX


class AxisState(Enum):
    NEGATIVE = auto()
    NEUTRAL = auto()
    POSITIVE = auto()


def classify_axis(raw_value: int) -> AxisState:
    value = normalize_axis(raw_value)
    if value < -AXIS_DEADZONE:
        return AxisState.NEGATIVE
    if value > AXIS_DEADZONE:
        return AxisState.POSITIVE
    return AxisState.NEUTRAL


KEY_TO_DIRECTION: dict[int, Direction] = {
    pygame.K_UP: Direction.UP,
    pygame.K_DOWN: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT,
}

CTRL_DPAD_BUTTONS: dict[int, Direction] = {
    pygame.CONTROLLER_BUTTON_DPAD_UP: Direction.UP,
    pygame.CONTROLLER_BUTTON_DPAD_DOWN: Direction.DOWN,
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: Direction.LEFT,
    pygame.CONTROLLER_BUTTON_DPAD_RIGHT: Direction.RIGHT,
}
CTRL_SHOOT_BUTTONS: tuple[int, ...] = (
    pygame.CONTROLLER_BUTTON_A,
    pygame.CONTROLLER_BUTTON_B,
)
CTRL_START_BUTTON: int = pygame.CONTROLLER_BUTTON_START

_CONTROLLER_EVENT_TYPES: tuple[int, ...] = (
    pygame.CONTROLLERBUTTONDOWN,
    pygame.CONTROLLERBUTTONUP,
    pygame.CONTROLLERAXISMOTION,
)


class PlayerInput(Protocol):
    def handle_event(self, event: pygame.event.Event) -> None: ...
    def get_movement_direction(self) -> tuple[int, int]: ...
    def consume_shoot(self) -> bool: ...
    def clear_pending_shoot(self) -> None: ...


class _DirectionalInput:
    def __init__(self) -> None:
        self._directions: dict[Direction, bool] = {
            Direction.UP: False,
            Direction.DOWN: False,
            Direction.LEFT: False,
            Direction.RIGHT: False,
        }
        self._shoot_pressed: bool = False

    def get_movement_direction(self) -> tuple[int, int]:
        dx = 0
        dy = 0
        for direction, pressed in self._directions.items():
            if pressed:
                ddx, ddy = direction.delta
                dx += ddx
                dy += ddy
        return (dx, dy)

    def consume_shoot(self) -> bool:
        if self._shoot_pressed:
            self._shoot_pressed = False
            return True
        return False

    def clear_pending_shoot(self) -> None:
        self._shoot_pressed = False


class KeyboardInput(_DirectionalInput):
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in KEY_TO_DIRECTION:
                self._directions[KEY_TO_DIRECTION[event.key]] = True
            if event.key == pygame.K_SPACE:
                self._shoot_pressed = True
        elif event.type == pygame.KEYUP:
            if event.key in KEY_TO_DIRECTION:
                self._directions[KEY_TO_DIRECTION[event.key]] = False


class ControllerInput(_DirectionalInput):
    def __init__(self, instance_id: int | None = None) -> None:
        super().__init__()
        self.instance_id = instance_id

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type not in _CONTROLLER_EVENT_TYPES:
            return
        if (
            self.instance_id is not None
            and getattr(event, "instance_id", None) != self.instance_id
        ):
            return

        if event.type == pygame.CONTROLLERBUTTONDOWN:
            if event.button in CTRL_DPAD_BUTTONS:
                direction = CTRL_DPAD_BUTTONS[event.button]
                self._directions[direction.opposite] = False
                self._directions[direction] = True
            elif event.button in CTRL_SHOOT_BUTTONS:
                self._shoot_pressed = True
        elif event.type == pygame.CONTROLLERBUTTONUP:
            if event.button in CTRL_DPAD_BUTTONS:
                self._directions[CTRL_DPAD_BUTTONS[event.button]] = False
        elif event.type == pygame.CONTROLLERAXISMOTION:
            if event.axis == pygame.CONTROLLER_AXIS_LEFTX:
                self._handle_axis(event.value, Direction.LEFT, Direction.RIGHT)
            elif event.axis == pygame.CONTROLLER_AXIS_LEFTY:
                self._handle_axis(event.value, Direction.UP, Direction.DOWN)

    def _handle_axis(
        self, raw_value: int, neg_dir: Direction, pos_dir: Direction
    ) -> None:
        state = classify_axis(raw_value)
        neg = state is AxisState.NEGATIVE
        pos = state is AxisState.POSITIVE
        if self._directions[neg_dir] == neg and self._directions[pos_dir] == pos:
            return
        self._directions[neg_dir] = neg
        self._directions[pos_dir] = pos


class CombinedInput:
    def __init__(self, inputs: list["PlayerInput"]) -> None:
        self._inputs = inputs

    def handle_event(self, event: pygame.event.Event) -> None:
        for inp in self._inputs:
            inp.handle_event(event)

    def get_movement_direction(self) -> tuple[int, int]:
        dx = 0
        dy = 0
        for inp in self._inputs:
            ddx, ddy = inp.get_movement_direction()
            dx += ddx
            dy += ddy
        return (dx, dy)

    def consume_shoot(self) -> bool:
        fired = False
        for inp in self._inputs:
            if inp.consume_shoot():
                fired = True
        return fired

    def clear_pending_shoot(self) -> None:
        for inp in self._inputs:
            inp.clear_pending_shoot()
