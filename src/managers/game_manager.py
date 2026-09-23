import os
import pygame
from collections.abc import Callable
from loguru import logger
from src.core.map import Map
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
    CURTAIN_CLOSE_DURATION,
    CURTAIN_OPEN_DURATION,
    CURTAIN_STAGE_DISPLAY,
    VICTORY_PAUSE_DURATION,
    GAME_OVER_RISE_DURATION,
    GAME_OVER_HOLD_DURATION,
    MAX_STAGE,
    MenuAction,
)
from src.managers.battle import Battle, BattleResult
from src.managers.player_manager import CarriedProgress
from src.managers.texture_manager import TextureManager
from src.managers.input_handler import InputHandler
from src.managers.menu_controller import MenuController, MenuItem
from src.managers.player_input import CTRL_START_BUTTON
from src.managers.renderer import Renderer
from src.managers.sound_manager import SoundManager
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
        # The Battle being fought, or the last one; None before the first game.
        self.battle: Battle | None = None
        self.current_stage: int = 1

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

        # Renderer for title screen (recreated with map dims in _start_battle)
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
        self._start_battle(carried={})

    @property
    def _curtain_progress(self) -> float:
        """Compute curtain progress from _state_timer and current state."""
        if self.state == GameState.STAGE_CURTAIN_CLOSE:
            return min(1.0, self._state_timer / CURTAIN_CLOSE_DURATION)
        elif self.state == GameState.STAGE_CURTAIN_OPEN:
            return max(0.0, 1.0 - self._state_timer / CURTAIN_OPEN_DURATION)
        return 0.0

    def _load_stage_map(self) -> Map:
        """Load the current Stage's map, falling back to level_01 if missing."""
        map_name = f"level_{self.current_stage:02d}.tmx"
        map_path = resource_path(f"assets/maps/{map_name}")
        if not os.path.exists(map_path):
            logger.error(
                f"Map file not found: {map_name}; falling back to level_01.tmx"
            )
            map_path = resource_path("assets/maps/level_01.tmx")
        return Map(map_path, self.texture_manager)

    def _start_battle(self, carried: dict[int, CarriedProgress]) -> None:
        """Start a Battle for the current Stage with the Players' progress."""
        logger.info(f"Loading stage {self.current_stage}...")

        self.input_handler.reset()
        game_map = self._load_stage_map()
        self.battle = Battle(
            game_map,
            mode=self._game_mode,
            carried=carried,
            difficulty=self.settings_manager.difficulty,
            controller_instance_ids=self.input_handler.controller_instance_ids,
            texture_manager=self.texture_manager,
            sound=self.sound_manager,
        )

        # Renderer (fixed logical surface with map centered inside)
        self.renderer = Renderer(
            self.screen,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
            game_map.width_px,
            game_map.height_px,
        )

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
            if self.battle is not None:
                self.battle.handle_event(event)

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
        if self.battle is not None:
            self.battle.clear_pending_shoot()

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

        if self.state != GameState.RUNNING or self.battle is None:
            return

        match self.battle.step(dt):
            case BattleResult.GAME_OVER:
                self._set_game_state(GameState.GAME_OVER)
            case BattleResult.VICTORY:
                self._set_game_state(GameState.VICTORY)

    def _on_victory_finished(self) -> None:
        if self.current_stage >= MAX_STAGE:
            self._set_game_state(GameState.GAME_COMPLETE)
            return
        self.current_stage += 1
        self._start_battle(self.battle.carried_progress)
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

        battle = self.battle
        if battle is None:
            return
        self.renderer.render(
            battle.map,
            battle.player_manager.players,
            battle.enemy_manager.enemies,
            battle.tank_stepper.bullets,
            battle.effect_manager,
            self.state,
            battle.player_manager.scores,
            power_ups=battle.power_up_manager.active_power_ups,
            game_over_rise_progress=game_over_rise_progress,
            cpu_partner_ids=battle.player_manager.cpu_partner_ids,
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
