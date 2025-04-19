import pygame
import sys
from typing import Optional, List
from core.map import Map
from core.player_tank import PlayerTank
from core.enemy_tank import EnemyTank
from core.tile import TileType
from states.game_state import GameState
import random


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
        self.state = GameState.RUNNING
        self.background_color = (0, 0, 0)  # Black background

        # Initialize the map
        self.map = Map()

        # Initialize the player tank
        # Start at the bottom center of the screen
        start_x = (self.screen_width - self.tile_size) // 2
        start_y = self.screen_height - self.tile_size * 2
        self.player_tank = PlayerTank(start_x, start_y, self.tile_size)

        # Initialize enemy tanks
        self.enemy_tanks: List[EnemyTank] = []
        self._spawn_enemy()

        # Initialize font
        pygame.font.init()
        self.font = pygame.font.SysFont(None, 48)
        self.small_font = pygame.font.SysFont(None, 24)

    def _spawn_enemy(self) -> None:
        """Spawn a new enemy tank at a random position."""
        # Find a valid spawn position (not colliding with walls)
        while True:
            x = random.randint(1, self.map.width - 2) * self.tile_size
            y = random.randint(1, self.map.height - 2) * self.tile_size

            # Check if the position is valid (not colliding with walls)
            temp_rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
            collision = False
            for map_rect in self.map.get_collidable_tiles():
                if temp_rect.colliderect(map_rect):
                    collision = True
                    break

            if not collision:
                enemy = EnemyTank(x, y, self.tile_size)
                self.enemy_tanks.append(enemy)
                break

    def handle_events(self) -> None:
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_r and self.state != GameState.RUNNING:
                    # Restart game
                    self.__init__()
            # Pass events to the player tank only if game is running
            if self.state == GameState.RUNNING:
                self.player_tank.handle_event(event)

    def update(self) -> None:
        """Update game state."""
        if self.state != GameState.RUNNING:
            return

        # Get collidable map tiles
        map_rects = self.map.get_collidable_tiles()

        # Update the player tank
        self.player_tank.update(1.0 / self.fps, map_rects)

        # Update enemy tanks
        for enemy in self.enemy_tanks[:]:  # Create a copy of the list for iteration
            enemy.update(1.0 / self.fps, map_rects)

        # Handle bullet collisions with map tiles and tanks
        self._handle_bullet_collisions()

    def _handle_bullet_collisions(self) -> None:
        """Handle all bullet collisions with map tiles and tanks."""
        # Handle player bullet collisions
        if self.player_tank.bullet is not None and self.player_tank.bullet.active:
            bullet_rect = self.player_tank.bullet.rect

            # Check if bullet is out of bounds
            if (
                bullet_rect.x < 0
                or bullet_rect.x > self.screen_width
                or bullet_rect.y < 0
                or bullet_rect.y > self.screen_height
            ):
                self.player_tank.bullet.active = False
                return

            # Check collision with enemy tanks
            for enemy in self.enemy_tanks[:]:
                if bullet_rect.colliderect(enemy.rect):
                    self.enemy_tanks.remove(enemy)
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
                            return
                        elif tile.type == TileType.STEEL:
                            # Bullet stops at steel
                            self.player_tank.bullet.active = False
                            return
                        elif tile.type == TileType.BASE:
                            # Game over if base is hit
                            self.state = GameState.GAME_OVER
                            return

        # Handle enemy bullet collisions
        for enemy in self.enemy_tanks:
            if enemy.bullet is not None and enemy.bullet.active:
                bullet_rect = enemy.bullet.rect

                # Check if bullet is out of bounds
                if (
                    bullet_rect.x < 0
                    or bullet_rect.x > self.screen_width
                    or bullet_rect.y < 0
                    or bullet_rect.y > self.screen_height
                ):
                    enemy.bullet.active = False
                    continue

                # Check collision with player tank
                if bullet_rect.colliderect(self.player_tank.rect) and not self.player_tank.is_invincible:
                    self.player_tank.respawn()
                    enemy.bullet.active = False
                    if self.player_tank.lives <= 0:
                        self.state = GameState.GAME_OVER
                    return

                # Check collision with map tiles
                for y in range(self.map.height):
                    for x in range(self.map.width):
                        tile = self.map.get_tile_at(x, y)
                        if tile and tile.rect.colliderect(bullet_rect):
                            if tile.type == TileType.BRICK:
                                # Destroy brick tile
                                tile.type = TileType.EMPTY
                                enemy.bullet.active = False
                                break
                            elif tile.type == TileType.STEEL:
                                # Bullet stops at steel
                                enemy.bullet.active = False
                                break
                            elif tile.type == TileType.BASE:
                                # Game over if base is hit
                                self.state = GameState.GAME_OVER
                                return

    def _draw_game_over(self) -> None:
        """Draw the game over screen."""
        # Draw semi-transparent overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))  # Black with 50% opacity
        self.screen.blit(overlay, (0, 0))

        # Draw game over text
        text = self.font.render("GAME OVER", True, (255, 0, 0))
        text_rect = text.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
        self.screen.blit(text, text_rect)

        # Draw restart instructions
        restart_text = self.font.render("Press R to Restart", True, (255, 255, 255))
        restart_rect = restart_text.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 50))
        self.screen.blit(restart_text, restart_rect)

    def _draw_hud(self) -> None:
        """Draw the heads-up display."""
        # Draw lives
        lives_text = self.small_font.render(f"Lives: {self.player_tank.lives}", True, (255, 255, 255))
        self.screen.blit(lives_text, (10, 10))

        # Draw invincibility timer if active
        if self.player_tank.is_invincible:
            remaining_time = max(0, self.player_tank.respawn_duration - self.player_tank.respawn_timer)
            invincible_text = self.small_font.render(
                f"Invincible: {remaining_time:.1f}s", True, (255, 255, 0)
            )
            self.screen.blit(invincible_text, (10, 40))

    def render(self) -> None:
        """Render the game state."""
        # Clear the screen
        self.screen.fill(self.background_color)

        # Draw the map
        self.map.draw(self.screen)

        # Draw the player tank
        self.player_tank.draw(self.screen)

        # Draw enemy tanks
        for enemy in self.enemy_tanks:
            enemy.draw(self.screen)

        # Draw HUD
        self._draw_hud()

        # Draw game over screen if needed
        if self.state == GameState.GAME_OVER:
            self._draw_game_over()

        # Update the display
        pygame.display.flip()

    def run(self) -> None:
        """Main game loop."""
        running = True
        while running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(self.fps)
