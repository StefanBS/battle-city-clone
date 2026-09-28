from unittest.mock import MagicMock

import pytest

from src.managers.screen_flow import BattleRequest, ScreenFlow
from src.managers.settings_manager import SettingsManager
from src.managers.sound_manager import SoundManager
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
    VICTORY_PAUSE_DURATION,
    VOLUME_ADJUSTMENT_STEP,
    MenuAction,
)


@pytest.fixture
def settings(tmp_path):
    return SettingsManager(str(tmp_path / "settings.json"))


@pytest.fixture
def sound():
    return MagicMock(spec=SoundManager)


@pytest.fixture
def flow(settings, sound):
    return ScreenFlow(settings, sound)


def choose(flow, index):
    """Move the active menu's selection down to ``index`` and confirm it."""
    for _ in range(index):
        flow.handle(MenuAction.DOWN)
    flow.handle(MenuAction.CONFIRM)


def run_curtain(flow):
    """Run the curtain from closing to fully open."""
    flow.update(CURTAIN_CLOSE_DURATION + CURTAIN_STAGE_DISPLAY, None)
    flow.update(CURTAIN_OPEN_DURATION, None)


# The title menu's modes, top to bottom.
TITLE_MODES = (GameMode.ONE_PLAYER, GameMode.TWO_PLAYERS, GameMode.ONE_PLAYER_CPU)


def choose_mode(flow, mode):
    """Choose ``mode`` on the title screen."""
    choose(flow, TITLE_MODES.index(mode))


def start_game(flow, mode=GameMode.ONE_PLAYER):
    """Choose ``mode`` and run the curtain until the Battle steps."""
    choose_mode(flow, mode)
    run_curtain(flow)


def reach_next_stage(flow):
    """End the running Battle in Victory and run the Victory pause."""
    flow.update(1 / 60, BattleResult.VICTORY)
    flow.update(VICTORY_PAUSE_DURATION, None)


def complete_game(flow, mode=GameMode.ONE_PLAYER):
    """Reach Victory on every Stage, ending on Game Complete."""
    start_game(flow, mode)
    for _ in range(MAX_STAGE - 1):
        reach_next_stage(flow)
        run_curtain(flow)
    flow.take_battle_request()
    reach_next_stage(flow)


class TestTitleScreen:
    def test_starts_on_the_title_screen_with_the_title_menu(self, flow):
        assert flow.screen is Screen.TITLE_SCREEN
        assert flow.menu is not None
        assert flow.menu.labels == [
            "1 Player",
            "2 Players",
            "1 Player + CPU",
            "Options",
            "Quit",
        ]
        assert flow.menu.selection == 0
        assert flow.take_battle_request() is None

    def test_up_and_down_move_the_selection_and_play_menu_select(self, flow, sound):
        flow.handle(MenuAction.DOWN)
        flow.handle(MenuAction.DOWN)
        flow.handle(MenuAction.UP)

        assert flow.menu.selection == 1
        assert sound.play.call_count == 3
        sound.play.assert_called_with("menu_select")

    @pytest.mark.parametrize("mode", TITLE_MODES)
    def test_choosing_a_mode_requests_a_new_game_on_stage_1(self, flow, mode):
        choose_mode(flow, mode)

        assert flow.screen is Screen.STAGE_CURTAIN_CLOSE
        assert flow.stage == 1
        assert flow.take_battle_request() == BattleRequest(
            stage=1,
            mode=mode,
            new_game=True,
            difficulty=Difficulty.NORMAL,
        )
        assert flow.take_battle_request() is None

    def test_choosing_a_mode_plays_stage_start(self, flow, sound):
        choose_mode(flow, GameMode.ONE_PLAYER)

        sound.play.assert_called_with("stage_start")


class TestCurtain:
    def test_closes_shows_the_stage_then_opens_onto_the_battle(self, flow):
        choose_mode(flow, GameMode.ONE_PLAYER)
        assert flow.menu is None
        assert flow.battle_steps is False
        assert flow.curtain_progress == 0.0
        assert flow.curtain_stage == 1

        flow.update(CURTAIN_CLOSE_DURATION / 2, None)
        assert flow.curtain_progress == pytest.approx(0.5)

        flow.update(CURTAIN_CLOSE_DURATION / 2, None)
        assert flow.screen is Screen.STAGE_CURTAIN_CLOSE
        assert flow.curtain_progress == 1.0

        flow.update(CURTAIN_STAGE_DISPLAY, None)
        assert flow.screen is Screen.STAGE_CURTAIN_OPEN
        assert flow.curtain_progress == 1.0

        flow.update(CURTAIN_OPEN_DURATION / 2, None)
        assert flow.curtain_progress == pytest.approx(0.5)

        flow.update(CURTAIN_OPEN_DURATION / 2, None)
        assert flow.screen is Screen.RUNNING
        assert flow.battle_steps is True
        assert flow.curtain_progress == 0.0


