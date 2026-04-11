import pygame
from typing import Optional
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
    """Handles keyboard and controller input for menus and system actions.

    Gameplay input (movement, shooting) is handled by PlayerInput via
    PlayerManager. This class handles menu navigation, pause, joystick
    hot-plug, and confirm keys.
    """

    def __init__(self) -> None:
        """Initialize the input handler."""
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

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle a pygame event to update menu and system input state.

        Handles keyboard, raw joystick (JOY*), and SDL GameController
        (CONTROLLER*) events for menu navigation and system actions.
        Gameplay input (movement, shooting) is handled by PlayerInput.

        Args:
            event: The pygame event to handle
        """
        if event.type == pygame.KEYDOWN:
            direction = {
                pygame.K_UP: Direction.UP,
                pygame.K_DOWN: Direction.DOWN,
                pygame.K_LEFT: Direction.LEFT,
                pygame.K_RIGHT: Direction.RIGHT,
            }.get(event.key)
            if direction is not None:
                self._menu_actions.append(_DIRECTION_TO_MENU_ACTION[direction])
            if event.key in _CONFIRM_KEYS:
                self._menu_actions.append(MenuAction.CONFIRM)

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

        # --- SDL GameController API (recognized controllers) ---
        elif event.type == pygame.CONTROLLERBUTTONDOWN:
            if event.button in CTRL_DPAD_BUTTONS:
                direction = CTRL_DPAD_BUTTONS[event.button]
                self._menu_actions.append(_DIRECTION_TO_MENU_ACTION[direction])
            elif event.button in CTRL_SHOOT_BUTTONS:
                self._menu_actions.append(MenuAction.CONFIRM)

        # --- Axis motion (shared: CONTROLLER_AXIS_LEFTX == 0, LEFTY == 1) ---
        elif event.type in (
            pygame.CONTROLLERAXISMOTION,
            pygame.JOYAXISMOTION,
        ):
            if event.axis in (pygame.CONTROLLER_AXIS_LEFTX, JOY_AXIS_X):
                self._emit_axis_menu_action(
                    True, event.value, MenuAction.LEFT, MenuAction.RIGHT
                )
            elif event.axis in (pygame.CONTROLLER_AXIS_LEFTY, JOY_AXIS_Y):
                self._emit_axis_menu_action(
                    False, event.value, MenuAction.UP, MenuAction.DOWN
                )

        # --- Raw joystick API (unrecognized controllers) ---
        elif event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
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
                self._menu_actions.append(_DIRECTION_TO_MENU_ACTION[hat_dir])
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button in JOY_SHOOT_BUTTONS:
                self._menu_actions.append(MenuAction.CONFIRM)

    def reset(self) -> None:
        """Reset all input state. Called between stages."""
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
