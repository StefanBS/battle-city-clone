"""Per-player gameplay input encapsulation (keyboard or joystick)."""

from enum import Enum, auto
from typing import Dict, Optional

import pygame

from src.utils.constants import Direction

AXIS_DEADZONE: float = 0.5

# Raw joystick API (fallback for controllers not in SDL's GameController DB)
JOY_AXIS_X: int = 0
JOY_AXIS_Y: int = 1
JOY_SHOOT_BUTTONS: tuple[int, ...] = (0, 1)
JOY_START_BUTTON: int = 7

# SDL GameController API (normalized IDs for recognized controllers like Xbox)
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


class InputSource(Enum):
    """Input source type for a player."""

    KEYBOARD = auto()
    JOYSTICK = auto()


class PlayerInput:
    """Encapsulates per-player gameplay input from a keyboard or joystick.

    For KEYBOARD source, handles arrow keys for direction and SPACE to shoot.
    For JOYSTICK source, handles controller/joystick events filtered by
    joystick_index.
    """

    def __init__(self, source: InputSource, joystick_index: int = 0) -> None:
        """Initialize PlayerInput.

        Args:
            source: Whether this player uses KEYBOARD or JOYSTICK input.
            joystick_index: The joystick/controller index (only used when
                source is JOYSTICK).
        """
        self.source = source
        self.joystick_index = joystick_index

        self._directions: Dict[Direction, bool] = {
            Direction.UP: False,
            Direction.DOWN: False,
            Direction.LEFT: False,
            Direction.RIGHT: False,
        }
        self._shoot_pressed: bool = False

        self._key_mappings: Dict[int, Direction] = {
            pygame.K_UP: Direction.UP,
            pygame.K_DOWN: Direction.DOWN,
            pygame.K_LEFT: Direction.LEFT,
            pygame.K_RIGHT: Direction.RIGHT,
        }

    def handle_event(self, event: pygame.event.Event) -> None:
        """Process a pygame event and update internal input state.

        Keyboard source handles both keyboard and controller/joystick events
        (since a single player may use either input device). Joystick source
        handles only controller/joystick events filtered by joystick_index.

        Args:
            event: The pygame event to handle.
        """
        if self.source == InputSource.KEYBOARD:
            self._handle_keyboard_event(event)
            self._handle_joystick_event(event)
        else:
            self._handle_joystick_event(event)

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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_keyboard_event(self, event: pygame.event.Event) -> None:
        """Handle keyboard events (KEYDOWN / KEYUP)."""
        if event.type == pygame.KEYDOWN:
            if event.key in self._key_mappings:
                direction = self._key_mappings[event.key]
                self._directions[direction] = True
            if event.key == pygame.K_SPACE:
                self._shoot_pressed = True
        elif event.type == pygame.KEYUP:
            if event.key in self._key_mappings:
                direction = self._key_mappings[event.key]
                self._directions[direction] = False

    def _handle_joystick_event(self, event: pygame.event.Event) -> None:
        """Handle joystick/controller events filtered by joystick_index."""
        # --- SDL GameController API ---
        if event.type == pygame.CONTROLLERBUTTONDOWN:
            if getattr(event, "which", self.joystick_index) != self.joystick_index:
                return
            if event.button in CTRL_DPAD_BUTTONS:
                direction = CTRL_DPAD_BUTTONS[event.button]
                for d in self._directions:
                    self._directions[d] = False
                self._directions[direction] = True
            elif event.button in CTRL_SHOOT_BUTTONS:
                self._shoot_pressed = True

        elif event.type == pygame.CONTROLLERBUTTONUP:
            if getattr(event, "which", self.joystick_index) != self.joystick_index:
                return
            if event.button in CTRL_DPAD_BUTTONS:
                direction = CTRL_DPAD_BUTTONS[event.button]
                self._directions[direction] = False

        # --- Axis motion (CONTROLLER and raw JOY share axis indices 0/1) ---
        elif event.type in (pygame.CONTROLLERAXISMOTION, pygame.JOYAXISMOTION):
            joy_index = self._get_joy_index(event)
            if joy_index != self.joystick_index:
                return
            if event.axis in (pygame.CONTROLLER_AXIS_LEFTX, JOY_AXIS_X):
                self._handle_axis(event.value, Direction.LEFT, Direction.RIGHT)
            elif event.axis in (pygame.CONTROLLER_AXIS_LEFTY, JOY_AXIS_Y):
                self._handle_axis(event.value, Direction.UP, Direction.DOWN)

        # --- Raw joystick API ---
        elif event.type == pygame.JOYHATMOTION:
            if getattr(event, "joy", self.joystick_index) != self.joystick_index:
                return
            hat_x, hat_y = event.value
            for d in self._directions:
                self._directions[d] = False
            hat_dir: Optional[Direction] = None
            if hat_y > 0:
                hat_dir = Direction.UP
            elif hat_y < 0:
                hat_dir = Direction.DOWN
            elif hat_x > 0:
                hat_dir = Direction.RIGHT
            elif hat_x < 0:
                hat_dir = Direction.LEFT
            if hat_dir is not None:
                self._directions[hat_dir] = True

        elif event.type == pygame.JOYBUTTONDOWN:
            if getattr(event, "joy", self.joystick_index) != self.joystick_index:
                return
            if event.button in JOY_SHOOT_BUTTONS:
                self._shoot_pressed = True

    def _handle_axis(
        self, value: float, neg_dir: Direction, pos_dir: Direction
    ) -> None:
        """Update direction state for an axis value with deadzone.

        Args:
            value: The raw axis value in [-1.0, 1.0].
            neg_dir: Direction to activate when value < -deadzone.
            pos_dir: Direction to activate when value > +deadzone.
        """
        if value < -AXIS_DEADZONE:
            self._directions[neg_dir] = True
            self._directions[pos_dir] = False
        elif value > AXIS_DEADZONE:
            self._directions[pos_dir] = True
            self._directions[neg_dir] = False
        else:
            self._directions[neg_dir] = False
            self._directions[pos_dir] = False

    def _get_joy_index(self, event: pygame.event.Event) -> int:
        """Return the joystick index from a CONTROLLERAXISMOTION or JOYAXISMOTION event.

        CONTROLLERAXISMOTION uses ``which``; JOYAXISMOTION uses ``joy``.
        Falls back to own joystick_index when the attribute is missing
        (e.g. manually created test events).
        """
        if event.type == pygame.CONTROLLERAXISMOTION:
            return getattr(event, "which", self.joystick_index)
        return getattr(event, "joy", self.joystick_index)
