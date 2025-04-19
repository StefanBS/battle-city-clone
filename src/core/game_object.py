"""
Base GameObject class for all game entities.
"""

from typing import Tuple, Optional
import pygame


class GameObject:
    """Base class for all game entities."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        sprite: Optional[pygame.Surface] = None,
    ):
        """
        Initialize a game object.

        Args:
            x: X coordinate
            y: Y coordinate
            width: Width of the object
            height: Height of the object
            sprite: Optional sprite surface
        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.sprite = sprite
        self.rect = pygame.Rect(x, y, width, height)

    def update(self, dt: float) -> None:
        """
        Update the game object's state.

        Args:
            dt: Time elapsed since last update in seconds
        """
        self.rect.x = self.x
        self.rect.y = self.y

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the game object on the given surface.

        Args:
            surface: Surface to draw on
        """
        if self.sprite:
            surface.blit(self.sprite, self.rect)
        else:
            pygame.draw.rect(surface, (255, 0, 0), self.rect)  # Debug red rectangle

    def get_position(self) -> Tuple[int, int]:
        """Get the current position of the object."""
        return (self.x, self.y)

    def set_position(self, x: int, y: int) -> None:
        """
        Set the position of the object.

        Args:
            x: New x coordinate
            y: New y coordinate
        """
        self.x = x
        self.y = y
        self.rect.x = x
        self.rect.y = y
