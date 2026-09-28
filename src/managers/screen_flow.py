"""The Screen Flow: the screens around the Battles, and which Stage comes next."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from src.managers.menu_controller import MenuController, MenuItem
from src.states.battle_result import BattleResult
from src.states.game_mode import GameMode
from src.states.screen import Screen
from src.utils.constants import (
    CURTAIN_CLOSE_DURATION,
    CURTAIN_OPEN_DURATION,
    CURTAIN_STAGE_DISPLAY,
    Difficulty,
    GAME_OVER_HOLD_DURATION,
    GAME_OVER_RISE_DURATION,
    MAX_STAGE,
    MenuAction,
    VICTORY_PAUSE_DURATION,
    VOLUME_ADJUSTMENT_STEP,
)

if TYPE_CHECKING:
    from src.managers.settings_manager import SettingsManager
    from src.managers.sound_manager import SoundManager


@dataclass(frozen=True)
class MenuView:
    """What to draw for the active menu."""

    labels: list[str]
    selection: int


@dataclass(frozen=True)
class BattleRequest:
    """A Battle the adapter should start.

    A new game starts with nothing carried; otherwise the Battle is built
    from the last Battle's ``carried_progress``.
    """

    stage: int
    mode: GameMode
    new_game: bool
    difficulty: Difficulty


class ScreenFlow:
    """Moves between the screens around the Battles.

    It never holds a Battle (ADR 0007): the adapter steps the Battle while
    ``battle_steps`` is true, passes each frame's ``BattleResult`` to
    ``update`` and builds a Battle for each ``take_battle_request()``.
    """

    def __init__(self, settings: SettingsManager, sound: SoundManager) -> None:
        self._settings = settings
        self._sound = sound
        self.screen: Screen = Screen.TITLE_SCREEN
        self.stage: int = 1
        self._mode: GameMode = GameMode.ONE_PLAYER
        self._battle_request: BattleRequest | None = None
        self._screen_timer: float = 0.0
        # Where the curtain opens onto: the Battle, or the title screen after
        # Game Over.
        self._behind_curtain: Screen = Screen.RUNNING
        self._options_from_pause: bool = False
        self._title_menu = MenuController(
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
                MenuItem("Quit", on_confirm=self.quit),
            ],
            on_select=self._play_select,
        )
        self._pause_menu = MenuController(
            items=[
                MenuItem("Resume", on_confirm=self._resume),
                MenuItem("Options", on_confirm=lambda: self._open_options(True)),
                MenuItem("Title Screen", on_confirm=self._return_to_title),
                MenuItem("Quit", on_confirm=self.quit),
            ],
            on_select=self._play_select,
            on_back=self._resume,
        )
        self._options_menu = MenuController(
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
                MenuItem("Back", on_confirm=self._leave_options),
            ],
            on_select=self._play_select,
            on_back=self._leave_options,
        )
        self._timed_screens: dict[Screen, tuple[float, Callable[[], None]]] = {
            Screen.VICTORY: (VICTORY_PAUSE_DURATION, self._on_victory_pause_finished),
            Screen.STAGE_CURTAIN_CLOSE: (
                CURTAIN_CLOSE_DURATION + CURTAIN_STAGE_DISPLAY,
                self._on_curtain_closed,
            ),
            Screen.STAGE_CURTAIN_OPEN: (
                CURTAIN_OPEN_DURATION,
                self._on_curtain_opened,
            ),
            Screen.GAME_OVER_ANIMATION: (
                GAME_OVER_RISE_DURATION + GAME_OVER_HOLD_DURATION,
                self._on_game_over_animation_finished,
            ),
        }

    def handle(self, action: MenuAction) -> None:
        """Act on one menu action, in the order it happened.

        PAUSE pauses a running Battle and resumes a paused one. Screens
        without a menu ignore every other menu action.
        """
        if action is MenuAction.PAUSE:
            self._toggle_pause()
            return
        if self.screen is Screen.GAME_COMPLETE and action is MenuAction.CONFIRM:
            logger.info("Returning to title screen.")
            self._return_to_title()
            return
        menu = self._active_menu()
        if menu is not None:
            menu.handle_action(action)

    def update(self, dt: float, result: BattleResult | None) -> None:
        """Advance the timed screens by ``dt``, or act on the Battle's result."""
        timed = self._timed_screens.get(self.screen)
        if timed is not None:
            duration, on_finished = timed
            self._screen_timer += dt
            if self._screen_timer >= duration:
                self._screen_timer = 0.0
                on_finished()
            return

        if result is BattleResult.VICTORY:
            self._sound.stop_loops()
            self._sound.play("victory")
            self.screen = Screen.VICTORY
        elif result is BattleResult.GAME_OVER:
            self._sound.stop_loops()
            self._sound.play("game_over")
            self.screen = Screen.GAME_OVER_ANIMATION

    def take_battle_request(self) -> BattleRequest | None:
        """The Battle to start now, if any; each request is handed out once."""
        request, self._battle_request = self._battle_request, None
        return request

    def quit(self) -> None:
        """Leave the game from whatever screen is showing."""
        logger.info("Exiting the game.")
        self._sound.stop_loops()
        self.screen = Screen.EXIT

    @property
    def menu(self) -> MenuView | None:
        """The active menu's labels and selection, or None on a screen without one."""
        menu = self._active_menu()
        if menu is None:
            return None
        return MenuView(menu.labels, menu.selection)

    @property
    def battle_steps(self) -> bool:
        """Whether the adapter steps the Battle this frame."""
        return self.screen is Screen.RUNNING

    @property
    def curtain_progress(self) -> float:
        """How far the curtain covers the screen, from 0 (open) to 1 (closed)."""
        if self.screen is Screen.STAGE_CURTAIN_CLOSE:
            return min(1.0, self._screen_timer / CURTAIN_CLOSE_DURATION)
        if self.screen is Screen.STAGE_CURTAIN_OPEN:
            return max(0.0, 1.0 - self._screen_timer / CURTAIN_OPEN_DURATION)
        return 0.0

    @property
    def curtain_stage(self) -> int | None:
        """The Stage number shown on the curtain; None on the wipe to the title."""
        if self._behind_curtain is not Screen.RUNNING:
            return None
        return self.stage

    @property
    def game_over_rise_progress(self) -> float | None:
        """How far the Game Over text has risen, or None outside the animation."""
        if self.screen is not Screen.GAME_OVER_ANIMATION:
            return None
        return min(1.0, self._screen_timer / GAME_OVER_RISE_DURATION)

    def _start_game(self, mode: GameMode) -> None:
        logger.info(f"{mode.value} selected, starting game.")
        self._mode = mode
        self.stage = 1
        self._start_stage(new_game=True)

    def _start_stage(self, new_game: bool) -> None:
        self._battle_request = BattleRequest(
            self.stage, self._mode, new_game, self._settings.difficulty
        )
        self.screen = Screen.STAGE_CURTAIN_CLOSE
        self._sound.play("stage_start")

    def _on_victory_pause_finished(self) -> None:
        if self.stage >= MAX_STAGE:
            self._sound.stop_loops()
            self.screen = Screen.GAME_COMPLETE
            return
        self.stage += 1
        self._start_stage(new_game=False)

    def _on_curtain_closed(self) -> None:
        self.screen = Screen.STAGE_CURTAIN_OPEN

    def _on_curtain_opened(self) -> None:
        self.screen = self._behind_curtain
        self._behind_curtain = Screen.RUNNING
        if self.screen is Screen.TITLE_SCREEN:
            self._title_menu.reset()

    def _on_game_over_animation_finished(self) -> None:
        logger.info("Wiping to title screen.")
        self._behind_curtain = Screen.TITLE_SCREEN
        self.screen = Screen.STAGE_CURTAIN_CLOSE

    def _toggle_pause(self) -> None:
        if self.screen is Screen.RUNNING:
            logger.info("Game paused.")
            self._sound.stop_loops()
            self._pause_menu.reset()
            self.screen = Screen.PAUSED
        elif self.screen is Screen.PAUSED:
            self._resume()
        elif self.screen is Screen.OPTIONS_MENU:
            self._leave_options()

    def _resume(self) -> None:
        logger.info("Game resumed.")
        self.screen = Screen.RUNNING

    def _open_options(self, from_pause: bool) -> None:
        self._options_from_pause = from_pause
        self._options_menu.reset()
        self.screen = Screen.OPTIONS_MENU

    def _leave_options(self) -> None:
        self._settings.save()
        self.screen = Screen.PAUSED if self._options_from_pause else Screen.TITLE_SCREEN

    def _cycle_difficulty(self, step: int) -> None:
        self._settings.cycle_difficulty(step)
        self._play_select()

    def _adjust_volume(self, delta: float) -> None:
        self._settings.adjust_volume(delta)
        self._sound.set_master_volume(self._settings.master_volume)
        self._play_select()

    def _return_to_title(self) -> None:
        self._sound.stop_loops()
        self._title_menu.reset()
        self.screen = Screen.TITLE_SCREEN

    def _active_menu(self) -> MenuController | None:
        if self.screen is Screen.TITLE_SCREEN:
            return self._title_menu
        if self.screen is Screen.PAUSED:
            return self._pause_menu
        if self.screen is Screen.OPTIONS_MENU:
            return self._options_menu
        return None

    def _play_select(self) -> None:
        self._sound.play("menu_select")
