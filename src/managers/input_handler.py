"""Menu and system input, backed by the SDL GameController API."""

from typing import Optional

import pygame
from loguru import logger

from src.managers.player_input import (
    AXIS_DEADZONE,
    CTRL_DPAD_BUTTONS,
    KEY_TO_DIRECTION,
    normalize_axis,
)
from src.utils.constants import Direction, MenuAction

try:
    from pygame._sdl2 import controller as sdl_controller  # type: ignore
except ImportError:
    sdl_controller = None  # type: ignore


_DIRECTION_TO_MENU_ACTION: dict[Direction, MenuAction] = {
    Direction.UP: MenuAction.UP,
    Direction.DOWN: MenuAction.DOWN,
    Direction.LEFT: MenuAction.LEFT,
    Direction.RIGHT: MenuAction.RIGHT,
}

_CTRL_MENU_BUTTONS: dict[int, MenuAction] = {
    pygame.CONTROLLER_BUTTON_A: MenuAction.CONFIRM,
    pygame.CONTROLLER_BUTTON_B: MenuAction.BACK,
}

_CONFIRM_KEYS: tuple[int, ...] = (pygame.K_RETURN, pygame.K_r)


class InputHandler:
    """Handles keyboard and controller input for menus and system actions.

    Gameplay input (movement, shooting) is handled by PlayerInput via
    PlayerManager. This class opens every connected SDL GameController,
    tracks hot-plug, and produces MenuAction values for navigation.
    """

    def __init__(self) -> None:
        """Initialize the input handler and open any present controllers."""
        self._controllers: dict[int, "sdl_controller.Controller"] = {}
        self._menu_actions: list[MenuAction] = []
        self._axis_menu_h: Optional[MenuAction] = None
        self._axis_menu_v: Optional[MenuAction] = None
        self._init_controllers()

    # ------------------------------------------------------------------
    # Controller registry
    # ------------------------------------------------------------------

    def _init_controllers(self) -> None:
        """Open every connected device recognized as a game controller."""
        if sdl_controller is None:
            logger.warning(
                "pygame._sdl2.controller is unavailable; controller input disabled."
            )
            return
        sdl_controller.init()
        for device_index in range(pygame.joystick.get_count()):
            self._open_controller(device_index)

    def _open_controller(self, device_index: int) -> None:
        """Open a device as a game controller and register it by instance_id.

        Skips devices SDL doesn't recognize as game controllers (e.g. flight
        sticks, steering wheels) and is a no-op if the device's instance_id
        is already registered, which prevents handle leaks if SDL emits
        CONTROLLERDEVICEADDED more than once for the same device.
        """
        if sdl_controller is None:
            return
        if not sdl_controller.is_controller(device_index):
            logger.debug(
                f"Device {device_index} is not a game controller; skipping."
            )
            return
        ctrl = sdl_controller.Controller(device_index)
        ctrl.init()
        instance_id = ctrl.as_joystick().get_instance_id()
        if instance_id in self._controllers:
            ctrl.quit()
            return
        self._controllers[instance_id] = ctrl
        logger.info(
            f"Controller connected: {ctrl.name} "
            f"(device_index={device_index}, instance_id={instance_id})"
        )

    def _close_controller(self, instance_id: int) -> None:
        """Close the SDL handle and drop the controller from the registry."""
        ctrl = self._controllers.pop(instance_id, None)
        if ctrl is None:
            return
        logger.info(
            f"Controller disconnected: {ctrl.name} (instance_id={instance_id})"
        )
        ctrl.quit()

    @property
    def controller_instance_ids(self) -> list[int]:
        """Return instance_ids of every currently-open controller."""
        return list(self._controllers.keys())

    # ------------------------------------------------------------------
    # Event dispatch
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route a pygame event to the appropriate input source handler."""
        if event.type == pygame.KEYDOWN:
            self._handle_keyboard_event(event)
        elif event.type in (
            pygame.CONTROLLERDEVICEADDED,
            pygame.CONTROLLERDEVICEREMOVED,
        ):
            self._handle_device_event(event)
        elif event.type in (
            pygame.CONTROLLERBUTTONDOWN,
            pygame.CONTROLLERAXISMOTION,
        ):
            self._handle_controller_event(event)

    def _handle_keyboard_event(self, event: pygame.event.Event) -> None:
        direction = KEY_TO_DIRECTION.get(event.key)
        if direction is not None:
            self._menu_actions.append(_DIRECTION_TO_MENU_ACTION[direction])
        if event.key in _CONFIRM_KEYS:
            self._menu_actions.append(MenuAction.CONFIRM)

    def _handle_device_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.CONTROLLERDEVICEADDED:
            self._open_controller(event.device_index)
        elif event.type == pygame.CONTROLLERDEVICEREMOVED:
            self._close_controller(event.instance_id)

    def _handle_controller_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.CONTROLLERBUTTONDOWN:
            if event.button in CTRL_DPAD_BUTTONS:
                direction = CTRL_DPAD_BUTTONS[event.button]
                self._menu_actions.append(_DIRECTION_TO_MENU_ACTION[direction])
            elif event.button in _CTRL_MENU_BUTTONS:
                self._menu_actions.append(_CTRL_MENU_BUTTONS[event.button])
        elif event.type == pygame.CONTROLLERAXISMOTION:
            value = normalize_axis(event.value)
            if event.axis == pygame.CONTROLLER_AXIS_LEFTX:
                self._emit_axis_menu_action(
                    True, value, MenuAction.LEFT, MenuAction.RIGHT
                )
            elif event.axis == pygame.CONTROLLER_AXIS_LEFTY:
                self._emit_axis_menu_action(
                    False, value, MenuAction.UP, MenuAction.DOWN
                )

    def _emit_axis_menu_action(
        self,
        horizontal: bool,
        value: float,
        neg_action: MenuAction,
        pos_action: MenuAction,
    ) -> None:
        """Emit a menu action when an axis crosses the deadzone threshold."""
        if value < -AXIS_DEADZONE:
            new_state: Optional[MenuAction] = neg_action
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

    # ------------------------------------------------------------------
    # Menu action queue
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset menu action queue and axis edge-detection state."""
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
