import os
import pygame
from collections import deque
from collections.abc import Callable
from loguru import logger
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.tile import Tile
from src.states.game_mode import GameMode
from src.states.game_state import GameState
from src.utils.constants import (
    VOLUME_ADJUSTMENT_STEP,
    WINDOW_TITLE,
    FPS,
    TILE_SIZE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    LOGICAL_WIDTH,
    LOGICAL_HEIGHT,
    EffectType,
    ENEMY_POINTS,
    POWERUP_COLLECT_POINTS,
    SPAWN_INVINCIBILITY_DURATION,
    CURTAIN_CLOSE_DURATION,
    CURTAIN_OPEN_DURATION,
    CURTAIN_STAGE_DISPLAY,
    VICTORY_PAUSE_DURATION,
    GAME_OVER_RISE_DURATION,
    GAME_OVER_HOLD_DURATION,
    MAX_STAGE,
    MenuAction,
)
from src.managers.collision_manager import CollisionManager
from src.managers.collision_response_handler import CollisionResponseHandler
from src.managers.effect_manager import EffectManager
from src.managers.texture_manager import TextureManager
from src.managers.input_handler import InputHandler
from src.managers.menu_controller import MenuController, MenuItem
from src.managers.outcomes import (
    BaseDestroyed,
    CarrierHit,
    CollisionOutcome,
    EnemyDestroyed,
    PlayerDestroyed,
    PowerUpCollected,
)
from src.managers.player_input import CTRL_START_BUTTON
from src.managers.spawn_manager import SpawnManager
from src.managers.renderer import Renderer
from src.managers.power_up_manager import PowerUpManager
from src.managers.player_manager import PlayerManager
from src.managers.sound_manager import SoundManager
from src.managers.tank_stepper import TankStepper
from src.managers.world_view import WorldView, build_world_view
from src.managers.settings_manager import SettingsManager
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
        self.settings_manager: SettingsManager = SettingsManager()
        self.sound_manager: SoundManager = SoundManager(
            master_volume=self.settings_manager.master_volume
        )
        self.player_manager: PlayerManager = PlayerManager(
            self.texture_manager, self.sound_manager
        )

        self.state: GameState = GameState.TITLE_SCREEN
        self._options_from_pause: bool = False
        self._state_timer: float = 0.0
        self._game_mode: GameMode = GameMode.ONE_PLAYER
        self._post_curtain_state: GameState = GameState.RUNNING

        self._title_menu, self._pause_menu, self._options_menu = self._build_menus()

        self._timed_transitions: dict[GameState, tuple[float, Callable[[], None]]] = {
            GameState.VICTORY: (
                VICTORY_PAUSE_DURATION,
                self._on_victory_finished,
            ),
            GameState.STAGE_CURTAIN_CLOSE: (
                CURTAIN_CLOSE_DURATION + CURTAIN_STAGE_DISPLAY,
                self._on_curtain_close_finished,
            ),
            GameState.STAGE_CURTAIN_OPEN: (
                CURTAIN_OPEN_DURATION,
                self._on_curtain_open_finished,
            ),
            GameState.GAME_OVER_ANIMATION: (
                GAME_OVER_RISE_DURATION + GAME_OVER_HOLD_DURATION,
                self._on_game_over_animation_finished,
            ),
        }

        # Renderer for title screen (recreated with map dims in _load_stage)
        self.renderer: Renderer = Renderer(
            self.screen,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
        )

    def _build_menus(self) -> tuple[MenuController, MenuController, MenuController]:
        # Late-bound so tests can swap sound_manager after construction.
        def play_select() -> None:
            self.sound_manager.play("menu_select")

        title = MenuController(
            items=[
                MenuItem(
                    "1 Player",
                    on_confirm=lambda: self._start_game(GameMode.ONE_PLAYER),
                ),
                MenuItem(
                    "2 Players",
                    on_confirm=lambda: self._start_game(GameMode.TWO_PLAYERS),
                ),
                MenuItem(
                    "1 Player + CPU",
                    on_confirm=lambda: self._start_game(GameMode.ONE_PLAYER_CPU),
                ),
                MenuItem("Options", on_confirm=lambda: self._open_options(False)),
                MenuItem("Quit", on_confirm=self._quit_game),
            ],
            on_select=play_select,
        )
        pause = MenuController(
            items=[
                MenuItem("Resume", on_confirm=self._resume_game),
                MenuItem("Options", on_confirm=lambda: self._open_options(True)),
                MenuItem("Title Screen", on_confirm=self._return_to_title),
                MenuItem("Quit", on_confirm=self._quit_game),
            ],
            on_select=play_select,
            on_back=self._resume_game,
        )
        options = MenuController(
            items=[
                MenuItem(
                    "Difficulty",
                    on_left=lambda: self._cycle_difficulty(-1),
                    on_right=lambda: self._cycle_difficulty(1),
                ),
                MenuItem(
                    "Volume",
                    on_left=lambda: self._adjust_volume(-VOLUME_ADJUSTMENT_STEP),
                    on_right=lambda: self._adjust_volume(VOLUME_ADJUSTMENT_STEP),
                ),
                MenuItem("Back", on_confirm=self._exit_options),
            ],
            on_select=play_select,
            on_back=self._exit_options,
        )
        return title, pause, options

    def _reset_game(self) -> None:
        """Start a new game and immediately enter RUNNING state (used by tests)."""
        self._new_game()
        self.state = GameState.RUNNING

    def _new_game(self) -> None:
        """Full reset for starting a new game. Does not set state."""
        self.current_stage = 1
        self._state_timer = 0.0
        self.player_manager.reset()
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

        self.input_handler.reset()

        # Preserve player progress across stages
        self.player_manager.preserve_state()

        self.collision_manager = CollisionManager()

        # Map
        map_name = f"level_{self.current_stage:02d}.tmx"
        map_path = resource_path(f"assets/maps/{map_name}")
        if not os.path.exists(map_path):
            logger.error(
                f"Map file not found: {map_name}; falling back to level_01.tmx"
            )
            map_path = resource_path("assets/maps/level_01.tmx")
        self.map = Map(map_path, self.texture_manager)

        map_width_px = self.map.width_px
        map_height_px = self.map.height_px

        # Effect manager
        self.effect_manager = EffectManager(self.texture_manager)

        # Power-up manager (must be created before CollisionResponseHandler)
        self.power_up_manager = PowerUpManager(self.texture_manager, self.map)

        # Collision response handler
        self.collision_response_handler = CollisionResponseHandler(
            game_map=self.map,
            effect_manager=self.effect_manager,
            power_up_manager=self.power_up_manager,
            sound_manager=self.sound_manager,
        )

        self.player_manager.create_players(
            self.map,
            controller_instance_ids=self.input_handler.controller_instance_ids,
            mode=self._game_mode,
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
        effective_difficulty = (
            self.map.difficulty_override
            if self.map.difficulty_override is not None
            else self.settings_manager.difficulty
        )
        self.spawn_manager = SpawnManager(
            texture_manager=self.texture_manager,
            game_map=self.map,
            enemy_composition=self.map.enemy_composition,
            spawn_interval=self.map.spawn_interval,
            player_tanks=self.player_manager.get_active_players(),
            effect_manager=self.effect_manager,
            difficulty=effective_difficulty,
            powerup_carrier_indices=self.map.powerup_carrier_indices,
            on_carrier_spawned=self.power_up_manager.clear,
        )

        # Steps every tank; recreated per stage so no bullet outlives it.
        self.tank_stepper = TankStepper(self.map)

        # Restore player progress
        self.player_manager.restore_state()

        # Grant spawn invincibility (after progress restoration)
        for player in self.player_manager.get_active_players():
            player.activate_invincibility(SPAWN_INVINCIBILITY_DURATION)

        logger.info("Stage load complete.")

    def handle_events(self) -> None:
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                logger.info("Quit event received.")
                self._quit_game()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._handle_escape()
            elif event.type == pygame.CONTROLLERBUTTONDOWN:
                if event.button == CTRL_START_BUTTON:
                    self._handle_escape()

            self.input_handler.handle_event(event)
            self.player_manager.handle_event(event)

        if self.state != GameState.RUNNING:
            self._process_menu_actions()

    def _process_menu_actions(self) -> None:
        """Poll and route menu actions from InputHandler."""
        menu = self._active_menu()
        for action in self.input_handler.consume_menu_actions():
            if menu is not None:
                menu.handle_action(action)
            elif action == MenuAction.CONFIRM and self.state == GameState.GAME_COMPLETE:
                logger.info("Returning to title screen.")
                self._return_to_title()

    def _active_menu(self) -> MenuController | None:
        if self.state == GameState.TITLE_SCREEN:
            return self._title_menu
        if self.state == GameState.PAUSED:
            return self._pause_menu
        if self.state == GameState.OPTIONS_MENU:
            return self._options_menu
        return None

    def _handle_escape(self) -> None:
        """Handle ESC key based on current state.

        Only acts during RUNNING, PAUSED, and OPTIONS_MENU.
        Ignored during animations, game over, and title screen.
        """
        if self.state == GameState.RUNNING:
            logger.info("Game paused.")
            self.sound_manager.stop_loops()
            self._pause_menu.reset()
            self.state = GameState.PAUSED
            # Drop any menu actions queued while RUNNING (e.g. a held UP key
            # that emitted a KEYDOWN before START was pressed), otherwise they
            # would jump the pause selector on the first frame.
            self.input_handler.reset()
        elif self.state == GameState.PAUSED:
            self._resume_game()
        elif self.state == GameState.OPTIONS_MENU:
            self._exit_options()

    def _resume_game(self) -> None:
        """Transition from PAUSED back to RUNNING.

        Clears any buffered shoot input so the button press that confirmed
        the menu (e.g. controller A) does not leak into gameplay as a bullet.
        """
        logger.info("Game resumed.")
        self.state = GameState.RUNNING
        self.player_manager.clear_pending_shoot()

    def _exit_options(self) -> None:
        """Save settings and return to the screen that opened options."""
        self.settings_manager.save()
        if self._options_from_pause:
            self.state = GameState.PAUSED
        else:
            self.state = GameState.TITLE_SCREEN

    def _start_game(self, mode: GameMode) -> None:
        self._game_mode = mode
        logger.info(f"{mode.value} selected, starting game.")
        self._new_game()
        self.state = GameState.STAGE_CURTAIN_CLOSE
        self._state_timer = 0.0
        self.sound_manager.play("stage_start")

    def _open_options(self, from_pause: bool) -> None:
        self._options_from_pause = from_pause
        self._options_menu.reset()
        self.state = GameState.OPTIONS_MENU

    def _return_to_title(self) -> None:
        self.sound_manager.stop_loops()
        self._title_menu.reset()
        self.state = GameState.TITLE_SCREEN

    def _cycle_difficulty(self, step: int) -> None:
        self.settings_manager.cycle_difficulty(step)
        self.sound_manager.play("menu_select")

    def _adjust_volume(self, delta: float) -> None:
        self.settings_manager.adjust_volume(delta)
        self.sound_manager.set_master_volume(self.settings_manager.master_volume)
        self.sound_manager.play("menu_select")

    def update(self) -> None:
        """Update game state."""
        dt: float = 1.0 / self.fps

        if self.state in (GameState.PAUSED, GameState.OPTIONS_MENU):
            return

        transition = self._timed_transitions.get(self.state)
        if transition is not None:
            threshold, on_finished = transition
            self._state_timer += dt
            if self._state_timer >= threshold:
                on_finished()
                self._state_timer = 0.0
            return

        if self.state != GameState.RUNNING:
            return

        self.map.update(dt)
        self.player_manager.observe(self._world_view())
        self.player_manager.update(dt, self.tank_stepper)

        active_players = self.player_manager.get_active_players()

        if not self.spawn_manager.enemies_frozen:
            # When 0 or 1 active players, the AI target is the same for every
            # enemy and can be hoisted out of the per-enemy loop. Only 2P mode
            # needs the per-enemy min() to pick the nearest player.
            num_players = len(active_players)
            shared_pos: tuple[float, float] | None = None
            if num_players == 1:
                p = active_players[0]
                shared_pos = (p.x, p.y)

            for enemy in self.spawn_manager.enemy_tanks:
                if num_players >= 2:
                    closest = min(
                        active_players,
                        key=lambda p: abs(p.x - enemy.x) + abs(p.y - enemy.y),
                    )
                    closest_pos: tuple[float, float] | None = (closest.x, closest.y)
                else:
                    closest_pos = shared_pos
                enemy.target_position = closest_pos
                if self.tank_stepper.step(enemy, enemy, dt).fired:
                    self.sound_manager.play("shoot")

        # Engine sound: plays when any tank is moving
        any_moving = any(p.is_moving for p in active_players) or any(
            e.is_moving for e in self.spawn_manager.enemy_tanks
        )
        self.sound_manager.update_engine(any_moving)

        self.tank_stepper.update_bullets(dt)

        self.spawn_manager.update(dt, active_players, self.map)
        self.power_up_manager.update(dt)

        # --- Prepare data for Collision Manager ---
        # Built AFTER updates so newly fired bullets are included
        tank_blocking_tiles: list[Tile] = self.map.get_blocking_tiles()
        bullet_blocking_tiles: list[Tile] = self.map.get_bullet_blocking_tiles()
        player_base: Tile | None = self.map.get_base()

        active_power_ups = self.power_up_manager.active_power_ups

        self.collision_manager.check_collisions(
            player_tanks=active_players,
            enemy_tanks=self.spawn_manager.enemy_tanks,
            bullets=self.tank_stepper.bullets,
            tank_blocking_tiles=tank_blocking_tiles,
            bullet_blocking_tiles=bullet_blocking_tiles,
            player_base=player_base,
            power_ups=active_power_ups,
        )

        events = self.collision_manager.get_collision_events()
        self._apply_outcomes(self.collision_response_handler.process_collisions(events))

        # Powerup blink sound: plays when any powerup is active
        self.sound_manager.update_powerup_blink(bool(active_power_ups))

        self.effect_manager.update(dt)

        # The only place Game Over is decided; it wins over Victory.
        if self.map.is_base_destroyed or self.player_manager.is_game_over():
            logger.info("Game over.")
            self._set_game_state(GameState.GAME_OVER)
        elif self.spawn_manager.all_enemies_defeated():
            logger.info("All enemies defeated. Victory!")
            self._set_game_state(GameState.VICTORY)

    def _apply_outcomes(self, outcomes: list[CollisionOutcome]) -> None:
        """Apply a frame's outcomes, and the outcomes they cause, in order."""
        queue = deque(outcomes)
        while queue:
            match queue.popleft():
                case CarrierHit(enemy=enemy):
                    self._drop_carrier_power_up(enemy)
                case EnemyDestroyed(enemy=enemy, by=by):
                    # A bullet and a Grenade can both destroy it in one frame.
                    if enemy not in self.spawn_manager.enemy_tanks:
                        continue
                    self.spawn_manager.remove_enemy(enemy)
                    self.effect_manager.spawn_at_rect(
                        EffectType.LARGE_EXPLOSION, enemy.rect
                    )
                    self.sound_manager.play("explosion")
                    if by is not None:
                        self.player_manager.add_score(
                            ENEMY_POINTS.get(enemy.tank_type, 0),
                            player_id=by.player_id,
                        )
                    # A Grenade kill is a Carrier's only drop without a hit.
                    self._drop_carrier_power_up(enemy)
                case PlayerDestroyed(player=player):
                    # Before handle_player_death moves it to its spawn point.
                    self.effect_manager.spawn_at_rect(
                        EffectType.LARGE_EXPLOSION, player.rect
                    )
                    self.sound_manager.play("explosion")
                    self.player_manager.handle_player_death(player)
                case BaseDestroyed():
                    pass  # Game Over is decided once all outcomes are applied.
                case PowerUpCollected(power_up_type=power_up_type, player=player):
                    self.player_manager.add_score(
                        POWERUP_COLLECT_POINTS, player_id=player.player_id
                    )
                    self.sound_manager.play("powerup")
                    queue.extend(
                        self.power_up_manager.apply(
                            power_up_type, player, self.spawn_manager
                        )
                    )

    def _drop_carrier_power_up(self, enemy: EnemyTank) -> None:
        """Make a Carrier's Power-Up appear; a Carrier drops only once."""
        if not enemy.is_carrier:
            return
        enemy.stop_carrying()
        self.power_up_manager.spawn_power_up(
            [
                *self.player_manager.get_active_players(),
                *self.spawn_manager.enemy_tanks,
            ]
        )

    def _world_view(self) -> WorldView:
        """Snapshot the current battlefield for the Players' inputs."""
        return build_world_view(
            self.map,
            players=self.player_manager.players,
            enemies=self.spawn_manager.enemy_tanks,
            enemies_frozen=self.spawn_manager.enemies_frozen,
            power_ups=self.power_up_manager.active_power_ups,
            bullets=self.tank_stepper.bullets,
        )

    def _on_victory_finished(self) -> None:
        if self.current_stage >= MAX_STAGE:
            self._set_game_state(GameState.GAME_COMPLETE)
            return
        self.current_stage += 1
        self._load_stage()
        self.state = GameState.STAGE_CURTAIN_CLOSE
        self.sound_manager.play("stage_start")

    def _on_curtain_close_finished(self) -> None:
        self.state = GameState.STAGE_CURTAIN_OPEN

    def _on_curtain_open_finished(self) -> None:
        self.state = self._post_curtain_state
        self._post_curtain_state = GameState.RUNNING
        if self.state == GameState.TITLE_SCREEN:
            self._title_menu.reset()

    def _on_game_over_animation_finished(self) -> None:
        logger.info("Wiping to title screen.")
        self._post_curtain_state = GameState.TITLE_SCREEN
        self.state = GameState.STAGE_CURTAIN_CLOSE

    def _set_game_state(self, state: GameState) -> None:
        """Set the game state with sound management."""
        self.sound_manager.stop_loops()
        if state == GameState.GAME_OVER:
            self.state = GameState.GAME_OVER_ANIMATION
            self._state_timer = 0.0
            self.sound_manager.play("game_over")
            return
        if state == GameState.VICTORY:
            self._state_timer = 0.0
            self.sound_manager.play("victory")
        self.state = state

    def render(self) -> None:
        """Render the game state."""
        if self.state == GameState.TITLE_SCREEN:
            self.renderer.render_title_screen(
                self._title_menu.labels, self._title_menu.selection
            )
            return

        if self.state in (
            GameState.STAGE_CURTAIN_CLOSE,
            GameState.STAGE_CURTAIN_OPEN,
        ):
            stage = (
                self.current_stage
                if self._post_curtain_state == GameState.RUNNING
                else None
            )
            self.renderer.render_curtain(self._curtain_progress, stage)
            return

        if self.state == GameState.OPTIONS_MENU:
            self.renderer.render_options_menu(
                self.settings_manager.master_volume,
                self.settings_manager.difficulty,
                self._options_menu.selection,
            )
            return

        if self.state == GameState.PAUSED:
            self.renderer.render_pause_menu(
                self._pause_menu.labels, self._pause_menu.selection
            )
            return

        if self.state == GameState.EXIT:
            return

        game_over_rise_progress = None
        if self.state == GameState.GAME_OVER_ANIMATION:
            game_over_rise_progress = min(
                1.0, self._state_timer / GAME_OVER_RISE_DURATION
            )

        self.renderer.render(
            self.map,
            self.player_manager.players,
            self.spawn_manager.enemy_tanks,
            self.tank_stepper.bullets,
            self.effect_manager,
            self.state,
            self.player_manager.scores,
            power_ups=self.power_up_manager.active_power_ups,
            game_over_rise_progress=game_over_rise_progress,
            cpu_partner_ids=self.player_manager.cpu_partner_ids,
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
        self.sound_manager.stop_loops()
        self.state = GameState.EXIT
