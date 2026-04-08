import pygame
from typing import Tuple, Dict, Optional
from loguru import logger
from src.utils.constants import Direction


class InputHandler:
    """Handles keyboard input for the player tank."""

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
        # Joystick state (tracked separately from keyboard)
        self.joy_directions: Dict[Direction, bool] = {
            Direction.UP: False,
            Direction.DOWN: False,
            Direction.LEFT: False,
            Direction.RIGHT: False,
        }
        self.joystick: Optional["pygame.joystick.JoystickType"] = None
        self._init_joystick()

    def _init_joystick(self) -> None:
        """Detect and initialize the first connected joystick."""
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            logger.info(f"Joystick connected: {self.joystick.get_name()}")

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Handle a pygame event to update input state.

        Args:
            event: The pygame event to handle
        """
        if event.type == pygame.KEYDOWN:
            if event.key in self.key_mappings:
                direction = self.key_mappings[event.key]
                if not self.directions[direction]:
                    logger.trace(f"Key down: {direction}")
                    self.directions[direction] = True
            if event.key == self.shoot_key:
                self.shoot_pressed = True
        elif event.type == pygame.KEYUP:
            if event.key in self.key_mappings:
                direction = self.key_mappings[event.key]
                if self.directions[direction]:
                    logger.trace(f"Key up: {direction}")
                    self.directions[direction] = False
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
        elif event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
            # Reset all joystick directions first
            for direction in self.joy_directions:
                self.joy_directions[direction] = False
            # Vertical takes priority (NES behavior) for diagonals
            if hat_y > 0:
                self.joy_directions[Direction.UP] = True
            elif hat_y < 0:
                self.joy_directions[Direction.DOWN] = True
            elif hat_x > 0:
                self.joy_directions[Direction.RIGHT] = True
            elif hat_x < 0:
                self.joy_directions[Direction.LEFT] = True

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
