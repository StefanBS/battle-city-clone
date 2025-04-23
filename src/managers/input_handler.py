import pygame
from typing import Tuple, Dict
from loguru import logger


class InputHandler:
    """Handles keyboard input for the player tank."""

    def __init__(self) -> None:
        """Initialize the input handler."""
        self.directions: Dict[str, bool] = {
            "up": False,
            "down": False,
            "left": False,
            "right": False,
        }
        self.key_mappings: Dict[int, str] = {
            pygame.K_UP: "up",
            pygame.K_DOWN: "down",
            pygame.K_LEFT: "left",
            pygame.K_RIGHT: "right",
        }

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

        if self.directions["up"]:
            dy -= 1
        if self.directions["down"]:
            dy += 1
        if self.directions["left"]:
            dx -= 1
        if self.directions["right"]:
            dx += 1

        return (dx, dy)
