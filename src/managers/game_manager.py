import pygame
from typing import List, Optional
from loguru import logger
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.core.tile import Tile, TileType, IMPASSABLE_TILE_TYPES
from src.core.bullet import Bullet
from src.states.game_state import GameState
from src.utils.constants import (
    OwnerType,
    WINDOW_TITLE,
    FPS,
    TILE_SIZE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    LOGICAL_WIDTH,
    LOGICAL_HEIGHT,
)
from src.managers.collision_manager import CollisionManager
from src.managers.collision_response_handler import CollisionResponseHandler
from src.managers.texture_manager import TextureManager
from src.managers.input_handler import InputHandler
from src.managers.spawn_manager import SpawnManager
from src.managers.renderer import Renderer
from src.utils.paths import resource_path


class GameManager:
    """Manages the core game loop and window."""

    def __init__(self) -> None:
        """Initialize the game window and persistent resources."""
        logger.info("Initializing GameManager...")

        # Display setup (once)
        self.tile_size: int = TILE_SIZE
        self.screen: pygame.Surface = pygame.display.set_mode(
            (WINDOW_WIDTH, WINDOW_HEIGHT)
        )
        pygame.display.set_caption(WINDOW_TITLE)

        # Persistent resources (once)
        sprite_path = resource_path("assets/sprites/sprites.png")
        self.texture_manager = TextureManager(sprite_path)
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.fps: int = FPS
        self.input_handler: InputHandler = InputHandler()

        self._reset_game()

    def _reset_game(self) -> None:
        """Resets per-level game state. Display and textures are preserved."""
        logger.info("Resetting game state...")

        self.state: GameState = GameState.RUNNING
        self.current_stage: int = 1
        self.collision_manager: CollisionManager = CollisionManager()

        # Map
        map_path = resource_path("assets/maps/level_01.tmx")
        self.map: Map = Map(map_path, self.texture_manager)

        # Compute map pixel dimensions (sub-tile grid * sub-tile size)
        map_width_px: int = self.map.width * self.map.tile_size
        map_height_px: int = self.map.height * self.map.tile_size

        # Collision response handler
        self.collision_response_handler: CollisionResponseHandler = (
            CollisionResponseHandler(
                game_map=self.map,
                set_game_state=self._set_game_state,
            )
        )

        # Player tank (spawn coords are in sub-tile units)
        start_x: int = self.map.player_spawn[0] * self.map.tile_size
        start_y: int = self.map.player_spawn[1] * self.map.tile_size
        self.player_tank: PlayerTank = PlayerTank(
            start_x,
            start_y,
            self.tile_size,
            self.texture_manager,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )

        # Renderer (fixed logical surface with map centered inside)
        self.renderer: Renderer = Renderer(
            self.screen,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
            map_width_px,
            map_height_px,
        )

        # SpawnManager
        self.spawn_manager: SpawnManager = SpawnManager(
            tile_size=self.tile_size,
            texture_manager=self.texture_manager,
            spawn_points=self.map.spawn_points,
            stage=self.current_stage,
            spawn_interval=5.0,
            player_tank=self.player_tank,
            game_map=self.map,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )

        self.bullets: List[Bullet] = []
        logger.info("Game reset complete.")

    def handle_events(self) -> None:
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                logger.info("Quit event received.")
                self._quit_game()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    logger.info("Escape key pressed, quitting game.")
                    self._quit_game()
                elif event.key == pygame.K_r and self.state != GameState.RUNNING:
                    logger.info("R key pressed, resetting game.")
                    self._reset_game()

            # Pass events to input handler only if game is running
            if self.state == GameState.RUNNING:
                self.input_handler.handle_event(event)

    def update(self) -> None:
        """Update game state."""
        if self.state != GameState.RUNNING:
            return

        dt: float = 1.0 / self.fps

        self.map.update(dt)
        # Update player tank (stores prev position) BEFORE movement
        self.player_tank.update(dt)

        # Drive player tank from input
        dx, dy = self.input_handler.get_movement_direction()
        if dx != 0 or dy != 0:
            self.player_tank.move(dx, dy, dt)
        if self.input_handler.consume_shoot():
            self._try_shoot(self.player_tank)

        for enemy in self.spawn_manager.enemy_tanks:
            enemy.update(dt)
            if enemy.consume_shoot():
                self._try_shoot(enemy)

        # Update all bullets
        for bullet in self.bullets:
            bullet.update(dt)
        # Remove inactive bullets
        self.bullets = [b for b in self.bullets if b.active]

        self.spawn_manager.update(dt, self.player_tank, self.map)

        # --- Prepare data for Collision Manager ---
        # Built AFTER updates so newly fired bullets are included
        destructible_tiles: List[Tile] = self.map.get_tiles_by_type([TileType.BRICK])
        impassable_tiles: List[Tile] = self.map.get_tiles_by_type(IMPASSABLE_TILE_TYPES)
        player_base: Optional[Tile] = self.map.get_base()

        player_bullets = [
            b for b in self.bullets if b.owner_type == OwnerType.PLAYER and b.active
        ]
        enemy_bullets = [
            b for b in self.bullets if b.owner_type == OwnerType.ENEMY and b.active
        ]

        self.collision_manager.check_collisions(
            player_tank=self.player_tank,
            player_bullets=player_bullets,
            enemy_tanks=self.spawn_manager.enemy_tanks,
            enemy_bullets=enemy_bullets,
            destructible_tiles=destructible_tiles,
            impassable_tiles=impassable_tiles,
            player_base=player_base,
        )

        events = self.collision_manager.get_collision_events()
        enemies_to_remove = self.collision_response_handler.process_collisions(events)
        for enemy in enemies_to_remove:
            self.spawn_manager.remove_enemy(enemy)

        if self.state == GameState.RUNNING:
            if self.spawn_manager.all_enemies_defeated():
                logger.info("All enemies defeated. Victory!")
                self.state = GameState.VICTORY
                self.current_stage += 1

    def _try_shoot(self, tank) -> None:
        """Attempt to fire a bullet for the given tank, respecting max_bullets."""
        active_count = sum(1 for b in self.bullets if b.owner is tank and b.active)
        if active_count < tank.max_bullets:
            bullet = tank.shoot()
            if bullet is not None:
                self.bullets.append(bullet)

    def _set_game_state(self, state: GameState) -> None:
        """Set the game state."""
        self.state = state

    def render(self) -> None:
        """Render the game state."""
        self.renderer.render(
            self.map,
            self.player_tank,
            self.spawn_manager.enemy_tanks,
            self.bullets,
            self.state,
        )

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
