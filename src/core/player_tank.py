import pygame
from typing import Tuple
from .game_object import GameObject
from managers.input_handler import InputHandler


class PlayerTank(GameObject):
    """Player-controlled tank entity."""

    def __init__(
        self,
        x: int,
        y: int,
        tile_size: int,
        sprite: pygame.Surface = None,
    ):
        """
        Initialize the player tank.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            sprite: Optional sprite surface
        """
        super().__init__(x, y, tile_size, tile_size, sprite)
        self.speed = 2  # Pixels per frame
        self.input_handler = InputHandler()
        self.direction = "up"  # Initial direction

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Handle a pygame event.

        Args:
            event: The pygame event to handle
        """
        self.input_handler.handle_event(event)

    def update(self, dt: float, map_rects: list[pygame.Rect]) -> None:
        """
        Update the tank's position based on input and check for collisions.

        Args:
            dt: Time elapsed since last update in seconds
            map_rects: List of rectangles representing collidable map tiles
        """
        # Get movement direction from input
        dx, dy = self.input_handler.get_movement_direction()

        # Update direction based on movement
        if dx != 0 or dy != 0:
            if dx > 0:
                self.direction = "right"
            elif dx < 0:
                self.direction = "left"
            elif dy > 0:
                self.direction = "down"
            elif dy < 0:
                self.direction = "up"

        # Calculate new position
        new_x = self.x + dx * self.speed
        new_y = self.y + dy * self.speed

        # Create a temporary rect for collision checking
        temp_rect = pygame.Rect(new_x, new_y, self.width, self.height)

        # Check for collisions with map tiles
        collision = False
        for map_rect in map_rects:
            if temp_rect.colliderect(map_rect):
                collision = True
                break

        # Only update position if no collision
        if not collision:
            self.x = new_x
            self.y = new_y

        # Update the tank's rect
        super().update(dt)
