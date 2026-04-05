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
    EffectType,
    CURTAIN_CLOSE_DURATION,
    CURTAIN_OPEN_DURATION,
    CURTAIN_STAGE_DISPLAY,
    VICTORY_PAUSE_DURATION,
    GAME_OVER_RISE_DURATION,
    GAME_OVER_HOLD_DURATION,
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

    _SELECTABLE_MENU_INDICES = (0, 2)  # Skip disabled "2 PLAYERS" at index 1

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
        self._state_timer: float = 0.0
        self._demo_mode: bool = False

        # Renderer for title screen (recreated with map dims in _load_stage)
        self.renderer: Renderer = Renderer(
            self.screen,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
        )

    def _reset_game(self) -> None:
        """Backward-compatible alias. Use _new_game() for new code."""
        self._new_game()
        self.state = GameState.RUNNING

    def _new_game(self) -> None:
        """Full reset for starting a new game. Does not set state."""
        self.current_stage = 1
        self.score = 0
        self._state_timer = 0.0
        self.player_tank = None
        self._load_stage()

    @property
    def _curtain_progress(self) -> float:
        """Compute curtain progress from _state_timer and current state."""
        if self.state == GameState.STAGE_CURTAIN_CLOSE:
            return min(1.0, self._state_timer / CURTAIN_CLOSE_DURATION)
        elif self.state == GameState.STAGE_CURTAIN_OPEN:
            return max(0.0, 1.0 - self._state_timer / CURTAIN_OPEN_DURATION)
        return 0.0

    def _load_stage(self) -> None:
        """Load/reload a stage. Preserves score, current_stage, and player progress."""
        logger.info(f"Loading stage {self.current_stage}...")

        # Preserve player progress across stages
        player_lives = self.player_tank.lives if self.player_tank is not None else 3
        player_star_level = (
            self.player_tank.star_level if self.player_tank is not None else 0
        )

        self.collision_manager = CollisionManager()

        # Map
        map_name = "demo_powerups.tmx" if self._demo_mode else "level_01.tmx"
        map_path = resource_path(f"assets/maps/{map_name}")
        self.map = Map(map_path, self.texture_manager)

        # Compute map pixel dimensions (sub-tile grid * sub-tile size)
        map_width_px = self.map.width * self.map.tile_size
        map_height_px = self.map.height * self.map.tile_size

        # Effect manager
        self.effect_manager = EffectManager(self.texture_manager)

        # Power-up manager (must be created before CollisionResponseHandler)
        self.power_up_manager = PowerUpManager(self.texture_manager, self.map)

        # Collision response handler
        self.collision_response_handler = CollisionResponseHandler(
            game_map=self.map,
            set_game_state=self._set_game_state,
            effect_manager=self.effect_manager,
            add_score=self._add_score,
            power_up_manager=self.power_up_manager,
        )

        # Player tank (spawn coords are in sub-tile units)
        start_x = self.map.player_spawn[0] * self.map.tile_size
        start_y = self.map.player_spawn[1] * self.map.tile_size
        self.player_tank = PlayerTank(
            start_x,
            start_y,
            self.tile_size,
            self.texture_manager,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )

        # Renderer (fixed logical surface with map centered inside)
        self.renderer = Renderer(
            self.screen,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
            map_width_px,
            map_height_px,
        )

        # SpawnManager
        self.spawn_manager = SpawnManager(
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

        # Restore player progress
        self.player_tank.lives = player_lives
        if player_star_level > 0:
            self.player_tank.star_level = player_star_level
            self.player_tank._apply_star_stats()
            self.player_tank._update_sprite()

        if self._demo_mode:
            self._spawn_demo_power_ups()

        logger.info("Stage load complete.")

    def _spawn_demo_power_ups(self) -> None:
        """Force-spawn all powerups at fixed positions for demo mode.

        Powerups are placed in the upper-left open area of the demo map,
        arranged in rows: 4 stars (top), helmet/clock/bomb (middle),
        shovel/extra_life (bottom). Pixel positions = sub-tile grid * 16.
        """
        demo_power_ups = [
            (PowerUpType.STAR, (32, 32)),
            (PowerUpType.STAR, (64, 32)),
            (PowerUpType.STAR, (96, 32)),
            (PowerUpType.STAR, (128, 32)),
            (PowerUpType.HELMET, (32, 96)),
            (PowerUpType.CLOCK, (64, 96)),
            (PowerUpType.BOMB, (96, 96)),
            (PowerUpType.SHOVEL, (32, 160)),
            (PowerUpType.EXTRA_LIFE, (64, 160)),
        ]
        for power_up_type, position in demo_power_ups:
            self.power_up_manager.spawn_power_up(
                power_up_type=power_up_type, position=position
            )
        logger.info(f"Demo: spawned {len(demo_power_ups)} power-ups")

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
                elif event.key == pygame.K_r and self.state == GameState.GAME_OVER:
                    logger.info("R key pressed, returning to title screen.")
                    self.state = GameState.TITLE_SCREEN
                    self._menu_selection = 0

            # Pass events to input handler only if game is running
            if self.state == GameState.RUNNING:
                self.input_handler.handle_event(event)

    def _handle_title_input(self, key: int) -> None:
        """Handle keyboard input on the title screen."""
        if key in (pygame.K_UP, pygame.K_DOWN):
            indices = self._SELECTABLE_MENU_INDICES
            if self._menu_selection in indices:
                pos = indices.index(self._menu_selection)
            else:
                pos = 0
            if key == pygame.K_UP:
                pos = (pos - 1) % len(indices)
            else:
                pos = (pos + 1) % len(indices)
            self._menu_selection = indices[pos]
        elif key == pygame.K_RETURN:
            if self._menu_selection in (0, 2):
                self._demo_mode = self._menu_selection == 2
                label = "Demo" if self._demo_mode else "1 Player"
                logger.info(f"{label} selected, starting game.")
                self._new_game()
                self.state = GameState.STAGE_CURTAIN_CLOSE
                self._state_timer = 0.0

    def update(self) -> None:
        """Update game state."""
        dt: float = 1.0 / self.fps

        if self.state == GameState.VICTORY:
            self._state_timer += dt
            if self._state_timer >= VICTORY_PAUSE_DURATION:
                self.current_stage += 1
                self._load_stage()
                self.state = GameState.STAGE_CURTAIN_CLOSE
                self._state_timer = 0.0
            return

        if self.state == GameState.STAGE_CURTAIN_CLOSE:
            self._state_timer += dt
            total = CURTAIN_CLOSE_DURATION + CURTAIN_STAGE_DISPLAY
            if self._state_timer >= total:
                self.state = GameState.STAGE_CURTAIN_OPEN
                self._state_timer = 0.0
            return

        if self.state == GameState.STAGE_CURTAIN_OPEN:
            self._state_timer += dt
            if self._state_timer >= CURTAIN_OPEN_DURATION:
                self.state = GameState.RUNNING
            return

        if self.state == GameState.GAME_OVER_ANIMATION:
            self._state_timer += dt
            total = GAME_OVER_RISE_DURATION + GAME_OVER_HOLD_DURATION
            if self._state_timer >= total:
                self.state = GameState.GAME_OVER
            return

        if self.state != GameState.RUNNING:
            return

        self.map.update(dt)
        # Update player tank (stores prev position) BEFORE movement
        self.player_tank.update(dt)

        # Drive player tank from input
        dx, dy = self.input_handler.get_movement_direction()
        if dx != 0 or dy != 0:
            self.player_tank.move(dx, dy, dt)
        if self.input_handler.consume_shoot():
            self._try_shoot(self.player_tank)

        # Ice detection and slide trigger for player
        self.player_tank._on_ice = self._is_on_ice(self.player_tank)
        if dx == 0 and dy == 0 and self.player_tank._on_ice:
            self.player_tank.start_slide()

        if self.freeze_timer > 0:
            self.freeze_timer -= dt
        else:
            for enemy in self.spawn_manager.enemy_tanks:
                enemy.update(dt)
                enemy._on_ice = self._is_on_ice(enemy)
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
            power_ups=self.power_up_manager.get_power_ups(),
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
            self._apply_power_up(collected)

        self.effect_manager.update(dt)

        if self.state == GameState.RUNNING:
            if self.spawn_manager.all_enemies_defeated():
                logger.info("All enemies defeated. Victory!")
                self.state = GameState.VICTORY
                self._state_timer = 0.0

    def _try_shoot(self, tank) -> None:
        """Attempt to fire a bullet for the given tank, respecting max_bullets."""
        active_count = sum(1 for b in self.bullets if b.owner is tank and b.active)
        if active_count < tank.max_bullets:
            bullet = tank.shoot()
            if bullet is not None:
                self.bullets.append(bullet)

    def _set_game_state(self, state: GameState) -> None:
        """Set the game state. Intercepts GAME_OVER to play rising text animation."""
        if state == GameState.GAME_OVER:
            self.state = GameState.GAME_OVER_ANIMATION
            self._state_timer = 0.0
            return
        self.state = state

    def _is_on_ice(self, tank) -> bool:
        """Check if the tank's center is over an ice tile."""
        center_x = int(tank.x + tank.width / 2)
        center_y = int(tank.y + tank.height / 2)
        grid_x = center_x // self.map.tile_size
        grid_y = center_y // self.map.tile_size
        tile = self.map.get_tile_at(grid_x, grid_y)
        return tile is not None and tile.type == TileType.ICE

    def _add_score(self, points: int) -> None:
        """Add points to the player's score."""
        self.score += points

    def _apply_power_up(self, power_up_type: PowerUpType) -> None:
        """Dispatch power-up effect by type."""
        if self.state != GameState.RUNNING:
            return
        if power_up_type == PowerUpType.HELMET:
            self._apply_helmet()
        elif power_up_type == PowerUpType.EXTRA_LIFE:
            self._apply_extra_life()
        elif power_up_type == PowerUpType.BOMB:
            self._apply_bomb()
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

    def _apply_bomb(self) -> None:
        """Destroy all active enemies on the map without awarding points."""
        for enemy in list(self.spawn_manager.enemy_tanks):
            self.effect_manager.spawn(
                EffectType.LARGE_EXPLOSION,
                float(enemy.rect.centerx),
                float(enemy.rect.centery),
            )
            self.spawn_manager.remove_enemy(enemy)
        logger.info("Bomb power-up applied: all enemies destroyed")

    def _apply_clock(self) -> None:
        """Freeze all enemies for the clock duration."""
        self.freeze_timer = CLOCK_FREEZE_DURATION
        logger.info(
            f"Clock power-up applied: enemies frozen for {CLOCK_FREEZE_DURATION}s"
        )

    def _apply_shovel(self) -> None:
        """Fortify base walls with steel, restoring destroyed bricks first."""
        if not self._shovel_original_tiles:
            tiles = self.map.get_base_surrounding_tiles(include_empty=True)
            # Restore destroyed and damaged tiles to full BRICK before fortifying
            for tile in tiles:
                if tile.type == TileType.EMPTY or tile.brick_variant != "full":
                    self.map.set_tile_type(tile, TileType.BRICK)
                    tile.brick_variant = "full"
                    tile.reset_rect()
            # Save original types AFTER restoration (so BRICK, not EMPTY)
            self._shovel_original_tiles = [(t, t.type) for t in tiles]
            for tile in tiles:
                self.map.set_tile_type(tile, TileType.STEEL)
            logger.info(
                f"Shovel power-up applied: base fortified for {SHOVEL_DURATION}s"
            )
        self.shovel_timer = SHOVEL_DURATION
        self._shovel_flash_timer = 0.0
        self._shovel_flash_showing_steel = True

    def _tick_shovel(self, dt: float) -> None:
        """Update shovel timer and flash logic."""
        if self.shovel_timer <= 0:
            return
        self.shovel_timer -= dt
        if self.shovel_timer <= 0:
            for tile, orig_type in self._shovel_original_tiles:
                if tile.type != TileType.EMPTY:
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
                    if tile.type != TileType.EMPTY:
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

        if self.state in (
            GameState.STAGE_CURTAIN_CLOSE,
            GameState.STAGE_CURTAIN_OPEN,
        ):
            self.renderer.render_curtain(self._curtain_progress, self.current_stage)
            return

        game_over_rise_progress = None
        if self.state == GameState.GAME_OVER_ANIMATION:
            game_over_rise_progress = min(
                1.0, self._state_timer / GAME_OVER_RISE_DURATION
            )

        self.renderer.render(
            self.map,
            self.player_tank,
            self.spawn_manager.enemy_tanks,
            self.bullets,
            self.effect_manager,
            self.state,
            self.score,
            power_ups=self.power_up_manager.get_power_ups(),
            game_over_rise_progress=game_over_rise_progress,
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
