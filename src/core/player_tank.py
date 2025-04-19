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
        self.lives = 3
        self.respawn_timer = 0
        self.respawn_duration = 3.0  # 3 seconds invincibility after respawn
        self.is_invincible = False
        self.initial_position = (x, y)
        self.blink_timer = 0
        self.blink_interval = 0.2  # Blink every 0.2 seconds during invincibility

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Handle a pygame event.

        Args:
            event: The pygame event to handle
        """
        if not self.is_invincible:  # Only handle input if not invincible
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
        # Update invincibility timer
        if self.is_invincible:
            self.respawn_timer += dt
            self.blink_timer += dt
            if self.respawn_timer >= self.respawn_duration:
                self.is_invincible = False
                self.respawn_timer = 0

        if self.is_invincible:
            return  # Don't move or shoot while invincible

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

    def respawn(self) -> None:
        """Respawn the tank at its initial position."""
        if self.lives > 0:
            self.lives -= 1
            self.x, self.y = self.initial_position
            self.is_invincible = True
            self.respawn_timer = 0
            self.blink_timer = 0
            self.direction = "up"  # Reset direction

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the tank and its bullet on the given surface.

        Args:
            surface: Surface to draw on
        """
        # Only draw if not invincible or during visible phase of blinking
        if not self.is_invincible or self.blink_timer % (self.blink_interval * 2) < self.blink_interval:
            if self.sprite:
                surface.blit(self.sprite, self.rect)
            else:
                # Draw a simple green tank if no sprite is provided
                pygame.draw.rect(surface, (0, 255, 0), self.rect)

        if self.bullet is not None and self.bullet.active:
            self.bullet.draw(surface)
