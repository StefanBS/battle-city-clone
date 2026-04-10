import pygame
from typing import Tuple, Dict, Optional
from loguru import logger
from src.utils.constants import Direction, MenuAction

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

_DIRECTION_TO_MENU_ACTION: dict[Direction, MenuAction] = {
    Direction.UP: MenuAction.UP,
    Direction.DOWN: MenuAction.DOWN,
    Direction.LEFT: MenuAction.LEFT,
    Direction.RIGHT: MenuAction.RIGHT,
}

_CONFIRM_KEYS: tuple[int, ...] = (pygame.K_RETURN, pygame.K_r)


class InputHandler:
    """Handles keyboard and controller input for the player tank."""

    def __init__(self, shoot_key: int = pygame.K_SPACE) -> None:
        """Initialize the input handler."""
        self.directions: Dict[Direction, bool] = {
            Direction.UP: False,
            Direction.DOWN: False,
            Direction.LEFT: False,
            Direction.RIGHT: False,
        }
        self.key_mappings: Dict[int, Direction] = {
            pygame.K_UP: Direction.UP,
            pygame.K_DOWN: Direction.DOWN,
            pygame.K_LEFT: Direction.LEFT,
            pygame.K_RIGHT: Direction.RIGHT,
        }
        self.shoot_key: int = shoot_key
        self.shoot_pressed: bool = False
        # Joystick/controller state (tracked separately from keyboard)
        self.joy_directions: Dict[Direction, bool] = {
            Direction.UP: False,
            Direction.DOWN: False,
            Direction.LEFT: False,
            Direction.RIGHT: False,
        }
        self.joystick: Optional["pygame.joystick.JoystickType"] = None
        self._init_joystick()
        self._menu_actions: list[MenuAction] = []
        self._axis_menu_h: Optional[MenuAction] = None
        self._axis_menu_v: Optional[MenuAction] = None

    def _init_joystick(self) -> None:
        """Detect and initialize the first connected joystick."""
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            logger.info(f"Joystick connected: {self.joystick.get_name()}")

    def _emit_axis_menu_action(
        self,
        horizontal: bool,
        value: float,
        neg_action: MenuAction,
        pos_action: MenuAction,
    ) -> None:
        """Emit a menu action when an axis crosses the deadzone threshold."""
        if value < -AXIS_DEADZONE:
            new_state = neg_action
        elif value > AXIS_DEADZONE:
            new_state = pos_action
        else:
            new_state = None
        prev_state = self._axis_menu_h if horizontal else self._axis_menu_v
        if new_state != prev_state:
            if horizontal:
                self._axis_menu_h = new_state
            else:
                self._axis_menu_v = new_state
            if new_state is not None:
                self._menu_actions.append(new_state)

    def _handle_axis(
        self, value: float, neg_dir: Direction, pos_dir: Direction
    ) -> None:
        """Update joy_directions for an axis value with deadzone."""
        if value < -AXIS_DEADZONE:
            self.joy_directions[neg_dir] = True
            self.joy_directions[pos_dir] = False
        elif value > AXIS_DEADZONE:
            self.joy_directions[pos_dir] = True
            self.joy_directions[neg_dir] = False
        else:
            self.joy_directions[neg_dir] = False
            self.joy_directions[pos_dir] = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Handle a pygame event to update input state.

        Handles keyboard, raw joystick (JOY*), and SDL GameController
        (CONTROLLER*) events. Recognized controllers (Xbox, PlayStation)
        emit CONTROLLER* events; unrecognized ones emit JOY* events.

        Args:
            event: The pygame event to handle
        """
        if event.type == pygame.KEYDOWN:
            if event.key in self.key_mappings:
                direction = self.key_mappings[event.key]
                if not self.directions[direction]:
                    logger.trace(f"Key down: {direction}")
                    self.directions[direction] = True
                self._menu_actions.append(_DIRECTION_TO_MENU_ACTION[direction])
            if event.key == self.shoot_key:
                self.shoot_pressed = True
            if event.key in _CONFIRM_KEYS:
                self._menu_actions.append(MenuAction.CONFIRM)
        elif event.type == pygame.KEYUP:
            if event.key in self.key_mappings:
                direction = self.key_mappings[event.key]
                if self.directions[direction]:
                    logger.trace(f"Key up: {direction}")
                    self.directions[direction] = False

        # --- Hot-plug (shared by both APIs) ---
        elif event.type == pygame.JOYDEVICEADDED:
            if self.joystick is None:
                self.joystick = pygame.joystick.Joystick(event.device_index)
                self.joystick.init()
                logger.info(f"Joystick connected: {self.joystick.get_name()}")
        elif event.type == pygame.JOYDEVICEREMOVED:
            if (
                self.joystick is not None
                and event.instance_id == self.joystick.get_instance_id()
            ):
                logger.info(f"Joystick disconnected: {self.joystick.get_name()}")
                self.joystick = None
                for direction in self.joy_directions:
                    self.joy_directions[direction] = False

        # --- SDL GameController API (recognized controllers) ---
        elif event.type == pygame.CONTROLLERBUTTONDOWN:
            if event.button in CTRL_DPAD_BUTTONS:
                direction = CTRL_DPAD_BUTTONS[event.button]
                for d in self.joy_directions:
                    self.joy_directions[d] = False
                self.joy_directions[direction] = True
                self._menu_actions.append(_DIRECTION_TO_MENU_ACTION[direction])
            elif event.button in CTRL_SHOOT_BUTTONS:
                self.shoot_pressed = True
                self._menu_actions.append(MenuAction.CONFIRM)
        elif event.type == pygame.CONTROLLERBUTTONUP:
            if event.button in CTRL_DPAD_BUTTONS:
                direction = CTRL_DPAD_BUTTONS[event.button]
                self.joy_directions[direction] = False

        # --- Axis motion (shared: CONTROLLER_AXIS_LEFTX == 0, LEFTY == 1) ---
        elif event.type in (pygame.CONTROLLERAXISMOTION, pygame.JOYAXISMOTION):
            if event.axis in (pygame.CONTROLLER_AXIS_LEFTX, JOY_AXIS_X):
                self._handle_axis(event.value, Direction.LEFT, Direction.RIGHT)
                self._emit_axis_menu_action(
                    True, event.value, MenuAction.LEFT, MenuAction.RIGHT
                )
            elif event.axis in (pygame.CONTROLLER_AXIS_LEFTY, JOY_AXIS_Y):
                self._handle_axis(event.value, Direction.UP, Direction.DOWN)
                self._emit_axis_menu_action(
                    False, event.value, MenuAction.UP, MenuAction.DOWN
                )

        # --- Raw joystick API (unrecognized controllers) ---
        elif event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
            for d in self.joy_directions:
                self.joy_directions[d] = False
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
                self.joy_directions[hat_dir] = True
                self._menu_actions.append(_DIRECTION_TO_MENU_ACTION[hat_dir])
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button in JOY_SHOOT_BUTTONS:
                self.shoot_pressed = True
                self._menu_actions.append(MenuAction.CONFIRM)

    def get_movement_direction(self) -> Tuple[int, int]:
        """
        Get the current movement direction as a vector.

        Merges keyboard and joystick input (OR logic).

        Returns:
            A tuple (dx, dy) representing the movement direction
        """
        dx = 0
        dy = 0
        for direction, pressed in self.directions.items():
            if pressed:
                ddx, ddy = direction.delta
                dx += ddx
                dy += ddy
        for direction, pressed in self.joy_directions.items():
            if pressed:
                ddx, ddy = direction.delta
                dx += ddx
                dy += ddy
        return (dx, dy)

    def reset(self) -> None:
        """Reset all input state. Called between stages."""
        for direction in self.directions:
            self.directions[direction] = False
        for direction in self.joy_directions:
            self.joy_directions[direction] = False
        self.shoot_pressed = False
        self._menu_actions.clear()
        self._axis_menu_h = None
        self._axis_menu_v = None

    def consume_menu_actions(self) -> list[MenuAction]:
        """Return pending menu actions and clear the list."""
        if not self._menu_actions:
            return []
        actions = self._menu_actions
        self._menu_actions = []
        return actions

    def consume_shoot(self) -> bool:
        """
        Check if shoot was pressed and reset the flag.

        Returns:
            True if shoot was pressed since last check, False otherwise.
        """
        if self.shoot_pressed:
            self.shoot_pressed = False
            return True
        return False
