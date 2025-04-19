import pygame
import sys
from typing import Optional
from core.map import Map
from core.player_tank import PlayerTank
from core.tile import TileType


class GameManager:
    """Manages the core game loop and window."""

    def __init__(self):
        """Initialize the game window and basic settings."""
        # Set up the display
        self.tile_size = 32
        self.screen_width = 25 * self.tile_size  # 25 tiles wide
        self.screen_height = 20 * self.tile_size  # 20 tiles high
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Battle City Clone")

        # Game clock for controlling frame rate
        self.clock = pygame.time.Clock()
        self.fps = 60

        # Game state
        self.running = True
        self.background_color = (0, 0, 0)  # Black background

        # Initialize the map
        self.map = Map()

        # Initialize the player tank
        # Start at the bottom center of the screen
        start_x = (self.screen_width - self.tile_size) // 2
        start_y = self.screen_height - self.tile_size * 2
        self.player_tank = PlayerTank(start_x, start_y, self.tile_size)

    def handle_events(self) -> None:
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            # Pass events to the player tank
            self.player_tank.handle_event(event)

    def update(self) -> None:
        """Update game state."""
        # Get collidable map tiles
        map_rects = self.map.get_collidable_tiles()

        # Update the player tank
        self.player_tank.update(1.0 / self.fps, map_rects)

        # Handle bullet collisions with map tiles
        if self.player_tank.bullet is not None and self.player_tank.bullet.active:
            bullet_rect = self.player_tank.bullet.rect

            # Check if bullet is out of bounds
            if (bullet_rect.x < 0 or bullet_rect.x > self.screen_width or
                bullet_rect.y < 0 or bullet_rect.y > self.screen_height):
                self.player_tank.bullet.active = False
                return

            # Check collision with map tiles
            for y in range(self.map.height):
                for x in range(self.map.width):
                    tile = self.map.get_tile_at(x, y)
                    if tile and tile.rect.colliderect(bullet_rect):
                        if tile.type == TileType.BRICK:
                            # Destroy brick tile
                            tile.type = TileType.EMPTY
                            self.player_tank.bullet.active = False
                            return  # Exit after first collision
                        elif tile.type == TileType.STEEL:
                            # Bullet stops at steel
                            self.player_tank.bullet.active = False
                            return  # Exit after first collision
                        elif tile.type == TileType.BASE:
                            # Game over if base is hit
                            self.running = False
                            return  # Exit after first collision

    def render(self) -> None:
        """Render the game state."""
        # Clear the screen
        self.screen.fill(self.background_color)

        # Draw the map
        self.map.draw(self.screen)

        # Draw the player tank
        self.player_tank.draw(self.screen)

        # Update the display
        pygame.display.flip()

    def run(self) -> None:
        """Main game loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(self.fps)
