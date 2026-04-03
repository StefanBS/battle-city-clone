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
    PowerUpType,
    HELMET_INVINCIBILITY_DURATION,
    CLOCK_FREEZE_DURATION,
    SHOVEL_DURATION,
    SHOVEL_WARNING_DURATION,
    SHOVEL_FLASH_INTERVAL,
    ENEMY_POINTS,
    EffectType,
)
from src.managers.collision_manager import CollisionManager
from src.managers.collision_response_handler import CollisionResponseHandler
from src.managers.effect_manager import EffectManager
from src.managers.texture_manager import TextureManager
from src.managers.input_handler import InputHandler
from src.managers.spawn_manager import SpawnManager
from src.managers.renderer import Renderer
from src.managers.power_up_manager import PowerUpManager
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

        self.state: GameState = GameState.TITLE_SCREEN
        self._menu_selection: int = 0  # 0 = 1 Player, 1 = 2 Players

        # Renderer for title screen (recreated with map dims in _reset_game)
        self.renderer: Renderer = Renderer(
            self.screen,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
        )

    def _reset_game(self) -> None:
        """Resets per-level game state. Display and textures are preserved."""
        logger.info("Resetting game state...")

        self.state: GameState = GameState.RUNNING
        self.current_stage: int = 1
        self.score: int = 0
        self.collision_manager: CollisionManager = CollisionManager()

        # Map
        map_path = resource_path("assets/maps/level_01.tmx")
        self.map: Map = Map(map_path, self.texture_manager)

        # Compute map pixel dimensions (sub-tile grid * sub-tile size)
        map_width_px: int = self.map.width * self.map.tile_size
        map_height_px: int = self.map.height * self.map.tile_size

        # Effect manager
        self.effect_manager: EffectManager = EffectManager(self.texture_manager)

        # Power-up manager (must be created before CollisionResponseHandler)
        self.power_up_manager: PowerUpManager = PowerUpManager(
            self.texture_manager, self.map
        )

        # Collision response handler
        self.collision_response_handler: CollisionResponseHandler = (
            CollisionResponseHandler(
                game_map=self.map,
                set_game_state=self._set_game_state,
                effect_manager=self.effect_manager,
                add_score=self._add_score,
                power_up_manager=self.power_up_manager,
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
            effect_manager=self.effect_manager,
        )

        self.bullets: List[Bullet] = []
        self.freeze_timer: float = 0.0
        self.shovel_timer: float = 0.0
        self._shovel_original_tiles: List[tuple] = []
        self._shovel_flash_timer: float = 0.0
        self._shovel_flash_showing_steel: bool = True
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
                elif self.state == GameState.TITLE_SCREEN:
                    self._handle_title_input(event.key)
                elif event.key == pygame.K_r and self.state in (
                    GameState.GAME_OVER,
                    GameState.VICTORY,
                ):
                    logger.info("R key pressed, returning to title screen.")
                    self.state = GameState.TITLE_SCREEN
                    self._menu_selection = 0

            # Pass events to input handler only if game is running
            if self.state == GameState.RUNNING:
                self.input_handler.handle_event(event)

    def _handle_title_input(self, key: int) -> None:
        """Handle keyboard input on the title screen."""
        if key in (pygame.K_UP, pygame.K_DOWN):
            self._menu_selection = 1 - self._menu_selection
        elif key == pygame.K_RETURN:
            if self._menu_selection == 0:
                logger.info("1 Player selected, starting game.")
                self._reset_game()
            # 2 Players (index 1) is disabled — do nothing

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

        if self.freeze_timer > 0:
            self.freeze_timer -= dt
        else:
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
        self.power_up_manager.update(dt)
        self._tick_shovel(dt)

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
            power_up=self.power_up_manager.get_power_up(),
        )

        events = self.collision_manager.get_collision_events()
        enemies_to_remove = self.collision_response_handler.process_collisions(events)
        for enemy in enemies_to_remove:
            self.spawn_manager.remove_enemy(enemy)
            if enemy.is_carrier:
                self.power_up_manager.spawn_power_up(
                    self.player_tank, self.spawn_manager.enemy_tanks
                )

        # Apply deferred power-up effect
        collected = self.collision_response_handler.consume_collected_power_up()
        if collected is not None:
            self._apply_power_up(collected, set(enemies_to_remove))

        self.effect_manager.update(dt)

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

    def _add_score(self, points: int) -> None:
        """Add points to the player's score."""
        self.score += points

    def _apply_power_up(
        self, power_up_type: PowerUpType, already_scored: Optional[set] = None
    ) -> None:
        """Dispatch power-up effect by type."""
        if self.state != GameState.RUNNING:
            return
        if power_up_type == PowerUpType.HELMET:
            self._apply_helmet()
        elif power_up_type == PowerUpType.EXTRA_LIFE:
            self._apply_extra_life()
        elif power_up_type == PowerUpType.BOMB:
            self._apply_bomb(already_scored if already_scored is not None else set())
        elif power_up_type == PowerUpType.CLOCK:
            self._apply_clock()
        elif power_up_type == PowerUpType.SHOVEL:
            self._apply_shovel()
        elif power_up_type == PowerUpType.STAR:
            self._apply_star()
        else:
            logger.warning(f"Unhandled power-up type: {power_up_type}")

    def _apply_helmet(self) -> None:
        """Grant temporary invincibility to the player."""
        self.player_tank.activate_invincibility(HELMET_INVINCIBILITY_DURATION)
        logger.info(
            f"Helmet power-up applied: player invincible "
            f"for {HELMET_INVINCIBILITY_DURATION}s"
        )

    def _apply_extra_life(self) -> None:
        """Award the player one extra life."""
        self.player_tank.lives += 1
        logger.info(f"Extra Life power-up applied: lives now {self.player_tank.lives}")

    def _apply_bomb(self, already_scored: set) -> None:
        """Destroy all active enemies on the map."""
        for enemy in list(self.spawn_manager.enemy_tanks):
            self.effect_manager.spawn(
                EffectType.LARGE_EXPLOSION,
                float(enemy.rect.centerx),
                float(enemy.rect.centery),
            )
            if enemy not in already_scored:
                self._add_score(ENEMY_POINTS.get(enemy.tank_type, 0))
            self.spawn_manager.remove_enemy(enemy)
        logger.info("Bomb power-up applied: all enemies destroyed")

    def _apply_clock(self) -> None:
        """Freeze all enemies for the clock duration."""
        self.freeze_timer = CLOCK_FREEZE_DURATION
        logger.info(
            f"Clock power-up applied: enemies frozen for {CLOCK_FREEZE_DURATION}s"
        )

    def _apply_shovel(self) -> None:
        """Fortify base walls with steel."""
        if self.shovel_timer > 0:
            self.shovel_timer = SHOVEL_DURATION
            self._shovel_flash_timer = 0.0
            self._shovel_flash_showing_steel = True
            return
        tiles = self.map.get_base_surrounding_tiles()
        self._shovel_original_tiles = [(t, t.type) for t in tiles]
        for tile in tiles:
            self.map.set_tile_type(tile, TileType.STEEL)
        self.shovel_timer = SHOVEL_DURATION
        self._shovel_flash_timer = 0.0
        self._shovel_flash_showing_steel = True
        logger.info(f"Shovel power-up applied: base fortified for {SHOVEL_DURATION}s")

    def _tick_shovel(self, dt: float) -> None:
        """Update shovel timer and flash logic."""
        if self.shovel_timer <= 0:
            return
        self.shovel_timer -= dt
        if self.shovel_timer <= 0:
            for tile, orig_type in self._shovel_original_tiles:
                self.map.set_tile_type(tile, orig_type)
            self._shovel_original_tiles = []
            logger.info("Shovel expired: base walls reverted")
            return
        if self.shovel_timer <= SHOVEL_WARNING_DURATION:
            self._shovel_flash_timer += dt
            should_show_steel = (
                self._shovel_flash_timer % (SHOVEL_FLASH_INTERVAL * 2)
                < SHOVEL_FLASH_INTERVAL
            )
            if should_show_steel != self._shovel_flash_showing_steel:
                self._shovel_flash_showing_steel = should_show_steel
                for tile, orig_type in self._shovel_original_tiles:
                    target = TileType.STEEL if should_show_steel else orig_type
                    self.map.set_tile_type(tile, target)

    def _apply_star(self) -> None:
        """Apply star upgrade to the player tank."""
        self.player_tank.apply_star()
        logger.info(
            f"Star power-up applied: player at tier {self.player_tank.star_level}"
        )

    def render(self) -> None:
        """Render the game state."""
        if self.state == GameState.TITLE_SCREEN:
            self.renderer.render_title_screen(self._menu_selection)
            return

        self.renderer.render(
            self.map,
            self.player_tank,
            self.spawn_manager.enemy_tanks,
            self.bullets,
            self.effect_manager,
            self.state,
            self.score,
            power_up=self.power_up_manager.get_power_up(),
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
