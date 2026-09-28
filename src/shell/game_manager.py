import os
import pygame
from loguru import logger
from src.core.map import Map
from src.states.game_mode import GameMode
from src.states.screen import Screen
from src.utils.constants import (
    WINDOW_TITLE,
    FPS,
    TILE_SIZE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    LOGICAL_WIDTH,
    LOGICAL_HEIGHT,
)
from src.battle.battle import Battle
from src.cpu_partner.cpu_partner import CpuPartnerInput
from src.shell.screen_flow import BattleRequest, ScreenFlow
from src.shell.texture_manager import TextureManager
from src.shell.input_handler import InputHandler
from src.shell.renderer import Renderer
from src.shell.sound_manager import SoundManager
from src.shell.settings_manager import SettingsManager
from src.utils.paths import resource_path


def stage_map_path(stage: int) -> str:
    """The map file for ``stage``, falling back to level_01 if it has none."""
    map_name = f"level_{stage:02d}.tmx"
    map_path = resource_path(f"assets/maps/{map_name}")
    if not os.path.exists(map_path):
        logger.error(f"Map file not found: {map_name}; falling back to level_01.tmx")
        map_path = resource_path("assets/maps/level_01.tmx")
    return map_path


class GameManager:
    """The pygame adapter around the Screen Flow: window, events, Battles, drawing.

    The ``ScreenFlow`` decides which screen shows and when a Battle starts
    (ADR 0007). This class turns pygame events into menu actions, builds and
    steps the Battle the flow asks for, and draws what the flow reports.
    """

    def __init__(self, sound_manager: SoundManager | None = None) -> None:
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
        self.sound_manager: SoundManager = sound_manager or SoundManager(
            master_volume=self.settings_manager.master_volume
        )
        self.flow: ScreenFlow = ScreenFlow(self.settings_manager, self.sound_manager)
        # The Battle being fought, or the last one; None before the first game.
        self.battle: Battle | None = None

        # Renderer for title screen (recreated with map dims in _start_battle)
        self.renderer: Renderer = Renderer(
            self.screen,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
            LOGICAL_WIDTH,
            LOGICAL_HEIGHT,
        )

    def _start_battle(self, request: BattleRequest) -> None:
        """Start the Battle the Screen Flow asked for."""
        logger.info(f"Loading stage {request.stage}...")

        carried = {}
        if not request.new_game:
            assert self.battle is not None, "only a new game has no Battle before"
            carried = self.battle.carried_progress

        self.input_handler.reset()
        game_map = Map(stage_map_path(request.stage), self.texture_manager)
        self.battle = Battle(
            game_map,
            mode=request.mode,
            carried=carried,
            difficulty=request.difficulty,
            controller_instance_ids=self.input_handler.controller_instance_ids,
            atlas=self.texture_manager,
            sound=self.sound_manager,
            cpu_partner=(
                CpuPartnerInput() if request.mode is GameMode.ONE_PLAYER_CPU else None
            ),
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
        """Pass pygame events to the input handler, the Battle and the Screen Flow."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                logger.info("Quit event received.")
                self.flow.quit()

            self.input_handler.handle_event(event)
            if self.battle is not None:
                self.battle.handle_event(event)

        for action in self.input_handler.consume_menu_actions():
            before = self.flow.screen
            self.flow.handle(action)
            after = self.flow.screen
            if before is Screen.RUNNING and after is Screen.PAUSED:
                # Forget a stick held while pausing, so moving it again
                # moves the pause cursor.
                self.input_handler.reset()
            elif before is Screen.PAUSED and after is Screen.RUNNING:
                # The button that chose Resume (e.g. controller A) also
                # reached the Battle as a shot; drop it.
                if self.battle is not None:
                    self.battle.clear_pending_shoot()

    def update(self) -> None:
        """Step the Battle while it runs, then advance the Screen Flow."""
        dt: float = 1.0 / self.fps

        result = None
        if self.flow.battle_steps and self.battle is not None:
            result = self.battle.step(dt)
        self.flow.update(dt, result)

        request = self.flow.take_battle_request()
        if request is not None:
            self._start_battle(request)

    def render(self) -> None:
        """Draw what the Screen Flow shows."""
        flow = self.flow
        menu = flow.menu

        if flow.screen is Screen.TITLE_SCREEN:
            assert menu is not None
            self.renderer.render_title_screen(menu.labels, menu.selection)
            return

        if flow.screen in (Screen.STAGE_CURTAIN_CLOSE, Screen.STAGE_CURTAIN_OPEN):
            self.renderer.render_curtain(flow.curtain_progress, flow.curtain_stage)
            return

        if flow.screen is Screen.OPTIONS_MENU:
            assert menu is not None
            self.renderer.render_options_menu(
                self.settings_manager.master_volume,
                self.settings_manager.difficulty,
                menu.selection,
            )
            return

        if flow.screen is Screen.PAUSED:
            assert menu is not None
            self.renderer.render_pause_menu(menu.labels, menu.selection)
            return

        if flow.screen is Screen.EXIT or self.battle is None:
            return

        self.renderer.render(
            self.battle.scene(),
            flow.screen,
            game_over_rise_progress=flow.game_over_rise_progress,
        )

    def run(self) -> None:
        """Main game loop."""
        logger.info("Starting main game loop.")
        while self.flow.screen is not Screen.EXIT:
            self.handle_events()
            self.update()
            self.render()

            # Cap the frame rate
            self.clock.tick(self.fps)

        logger.info("Exiting main game loop.")
