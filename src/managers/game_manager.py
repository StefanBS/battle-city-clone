import pygame
import sys
from typing import List, Tuple, Optional, Any
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
)
import random
from src.managers.collision_manager import CollisionManager
from src.core.tank import Tank


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
        pygame.init()  # Ensure Pygame is initialized
        pygame.font.init()
        self._reset_game()

    def _reset_game(self) -> None:
        """Resets the game state to the initial configuration."""
        logger.info("Resetting game state...")
        # Display setup
        self.tile_size: int = TILE_SIZE
        self.screen_width: int = GRID_WIDTH * TILE_SIZE
        self.screen_height: int = GRID_HEIGHT * TILE_SIZE
        self.screen: pygame.Surface = pygame.display.set_mode(
            (self.screen_width, self.screen_height)
        )
        pygame.display.set_caption(WINDOW_TITLE)

        # Game clock
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.fps: int = FPS

        # Game state
        self.state: GameState = GameState.RUNNING
        self.background_color: Tuple[int, int, int] = BLACK

        # Map
        self.map: Map = Map()

        # Collision Manager
        self.collision_manager: CollisionManager = CollisionManager()

        # Player tank
        start_x: int = ((GRID_WIDTH // 2) - 1) * self.tile_size
        start_y: int = (GRID_HEIGHT - 2) * self.tile_size
        self.player_tank: PlayerTank = PlayerTank(start_x, start_y, self.tile_size)

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

    def _spawn_enemy(self) -> None:
        """Spawn a new enemy tank at a random spawn point if under the spawn limit."""
        if self.total_enemy_spawns >= self.max_enemy_spawns:
            logger.trace("Max enemy spawns reached, skipping spawn.")
            return

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

        if not collision:
            for enemy in self.enemy_tanks:
                if temp_rect.colliderect(enemy.rect):
                    collision = True
                    break

        if not collision:
            # Always spawn 'basic' type for now
            enemy = EnemyTank(x, y, self.tile_size, tank_type="basic")
            self.enemy_tanks.append(enemy)
            self.total_enemy_spawns += 1
            logger.debug(
                (
                    f"Spawned enemy {self.total_enemy_spawns}/{self.max_enemy_spawns} "
                    f"at ({x}, {y})"
                )
            )
        else:
            logger.warning(f"Spawn point ({x}, {y}) was blocked.")

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

            # Pass events to the player tank only if game is running
            if self.state == GameState.RUNNING:
                self.player_tank.handle_event(event)

    def update(self) -> None:
        """Update game state."""
        if self.state != GameState.RUNNING:
            return

        logger.trace("Starting game update...")
        dt: float = 1.0 / self.fps

        # --- Prepare data for Collision Manager ---
        destructible_tiles: List[Tile] = self.map.get_tiles_by_type([TileType.BRICK])
        impassable_tiles: List[Tile] = self.map.get_tiles_by_type(
            [TileType.STEEL, TileType.WATER]
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

        # --- Update Game Objects ---

        # Update player tank
        self.player_tank.update(dt)

        # Iterate over a copy for safe removal
        for enemy in self.enemy_tanks[:]:
            enemy.update(dt)
        # --- End Update Game Objects ---

        # --- Enemy Spawning ---
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            logger.trace("Spawn timer triggered.")
            self._spawn_enemy()
            self.spawn_timer = 0
        # --- End Enemy Spawning ---

        # --- Check Collisions ---
        self.collision_manager.check_collisions(
            player_tank=self.player_tank,
            player_bullets=player_bullets,
            enemy_tanks=self.enemy_tanks,
            enemy_bullets=enemy_bullets,
            destructible_tiles=destructible_tiles,
            impassable_tiles=impassable_tiles,
            player_base=player_base,
        )
        # --- End Check Collisions ---

        # --- Process Collisions ---
        self._process_collisions()
        # --- End Process Collisions ---
        logger.trace("Game update finished.")

    def _process_collisions(self) -> None:
        """Process the collision events detected by the CollisionManager."""
        events: List[Tuple[Any, Any]] = self.collision_manager.get_collision_events()
        if not events:
            return

        logger.trace(f"Processing {len(events)} collision events...")
        processed_bullets = set()
        # Keep track of tanks whose moves were reverted to avoid double-reverting
        reverted_tanks = set()

        # Separate lists to manage removals safely
        enemies_to_remove: List[EnemyTank] = []

        for obj_a, obj_b in events:
            # Prioritize bullet collisions as they often have immediate effects
            bullet = None
            other_for_bullet = None
            if isinstance(obj_a, Bullet) and obj_a not in processed_bullets:
                bullet = obj_a
                other_for_bullet = obj_b
            elif isinstance(obj_b, Bullet) and obj_b not in processed_bullets:
                bullet = obj_b
                other_for_bullet = obj_a

            if bullet:
                if self._handle_bullet_collision(
                    bullet, other_for_bullet, enemies_to_remove
                ):
                    processed_bullets.add(bullet)
                    if isinstance(other_for_bullet, Bullet):
                        processed_bullets.add(other_for_bullet)
                continue  # Processed this pair as bullet collision

            # Handle tank collisions if not already reverted
            # Tank vs Tank
            if isinstance(obj_a, Tank) and isinstance(obj_b, Tank):
                if obj_a not in reverted_tanks or obj_b not in reverted_tanks:
                    if self._handle_tank_tank_collision(obj_a, obj_b):
                        reverted_tanks.add(obj_a)
                        reverted_tanks.add(obj_b)
            # Tank vs Tile
            elif isinstance(obj_a, Tank) and isinstance(obj_b, Tile):
                if obj_a not in reverted_tanks:
                    if self._handle_tank_tile_collision(obj_a, obj_b):
                        reverted_tanks.add(obj_a)
            elif isinstance(obj_b, Tank) and isinstance(obj_a, Tile):
                if obj_b not in reverted_tanks:
                    if self._handle_tank_tile_collision(obj_b, obj_a):
                        reverted_tanks.add(obj_b)

        # Remove destroyed enemies after processing all collisions for the frame
        for enemy in enemies_to_remove:
            if enemy in self.enemy_tanks:
                self.enemy_tanks.remove(enemy)

        # Check for win condition after potential enemy removals
        if not self.enemy_tanks and self.total_enemy_spawns >= self.max_enemy_spawns:
            logger.info("All enemies defeated. Victory!")
            self.state = GameState.VICTORY  # Assuming VICTORY state exists
        logger.trace("Finished processing collisions.")

    def _handle_bullet_collision(
        self, bullet: Bullet, other: Any, enemies_to_remove: List[EnemyTank]
    ) -> bool:
        """Handles the outcome of a bullet colliding with another object.

        Args:
            bullet: The bullet involved in the collision.
            other: The other object the bullet collided with.
            enemies_to_remove: A list to append enemies that should be removed.

        Returns:
            True if the bullet should be considered processed (i.e., deactivated)
        """
        logger.trace(
            (
                f"Handling bullet collision: {type(bullet).__name__} vs "
                f"{type(other).__name__}"
            )
        )
        if not bullet.active:
            return False  # Bullet already inactive

        processed = False

        # --- Bullet vs Enemy Tank ---
        if isinstance(other, EnemyTank) and bullet.owner_type == "player":
            logger.debug(f"Player bullet hit enemy tank (type: {other.tank_type})")
            bullet.active = False
            processed = True
            # Avoid damaging the same tank multiple times in one frame from different
            #  events if other not in processed_tanks:
            destroyed = other.take_damage()
            if destroyed:
                logger.info(f"Enemy tank (type: {other.tank_type}) destroyed.")
                enemies_to_remove.append(other)
            # processed_tanks.add(other)

        # --- Bullet vs Player Tank ---
        elif isinstance(other, PlayerTank) and bullet.owner_type == "enemy":
            logger.debug("Enemy bullet hit player tank.")
            bullet.active = False
            processed = True
            if not other.is_invincible:
                # if other not in processed_tanks:
                destroyed = other.take_damage()
                if destroyed:
                    logger.info("Player tank destroyed.")
                    self.state = GameState.GAME_OVER
                else:
                    other.respawn()  # Player lost a life but has more
                # processed_tanks.add(other)

        # --- Bullet vs Tile ---
        elif isinstance(other, Tile):
            if other.type == TileType.BRICK:
                logger.debug(f"Bullet hit brick tile at ({other.x}, {other.y})")
                bullet.active = False
                other.type = TileType.EMPTY  # Destroy brick
                # Potentially update map collision data if needed
                processed = True
            elif other.type == TileType.STEEL:
                logger.debug(f"Bullet hit steel tile at ({other.x}, {other.y})")
                bullet.active = False  # Bullet stops at steel
                processed = True
            elif other.type == TileType.BASE:
                logger.critical(
                    f"Bullet hit player base at ({other.x}, {other.y})! Game Over."
                )
                bullet.active = False
                other.type = TileType.BASE_DESTROYED  # Change base appearance
                self.state = GameState.GAME_OVER  # Game over
                processed = True

        # --- Bullet vs Bullet ---
        elif isinstance(other, Bullet) and other.active:
            # Ensure they are not the same bullet instance if logic allows
            if bullet != other:
                logger.debug("Bullet hit bullet. Both deactivated.")
                bullet.active = False
                other.active = False
                processed = True  # Mark this bullet as processed
                # The outer loop will mark the 'other' bullet as processed too

        return processed

    def _handle_tank_tank_collision(self, tank_a: Tank, tank_b: Tank) -> bool:
        """Handles Tank vs Tank collisions by reverting movement.

        Returns:
            True if movement was reverted for at least one tank, False otherwise.
        """
        logger.debug(
            f"Tank collision detected: {tank_a.owner_type} vs {tank_b.owner_type}"
        )
        # Simple reversion: If two tanks collide, revert both their moves.
        # More sophisticated logic could try to revert only one based on direction etc.
        tank_a.revert_move()
        tank_b.revert_move()
        return True  # Indicated reversion occurred

    def _handle_tank_tile_collision(self, tank: Tank, tile: Tile) -> bool:
        """Handles Tank vs Tile collisions. Reverts tank movement if needed.

        Returns:
            True if movement was reverted, False otherwise.
        """
        # Define which tile types block tank movement
        impassable_types = [TileType.STEEL, TileType.WATER, TileType.BASE]

        if tile.type in impassable_types:
            logger.debug(
                f"Tank ({tank.owner_type}) collision with impassable tile "
                f"({tile.type.name}) at ({tile.x}, {tile.y}). Reverting move."
            )
            tank.revert_move()

            # Special case for EnemyTank: If it hit a wall, encourage changing direction
            if isinstance(tank, EnemyTank):
                tank._change_direction()
                tank.direction_timer = 0  # Reset timer to avoid immediate change back

            return True  # Indicated reversion occurred

        return False  # Tile was not impassable, no reversion needed

    def _draw_game_over(self) -> None:
        """Draw the game over screen."""
        logger.debug("Drawing Game Over screen.")
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

        # Draw restart text
        restart_text = self.font.render("Press R to Restart", True, WHITE)
        restart_rect = restart_text.get_rect(
            center=(self.screen_width // 2, self.screen_height // 2 + 50)
        )
        self.screen.blit(restart_text, restart_rect)

    def _draw_victory(self) -> None:  # Added method
        """Draw the victory screen."""
        logger.debug("Drawing Victory screen.")
        overlay = pygame.Surface(
            (self.screen_width, self.screen_height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 128))
        self.screen.blit(overlay, (0, 0))

        text = self.font.render("VICTORY!", True, (0, 255, 0))
        text_rect = text.get_rect(
            center=(self.screen_width // 2, self.screen_height // 2)
        )
        self.screen.blit(text, text_rect)

        restart_text = self.font.render("Press R to Play Again", True, WHITE)
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
        elif self.state == GameState.VICTORY:  # Added victory check
            self._draw_victory()

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
        pygame.quit()
        sys.exit()