class TestVictory:
    def test_victory_pauses_the_battle_and_plays_victory(self, flow, sound):
        start_game(flow)
        flow.take_battle_request()

        flow.update(1 / 60, BattleResult.VICTORY)

        assert flow.screen is Screen.VICTORY
        assert flow.battle_steps is False
        sound.stop_loops.assert_called()
        sound.play.assert_called_with("victory")
        assert flow.take_battle_request() is None

    def test_after_the_pause_the_next_stage_carries_progress(self, flow, sound):
        start_game(flow, GameMode.ONE_PLAYER_CPU)
        flow.take_battle_request()

        reach_next_stage(flow)

        assert flow.screen is Screen.STAGE_CURTAIN_CLOSE
        assert flow.stage == 2
        assert flow.curtain_stage == 2
        assert flow.take_battle_request() == BattleRequest(
            stage=2,
            mode=GameMode.ONE_PLAYER_CPU,
            new_game=False,
            difficulty=Difficulty.NORMAL,
        )
        sound.play.assert_called_with("stage_start")

    def test_victory_on_the_last_stage_is_game_complete(self, flow, sound):
        complete_game(flow)

        assert flow.screen is Screen.GAME_COMPLETE
        assert flow.stage == MAX_STAGE
        assert flow.take_battle_request() is None
        sound.stop_loops.assert_called()


class TestGameOver:
    def test_game_over_plays_the_rise_animation(self, flow, sound):
        start_game(flow)

        flow.update(1 / 60, BattleResult.GAME_OVER)

        assert flow.screen is Screen.GAME_OVER_ANIMATION
        assert flow.battle_steps is False
        sound.stop_loops.assert_called()
        sound.play.assert_called_with("game_over")
        assert flow.game_over_rise_progress == 0.0
        flow.update(GAME_OVER_RISE_DURATION / 2, None)
        assert flow.game_over_rise_progress == pytest.approx(0.5)
        flow.update(GAME_OVER_RISE_DURATION / 2, None)
        assert flow.game_over_rise_progress == 1.0

    def test_no_rise_progress_outside_the_animation(self, flow):
        assert flow.game_over_rise_progress is None
        start_game(flow)
        assert flow.game_over_rise_progress is None

    def test_after_the_hold_the_curtain_wipes_to_the_title_screen(self, flow):
        start_game(flow, GameMode.TWO_PLAYERS)
        flow.take_battle_request()
        flow.update(1 / 60, BattleResult.GAME_OVER)

        flow.update(GAME_OVER_RISE_DURATION + GAME_OVER_HOLD_DURATION, None)
        assert flow.screen is Screen.STAGE_CURTAIN_CLOSE
        assert flow.curtain_stage is None
        run_curtain(flow)

        assert flow.screen is Screen.TITLE_SCREEN
        assert flow.menu.selection == 0
        assert flow.take_battle_request() is None

    def test_a_new_game_after_game_over_shows_stage_1(self, flow):
        start_game(flow)
        reach_next_stage(flow)
        run_curtain(flow)
        flow.update(1 / 60, BattleResult.GAME_OVER)
        flow.update(GAME_OVER_RISE_DURATION + GAME_OVER_HOLD_DURATION, None)
        run_curtain(flow)

        choose_mode(flow, GameMode.TWO_PLAYERS)

        assert flow.curtain_stage == 1
        assert flow.take_battle_request() == BattleRequest(
            stage=1,
            mode=GameMode.TWO_PLAYERS,
            new_game=True,
            difficulty=Difficulty.NORMAL,
        )
        run_curtain(flow)
        assert flow.screen is Screen.RUNNING


