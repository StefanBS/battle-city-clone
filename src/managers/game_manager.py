import pygame
import sys
from typing import List
from core.map import Map
from core.player_tank import PlayerTank
from core.enemy_tank import EnemyTank
from core.tile import TileType
from states.game_state import GameState
from utils.constants import (
    WINDOW_TITLE,
    FPS,
    TILE_SIZE,
    GRID_WIDTH,
    GRID_HEIGHT,
    BLACK,
    WHITE,
    YELLOW,
)
import random


class GameManager:
    """Manages the core game loop and window."""

    # Enemy spawn points (top of the screen)
    SPAWN_POINTS = [
        (3, 1),  # Left spawn
        (GRID_WIDTH // 2, 1),  # Center spawn
        (GRID_WIDTH - 4, 1),  # Right spawn
    ]

    def __init__(self):
        """Initialize the game window and basic settings."""
        # Set up the display
        self.tile_size = TILE_SIZE
        self.screen_width = GRID_WIDTH * TILE_SIZE
        self.screen_height = GRID_HEIGHT * TILE_SIZE
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption(WINDOW_TITLE)

        # Game clock for controlling frame rate
        self.clock = pygame.time.Clock()
        self.fps = FPS

        # Game state
        self.state = GameState.RUNNING
        self.background_color = BLACK

        # Initialize the map
        self.map = Map()

        # Initialize the player tank
        # Start at the bottom center of the screen, aligned to the grid
        start_x = ((GRID_WIDTH // 2) - 1) * self.tile_size
        start_y = (GRID_HEIGHT - 2) * self.tile_size
        self.player_tank = PlayerTank(start_x, start_y, self.tile_size)

        # Initialize enemy tanks
        self.enemy_tanks: List[EnemyTank] = []
        self.total_enemy_spawns = 0
        self.max_enemy_spawns = 10  # Total number of enemies to spawn per level
        self.spawn_timer = 0
        self.spawn_interval = 3.0  # Spawn a new enemy every 3 seconds
        self._spawn_enemy()

        # Initialize font
        pygame.font.init()
        self.font = pygame.font.SysFont(None, 48)
        self.small_font = pygame.font.SysFont(None, 24)

    def _spawn_enemy(self) -> None:
        """Spawn a new enemy tank at a random spawn point if under the spawn limit."""
        if self.total_enemy_spawns >= self.max_enemy_spawns:
            return

        # Choose a random spawn point
        spawn_grid_x, spawn_grid_y = random.choice(self.SPAWN_POINTS)
        x = spawn_grid_x * self.tile_size
        y = spawn_grid_y * self.tile_size

        # Check if the spawn point is clear
        temp_rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
        collision = False
        for map_rect in self.map.get_collidable_tiles():
            if temp_rect.colliderect(map_rect):
                collision = True
                break

        # Also check for collisions with other tanks
        for enemy in self.enemy_tanks:
            if temp_rect.colliderect(enemy.rect):
                collision = True
                break

        if not collision:
            enemy = EnemyTank(x, y, self.tile_size)
            self.enemy_tanks.append(enemy)
            self.total_enemy_spawns += 1

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

        # Update spawn timer and spawn new enemies
        self.spawn_timer += 1.0 / self.fps
        if self.spawn_timer >= self.spawn_interval:
            self._spawn_enemy()
            self.spawn_timer = 0

        # Handle bullet collisions with map tiles and tanks
        self._handle_bullet_collisions()

    def _handle_bullet_collisions(self) -> None:
        """Handle all bullet collisions with map tiles and tanks."""
        # Handle player bullet collisions
        if self.player_tank.bullet is not None and self.player_tank.bullet.active:
            player_bullet_rect = self.player_tank.bullet.rect

            # Check collision with enemy bullets
            for enemy in self.enemy_tanks:
                if enemy.bullet is not None and enemy.bullet.active:
                    if player_bullet_rect.colliderect(enemy.bullet.rect):
                        self.player_tank.bullet.active = False
                        enemy.bullet.active = False
                        return

            # Check collision with enemy tanks
            for enemy in self.enemy_tanks[:]:
                if player_bullet_rect.colliderect(enemy.rect):
                    if enemy.take_damage():
                        self.enemy_tanks.remove(enemy)
                        # Check if all enemies are destroyed and no more will spawn
                        if (
                            len(self.enemy_tanks) == 0
                            and self.total_enemy_spawns >= self.max_enemy_spawns
                        ):
                            self.state = GameState.VICTORY
                    self.player_tank.bullet.active = False
                    return

            # Check collision with map tiles
            for y in range(self.map.height):
                for x in range(self.map.width):
                    tile = self.map.get_tile_at(x, y)
                    if tile and tile.rect.colliderect(player_bullet_rect):
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
                enemy_bullet_rect = enemy.bullet.rect

                # Check collision with player bullet
                if (
                    self.player_tank.bullet is not None
                    and self.player_tank.bullet.active
                    and enemy_bullet_rect.colliderect(self.player_tank.bullet.rect)
                ):
                    enemy.bullet.active = False
                    self.player_tank.bullet.active = False
                    return

                # Check collision with player tank
                if enemy_bullet_rect.colliderect(self.player_tank.rect):
                    if not self.player_tank.is_invincible:
                        if self.player_tank.take_damage():
                            self.state = GameState.GAME_OVER
                        else:
                            self.player_tank.respawn()
                    enemy.bullet.active = False
                    return

                # Check collision with map tiles
                for y in range(self.map.height):
                    for x in range(self.map.width):
                        tile = self.map.get_tile_at(x, y)
                        if tile and tile.rect.colliderect(enemy_bullet_rect):
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
        overlay = pygame.Surface(
            (self.screen_width, self.screen_height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 128))  # Black with 50% opacity
        self.screen.blit(overlay, (0, 0))

        # Draw game over text
        text = self.font.render("GAME OVER", True, (255, 0, 0))
        text_rect = text.get_rect(
            center=(self.screen_width // 2, self.screen_height // 2)
        )
        self.screen.blit(text, text_rect)

        # Draw restart instructions
        restart_text = self.font.render("Press R to Restart", True, (255, 255, 255))
        restart_rect = restart_text.get_rect(
            center=(self.screen_width // 2, self.screen_height // 2 + 50)
        )
        self.screen.blit(restart_text, restart_rect)

    def _draw_hud(self) -> None:
        """Draw the heads-up display."""
        # Draw lives
        lives_text = self.small_font.render(
            f"Lives: {self.player_tank.lives}", True, WHITE
        )
        self.screen.blit(lives_text, (10, 10))

        # Draw invincibility timer if active
        if self.player_tank.is_invincible:
            remaining_time = max(
                0,
                self.player_tank.invincibility_duration
                - self.player_tank.invincibility_timer,
            )
            invincible_text = self.small_font.render(
                f"Invincible: {remaining_time:.1f}s", True, YELLOW
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
