import pygame
from typing import Tuple


class InputHandler:
    """Handles keyboard input for the player tank."""

    def __init__(self):
        """Initialize the input handler."""
        self.directions = {"up": False, "down": False, "left": False, "right": False}
        self.key_mappings = {
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
                self.directions[self.key_mappings[event.key]] = True
        elif event.type == pygame.KEYUP:
            if event.key in self.key_mappings:
                self.directions[self.key_mappings[event.key]] = False

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
