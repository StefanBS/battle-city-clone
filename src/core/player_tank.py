import pygame
from typing import Tuple, Optional
from .game_object import GameObject
from .bullet import Bullet
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
        self.bullet: Optional[Bullet] = None
        self.tile_size = tile_size

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Handle a pygame event.

        Args:
            event: The pygame event to handle
        """
        self.input_handler.handle_event(event)

        # Handle shooting
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.shoot()

    def shoot(self) -> None:
        """Create a new bullet if none exists."""
        if self.bullet is None or not self.bullet.active:
            # Calculate bullet starting position (center of tank)
            bullet_x = self.x + self.width // 2 - self.tile_size // 4
            bullet_y = self.y + self.height // 2 - self.tile_size // 4
            self.bullet = Bullet(bullet_x, bullet_y, self.direction, self.tile_size)

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

        # Update bullet if it exists
        if self.bullet is not None:
            self.bullet.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the tank and its bullet on the given surface.

        Args:
            surface: Surface to draw on
        """
        super().draw(surface)
        if self.bullet is not None and self.bullet.active:
            self.bullet.draw(surface)
