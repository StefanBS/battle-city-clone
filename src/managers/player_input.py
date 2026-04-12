"""Per-player gameplay input encapsulation (keyboard or controller)."""

from enum import Enum, auto
from typing import Dict, Optional

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


class InputSource(Enum):
    """Input source type for a player."""

    KEYBOARD = auto()
    CONTROLLER = auto()


class PlayerInput:
    """Encapsulates per-player gameplay input from a keyboard or controller.

    For KEYBOARD source, handles arrow keys for direction and SPACE to shoot.
    For CONTROLLER source, handles SDL GameController events filtered by the
    device's SDL instance_id.
    """

    def __init__(
        self,
        source: InputSource,
        instance_id: Optional[int] = None,
        *,
        exclusive: bool = False,
    ) -> None:
        """Initialize PlayerInput.

        Args:
            source: Whether this player uses KEYBOARD or CONTROLLER input.
            instance_id: SDL instance_id of the controller this player is
                bound to. Required when source is CONTROLLER. Ignored for
                KEYBOARD source (still stored so exclusive-mode keyboard
                players can be constructed without one).
            exclusive: When True, only events matching the assigned source
                type are processed and controller events are filtered by
                instance_id. Used in 2-player mode to prevent input crosstalk.
        """
        if source == InputSource.CONTROLLER and instance_id is None:
            raise ValueError("instance_id is required when source is CONTROLLER")
        self.source = source
        self.instance_id = instance_id
        self._exclusive = exclusive

        self._directions: Dict[Direction, bool] = {
            Direction.UP: False,
            Direction.DOWN: False,
            Direction.LEFT: False,
            Direction.RIGHT: False,
        }
        self._shoot_pressed: bool = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """Process a pygame event and update internal input state.

        In non-exclusive (1P) mode both keyboard and controller events drive
        the single player. In exclusive (2P) mode only the assigned source
        type is processed to prevent input crosstalk between players.

        Args:
            event: The pygame event to handle.
        """
        if self._exclusive:
            if self.source == InputSource.KEYBOARD:
                self._handle_keyboard_event(event)
            else:
                self._handle_controller_event(event)
        else:
            self._handle_keyboard_event(event)
            self._handle_controller_event(event)

    def get_movement_direction(self) -> tuple[int, int]:
        """Return the current movement direction as a (dx, dy) vector.

        Returns:
            A tuple (dx, dy) where each component is -1, 0, or 1.
        """
        dx = 0
        dy = 0
        for direction, pressed in self._directions.items():
            if pressed:
                ddx, ddy = direction.delta
                dx += ddx
                dy += ddy
        return (dx, dy)

    def consume_shoot(self) -> bool:
        """Return and clear the shoot flag.

        Returns:
            True if shoot was pressed since the last call, False otherwise.
        """
        if self._shoot_pressed:
            self._shoot_pressed = False
            return True
        return False

    def clear_pending_shoot(self) -> None:
        """Clear any pending shoot input without consuming it as a shot."""
        self._shoot_pressed = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_keyboard_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in KEY_TO_DIRECTION:
                self._directions[KEY_TO_DIRECTION[event.key]] = True
            if event.key == pygame.K_SPACE:
                self._shoot_pressed = True
        elif event.type == pygame.KEYUP:
            if event.key in KEY_TO_DIRECTION:
                self._directions[KEY_TO_DIRECTION[event.key]] = False

    def _event_belongs_to_this_player(self, event: pygame.event.Event) -> bool:
        """Return True if this controller event should drive this player.

        Returns False for non-controller events so the caller can skip its
        dispatch. In 1P (non-exclusive) mode any controller drives the single
        player; in 2P (exclusive) mode the event's instance_id must match
        this player's bound controller.
        """
        if event.type not in _CONTROLLER_EVENT_TYPES:
            return False
        if not self._exclusive:
            return True
        return getattr(event, "instance_id", None) == self.instance_id

    def _handle_controller_event(self, event: pygame.event.Event) -> None:
        """Handle SDL GameController events for this player."""
        if not self._event_belongs_to_this_player(event):
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
                direction = CTRL_DPAD_BUTTONS[event.button]
                self._directions[direction] = False

        elif event.type == pygame.CONTROLLERAXISMOTION:
            value = normalize_axis(event.value)
            if event.axis == pygame.CONTROLLER_AXIS_LEFTX:
                self._handle_axis(value, Direction.LEFT, Direction.RIGHT)
            elif event.axis == pygame.CONTROLLER_AXIS_LEFTY:
                self._handle_axis(value, Direction.UP, Direction.DOWN)

    def _handle_axis(
        self, value: float, neg_dir: Direction, pos_dir: Direction
    ) -> None:
        if value < -AXIS_DEADZONE:
            neg, pos = True, False
        elif value > AXIS_DEADZONE:
            neg, pos = False, True
        else:
            neg, pos = False, False
        if (
            self._directions[neg_dir] == neg
            and self._directions[pos_dir] == pos
        ):
            return
        self._directions[neg_dir] = neg
        self._directions[pos_dir] = pos
