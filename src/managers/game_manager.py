import pygame
from typing import List, Tuple, Optional
from loguru import logger
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType
from src.core.bullet import Bullet
from src.states.game_state import GameState
from src.utils.constants import (
    WINDOW_TITLE,
    FPS,
    TILE_SIZE,
    GRID_WIDTH,
    GRID_HEIGHT,
    BLACK,
    WHITE,
    YELLOW,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
)
import random
from src.managers.collision_manager import CollisionManager
from src.managers.collision_response_handler import CollisionResponseHandler
from src.managers.texture_manager import TextureManager
from src.managers.input_handler import InputHandler


class GameManager:
    """Manages the core game loop and window."""

    # Enemy spawn points (top of the screen)
    SPAWN_POINTS: List[Tuple[int, int]] = [
        (3, 1),  # Left spawn
        (GRID_WIDTH // 2, 1),  # Center spawn
        (GRID_WIDTH - 4, 1),  # Right spawn
    ]

    def __init__(self) -> None:
        """Initialize the game window and basic settings."""
        logger.info("Initializing GameManager...")
        self._reset_game()

    def _reset_game(self) -> None:
        """Resets the game state to the initial configuration."""
        logger.info("Resetting game state...")
        # Display setup
        self.tile_size: int = TILE_SIZE
        self.screen_width: int = WINDOW_WIDTH
        self.screen_height: int = WINDOW_HEIGHT
        self.screen: pygame.Surface = pygame.display.set_mode(
            (self.screen_width, self.screen_height)
        )
        # --- Create logical game surface ---
        self.logical_width: int = GRID_WIDTH * self.tile_size
        self.logical_height: int = GRID_HEIGHT * self.tile_size
        self.game_surface: pygame.Surface = pygame.Surface(
            (self.logical_width, self.logical_height)
        )
        # --- End Create logical game surface ---
        pygame.display.set_caption(WINDOW_TITLE)

        # --- Initialize Managers AFTER display mode is set ---
        logger.info("Initializing TextureManager...")
        self.texture_manager = TextureManager("assets/sprites/sprites.png")
        logger.info("Initializing CollisionManager...")
        self.collision_manager: CollisionManager = CollisionManager()
        self.input_handler: InputHandler = InputHandler()
        # --- End Initialize Managers ---

        # Game clock
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.fps: int = FPS

        # Game state
        self.state: GameState = GameState.RUNNING
        self.background_color: Tuple[int, int, int] = BLACK

        # Map
        self.map: Map = Map(self.texture_manager)

        # Collision response handler
        self.collision_response_handler: CollisionResponseHandler = (
            CollisionResponseHandler(
                game_map=self.map,
                set_game_state=self._set_game_state,
            )
        )

        # Player tank
        start_x: int = ((GRID_WIDTH // 2) - 1) * self.tile_size
        start_y: int = (GRID_HEIGHT - 2) * self.tile_size
        self.player_tank: PlayerTank = PlayerTank(
            start_x, start_y, self.tile_size, self.texture_manager
        )

        # Enemy tanks
        self.enemy_tanks: List[EnemyTank] = []
        self.total_enemy_spawns: int = 0
        self.max_enemy_spawns: int = 5
        self.spawn_timer: float = 0.0
        self.spawn_interval: float = 5.0
        self._spawn_enemy()  # Initial spawn

        # Font
        self.font: pygame.font.Font = pygame.font.SysFont(None, 48)
        self.small_font: pygame.font.Font = pygame.font.SysFont(None, 24)
        logger.info("Game reset complete.")

    def _spawn_enemy(self) -> bool:
        """Spawn a new enemy tank at a random spawn point if under the spawn limit.

        Returns:
            True if an enemy was successfully spawned, False otherwise.
        """
        if self.total_enemy_spawns >= self.max_enemy_spawns:
            logger.trace("Max enemy spawns reached, skipping spawn.")
            return False

        # Get a random spawn point
        spawn_grid_x, spawn_grid_y = random.choice(self.SPAWN_POINTS)
        x: int = spawn_grid_x * self.tile_size
        y: int = spawn_grid_y * self.tile_size

        # Check if the spawn point is clear
        temp_rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
        collision: bool = False
        map_collidables: List[pygame.Rect] = self.map.get_collidable_tiles()
        for map_rect in map_collidables:
            if temp_rect.colliderect(map_rect):
                collision = True
                break

        # Check against player tank
        if not collision and self.player_tank:
            if temp_rect.colliderect(self.player_tank.rect):
                logger.debug(f"Spawn point ({x}, {y}) blocked by player tank.")
                collision = True

        if not collision:
            for enemy in self.enemy_tanks:
                if temp_rect.colliderect(enemy.rect):
                    collision = True
                    break

        if not collision:
            # Always spawn 'basic' type for now
            enemy = EnemyTank(
                x, y, self.tile_size, self.texture_manager, tank_type="basic"
            )
            self.enemy_tanks.append(enemy)
            self.total_enemy_spawns += 1
            logger.debug(
                (
                    f"Spawned enemy {self.total_enemy_spawns}/{self.max_enemy_spawns} "
                    f"at ({x}, {y})"
                )
            )
            return True
        else:
            logger.warning(f"Spawn point ({x}, {y}) was blocked.")
            return False

    def handle_events(self) -> None:
        """Handle pygame events."""
        for event in pygame.event.get():
            logger.trace(f"Handling event: {event}")
            if event.type == pygame.QUIT:
                logger.info("Quit event received.")
                self._quit_game()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    logger.info("Escape key pressed, quitting game.")
                    self._quit_game()
                elif event.key == pygame.K_r and self.state != GameState.RUNNING:
                    logger.info("R key pressed, resetting game.")
                    self._reset_game()  # Use the new reset method

            # Pass events to input handler only if game is running
            if self.state == GameState.RUNNING:
                self.input_handler.handle_event(event)

    def update(self) -> None:
        """Update game state."""
        if self.state != GameState.RUNNING:
            return

        logger.trace("Starting game update...")
        dt: float = 1.0 / self.fps

        # --- Prepare data for Collision Manager ---
        destructible_tiles: List[Tile] = self.map.get_tiles_by_type([TileType.BRICK])
        impassable_tiles: List[Tile] = self.map.get_tiles_by_type(
            [TileType.STEEL, TileType.WATER, TileType.BASE, TileType.BRICK]
        )
        player_base: Optional[Tile] = self.map.get_base()

        player_bullets: List[Bullet] = []
        if self.player_tank.bullet and self.player_tank.bullet.active:
            player_bullets.append(self.player_tank.bullet)

        enemy_bullets: List[Bullet] = []
        for enemy in self.enemy_tanks:
            if enemy.bullet and enemy.bullet.active:
                enemy_bullets.append(enemy.bullet)
        # --- End Prepare data ---

        self.map.update(dt)
        # Drive player tank from input
        dx, dy = self.input_handler.get_movement_direction()
        if dx != 0 or dy != 0:
            self.player_tank.move(dx, dy, dt)
        if self.input_handler.consume_shoot():
            self.player_tank.shoot()
        self.player_tank.update(dt)

        # Iterate over a copy for safe removal
        for enemy in self.enemy_tanks[:]:
            enemy.update(dt)

        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            logger.trace("Spawn timer triggered.")
            # Reset timer only if spawn was successful
            if self._spawn_enemy():
                self.spawn_timer = 0
            # else: Timer keeps ticking if spawn failed (e.g., blocked)

        self.collision_manager.check_collisions(
            player_tank=self.player_tank,
            player_bullets=player_bullets,
            enemy_tanks=self.enemy_tanks,
            enemy_bullets=enemy_bullets,
            destructible_tiles=destructible_tiles,
            impassable_tiles=impassable_tiles,
            player_base=player_base,
        )

        events = self.collision_manager.get_collision_events()
        enemies_to_remove = self.collision_response_handler.process_collisions(
            events
        )
        for enemy in enemies_to_remove:
            if enemy in self.enemy_tanks:
                self.enemy_tanks.remove(enemy)

        if self.state == GameState.RUNNING:
            if (
                not self.enemy_tanks
                and self.total_enemy_spawns >= self.max_enemy_spawns
            ):
                logger.info("All enemies defeated. Victory!")
                self.state = GameState.VICTORY

        logger.trace("Game update finished.")

    def _set_game_state(self, state: GameState) -> None:
        """Set the game state."""
        self.state = state

    def _draw_game_over(self) -> None:
        """Draw the game over screen."""
        logger.debug("Drawing Game Over screen.")
        # Create overlay on the logical surface
        overlay = pygame.Surface(
            (self.logical_width, self.logical_height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 128))  # Black with 50% opacity
        self.game_surface.blit(overlay, (0, 0))

        # Draw game over text centered on logical surface
        text = self.font.render("GAME OVER", True, (255, 0, 0))
        text_rect = text.get_rect(
            center=(self.logical_width // 2, self.logical_height // 2)
        )
        self.game_surface.blit(text, text_rect)

        # Draw restart text centered on logical surface
        restart_text = self.font.render("Press R to Restart", True, WHITE)
        restart_rect = restart_text.get_rect(
            center=(self.logical_width // 2, self.logical_height // 2 + 50)
        )
        self.game_surface.blit(restart_text, restart_rect)

    def _draw_victory(self) -> None:  # Added method
        """Draw the victory screen."""
        logger.debug("Drawing Victory screen.")
        # Create overlay on the logical surface
        overlay = pygame.Surface(
            (self.logical_width, self.logical_height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 128))
        self.game_surface.blit(overlay, (0, 0))

        # Draw victory text centered on logical surface
        text = self.font.render("VICTORY!", True, (0, 255, 0))
        text_rect = text.get_rect(
            center=(self.logical_width // 2, self.logical_height // 2)
        )
        self.game_surface.blit(text, text_rect)

        # Draw restart text centered on logical surface
        restart_text = self.font.render("Press R to Play Again", True, WHITE)
        restart_rect = restart_text.get_rect(
            center=(self.logical_width // 2, self.logical_height // 2 + 50)
        )
        self.game_surface.blit(restart_text, restart_rect)

    def _draw_hud(self) -> None:
        """Draw the heads-up display."""
        # Draw lives onto the logical surface
        lives_text = self.small_font.render(
            f"Lives: {self.player_tank.lives}", True, WHITE
        )
        self.game_surface.blit(lives_text, (10, 10))

        # Draw invincibility timer if active onto the logical surface
        if self.player_tank.is_invincible:
            remaining_time = max(
                0,
                self.player_tank.invincibility_duration
                - self.player_tank.invincibility_timer,
            )
            invincible_text = self.small_font.render(
                f"Invincible: {remaining_time:.1f}s", True, YELLOW
            )
            self.game_surface.blit(invincible_text, (10, 40))

    def render(self) -> None:
        """Render the game state."""
        # Clear the logical game surface
        self.game_surface.fill(self.background_color)

        # Draw the map onto the logical surface
        self.map.draw(self.game_surface)

        # Draw the player tank onto the logical surface
        self.player_tank.draw(self.game_surface)

        # Draw enemy tanks onto the logical surface
        for enemy in self.enemy_tanks:
            enemy.draw(self.game_surface)

        # Draw HUD onto the logical surface
        self._draw_hud()  # Make sure HUD uses self.game_surface if drawing directly

        # Draw game over/victory screen if needed onto logical surface
        # NOTE: These draw methods might need adjustment if they assume self.screen size
        if self.state == GameState.GAME_OVER:
            self._draw_game_over()
        elif self.state == GameState.VICTORY:
            self._draw_victory()

        # Scale the logical surface to the main screen
        scaled_surface = pygame.transform.scale(
            self.game_surface, (self.screen_width, self.screen_height)
        )
        self.screen.blit(scaled_surface, (0, 0))

        # Update the display
        pygame.display.flip()

    def run(self) -> None:
        """Main game loop."""
        logger.info("Starting main game loop.")
        running = True
        while running:
            self.handle_events()
            self.update()
            self.render()

            # Cap the frame rate
            self.clock.tick(self.fps)

            # Check if state changed to EXIT
            if self.state == GameState.EXIT:
                running = False

        logger.info("Exiting main game loop.")

    def _quit_game(self) -> None:
        """Cleanly exit the game."""
        logger.info("Setting game state to EXIT.")
        self.state = GameState.EXIT