class TestScreensWithoutAMenu:
    @pytest.mark.parametrize(
        "reach",
        [
            pytest.param(
                lambda flow: choose_mode(flow, GameMode.ONE_PLAYER), id="curtain"
            ),
            pytest.param(start_game, id="running"),
            pytest.param(
                lambda flow: (
                    start_game(flow),
                    flow.update(1 / 60, BattleResult.VICTORY),
                ),
                id="victory",
            ),
            pytest.param(
                lambda flow: (
                    start_game(flow),
                    flow.update(1 / 60, BattleResult.GAME_OVER),
                ),
                id="game-over-animation",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "action",
        [MenuAction.UP, MenuAction.DOWN, MenuAction.CONFIRM, MenuAction.BACK],
    )
    def test_menu_actions_do_nothing(self, flow, sound, reach, action):
        reach(flow)
        flow.take_battle_request()
        screen = flow.screen
        sound.reset_mock()

        flow.handle(action)

        assert flow.screen is screen
        assert flow.take_battle_request() is None
        sound.play.assert_not_called()


class TestPause:
    def test_pause_stops_the_battle_and_opens_the_pause_menu(self, flow, sound):
        start_game(flow)

        flow.handle(MenuAction.PAUSE)

        assert flow.screen is Screen.PAUSED
        assert flow.battle_steps is False
        sound.stop_loops.assert_called()
        assert flow.menu.labels == ["Resume", "Options", "Title Screen", "Quit"]
        assert flow.menu.selection == 0

    def test_the_pause_menu_opens_at_the_top_each_time(self, flow):
        start_game(flow)
        flow.handle(MenuAction.PAUSE)
        flow.handle(MenuAction.DOWN)
        flow.handle(MenuAction.PAUSE)

        flow.handle(MenuAction.PAUSE)

        assert flow.menu.selection == 0

    def test_time_does_not_pass_while_paused(self, flow):
        start_game(flow)
        flow.handle(MenuAction.PAUSE)

        flow.update(60.0, None)

        assert flow.screen is Screen.PAUSED

    @pytest.mark.parametrize(
        "resume",
        [
            pytest.param([MenuAction.PAUSE], id="pause-again"),
            pytest.param([MenuAction.BACK], id="back"),
            pytest.param([MenuAction.CONFIRM], id="resume-item"),
        ],
    )
    def test_resuming_steps_the_battle_again(self, flow, resume):
        start_game(flow)
        flow.handle(MenuAction.PAUSE)

        for action in resume:
            flow.handle(action)

        assert flow.screen is Screen.RUNNING
        assert flow.battle_steps is True

    def test_title_screen_item_returns_to_the_title(self, flow, sound):
        start_game(flow, GameMode.TWO_PLAYERS)
        flow.handle(MenuAction.PAUSE)
        sound.reset_mock()

        choose(flow, 2)

        assert flow.screen is Screen.TITLE_SCREEN
        assert flow.menu.selection == 0
        sound.stop_loops.assert_called()

    @pytest.mark.parametrize(
        "reach",
        [
            pytest.param(lambda flow: None, id="title"),
            pytest.param(
                lambda flow: choose_mode(flow, GameMode.ONE_PLAYER), id="curtain"
            ),
            pytest.param(
                lambda flow: (
                    start_game(flow),
                    flow.update(1 / 60, BattleResult.VICTORY),
                ),
                id="victory",
            ),
        ],
    )
    def test_pause_does_nothing_outside_a_running_battle(self, flow, reach):
        reach(flow)
        screen = flow.screen

        flow.handle(MenuAction.PAUSE)

        assert flow.screen is screen


def open_options_from_pause(flow):
    start_game(flow)
    flow.handle(MenuAction.PAUSE)
    choose(flow, 1)


class TestOptions:
    def test_title_options_opens_the_options_menu(self, flow):
        choose(flow, 3)

        assert flow.screen is Screen.OPTIONS_MENU
        assert flow.menu.labels == ["Difficulty", "Volume", "Back"]
        assert flow.menu.selection == 0

    @pytest.mark.parametrize(
        "leave",
        [
            pytest.param([MenuAction.BACK], id="back"),
            pytest.param([MenuAction.PAUSE], id="pause"),
            pytest.param(
                [MenuAction.DOWN, MenuAction.DOWN, MenuAction.CONFIRM], id="back-item"
            ),
        ],
    )
    def test_leaving_returns_to_the_title_screen(self, flow, leave):
        choose(flow, 3)

        for action in leave:
            flow.handle(action)

        assert flow.screen is Screen.TITLE_SCREEN

    def test_leaving_options_opened_from_pause_returns_to_pause(self, flow):
        open_options_from_pause(flow)
        assert flow.screen is Screen.OPTIONS_MENU
        assert flow.battle_steps is False

        flow.handle(MenuAction.BACK)

        assert flow.screen is Screen.PAUSED

    def test_options_open_at_the_top_each_time(self, flow):
        choose(flow, 3)
        flow.handle(MenuAction.DOWN)
        flow.handle(MenuAction.BACK)

        flow.handle(MenuAction.CONFIRM)

        assert flow.screen is Screen.OPTIONS_MENU
        assert flow.menu.selection == 0

    @pytest.mark.parametrize(
        "action, difficulty",
        [(MenuAction.RIGHT, Difficulty.EASY), (MenuAction.LEFT, Difficulty.EASY)],
    )
    def test_left_and_right_cycle_the_difficulty(
        self, flow, settings, sound, action, difficulty
    ):
        choose(flow, 3)
        sound.reset_mock()

        flow.handle(action)

        assert settings.difficulty is difficulty
        sound.play.assert_called_once_with("menu_select")

    def test_left_and_right_adjust_the_volume(self, flow, settings, sound):
        choose(flow, 3)
        flow.handle(MenuAction.DOWN)
        sound.reset_mock()

        flow.handle(MenuAction.LEFT)

        assert settings.master_volume == pytest.approx(1.0 - VOLUME_ADJUSTMENT_STEP)
        sound.set_master_volume.assert_called_once_with(settings.master_volume)
        sound.play.assert_called_once_with("menu_select")

    def test_leaving_saves_the_settings(self, flow, tmp_path):
        choose(flow, 3)
        flow.handle(MenuAction.RIGHT)

        flow.handle(MenuAction.BACK)

        saved = SettingsManager(str(tmp_path / "settings.json"))
        assert saved.difficulty is Difficulty.EASY

    def test_a_new_game_is_requested_at_the_chosen_difficulty(self, flow):
        choose(flow, 3)
        flow.handle(MenuAction.RIGHT)
        flow.handle(MenuAction.BACK)
        assert flow.menu.selection == 3

        for _ in range(3):
            flow.handle(MenuAction.UP)
        flow.handle(MenuAction.CONFIRM)

        assert flow.take_battle_request().difficulty is Difficulty.EASY

    def test_the_next_stage_is_requested_at_a_difficulty_changed_in_pause(self, flow):
        open_options_from_pause(flow)
        flow.handle(MenuAction.RIGHT)
        flow.handle(MenuAction.BACK)
        flow.handle(MenuAction.PAUSE)
        flow.take_battle_request()

        reach_next_stage(flow)

        assert flow.take_battle_request().difficulty is Difficulty.EASY


class TestGameComplete:
    def test_confirm_returns_to_the_title_screen(self, flow, sound):
        complete_game(flow, GameMode.TWO_PLAYERS)
        assert flow.menu is None

        flow.handle(MenuAction.CONFIRM)

        assert flow.screen is Screen.TITLE_SCREEN
        assert flow.menu.selection == 0

    @pytest.mark.parametrize(
        "action", [MenuAction.UP, MenuAction.BACK, MenuAction.PAUSE]
    )
    def test_other_actions_do_nothing(self, flow, action):
        complete_game(flow)

        flow.handle(action)

        assert flow.screen is Screen.GAME_COMPLETE


class TestQuit:
    @pytest.mark.parametrize(
        "reach",
        [
            pytest.param(lambda flow: None, id="title"),
            pytest.param(start_game, id="running"),
            pytest.param(lambda flow: choose(flow, 3), id="options"),
        ],
    )
    def test_quit_exits_from_any_screen(self, flow, sound, reach):
        reach(flow)

        flow.quit()

        assert flow.screen is Screen.EXIT
        assert flow.battle_steps is False
        sound.stop_loops.assert_called()

    def test_title_quit_item_exits(self, flow):
        choose(flow, 4)

        assert flow.screen is Screen.EXIT

    def test_pause_quit_item_exits(self, flow):
        start_game(flow)
        flow.handle(MenuAction.PAUSE)

        choose(flow, 3)

        assert flow.screen is Screen.EXIT
