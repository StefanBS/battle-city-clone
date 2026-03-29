import pygame
from typing import Tuple, Dict
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

    def get_movement_direction(self) -> Tuple[int, int]:
        """
        Get the current movement direction as a vector.

        Returns:
            A tuple (dx, dy) representing the movement direction
        """
        dx = 0
        dy = 0

        if self.directions[Direction.UP]:
            dy -= 1
        if self.directions[Direction.DOWN]:
            dy += 1
        if self.directions[Direction.LEFT]:
            dx -= 1
        if self.directions[Direction.RIGHT]:
            dx += 1

        return (dx, dy)

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
