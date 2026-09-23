import pytest
import pygame
from unittest.mock import MagicMock, patch
from src.states.game_state import GameState
from src.states.game_mode import GameMode
from src.utils.constants import (
    Difficulty,
    MAX_STAGE,
    MenuAction,
    VICTORY_PAUSE_DURATION,
    VOLUME_ADJUSTMENT_STEP,
)


class TestGameManager:
    """Unit test cases for the GameManager class."""

    def test_initialization_starts_at_title_screen(self, game_manager_at_title):
        """Test that GameManager starts at the title screen."""
        assert game_manager_at_title.state == GameState.TITLE_SCREEN
        assert game_manager_at_title._title_menu.selection == 0

    def test_title_screen_cursor_moves(self, game_manager_at_title, key_down_event):
        """Test up/down keys cycle through selectable items (0, 1, 2, 3, 4)."""
        gm = game_manager_at_title
        assert gm._title_menu.selection == 0
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._title_menu.selection == 1
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._title_menu.selection == 2
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._title_menu.selection == 3
        pygame.event.post(key_down_event(pygame.K_UP))
        gm.handle_events()
        assert gm._title_menu.selection == 2

    @pytest.mark.parametrize(
        "selection, mode",
        [
            (0, GameMode.ONE_PLAYER),
            (1, GameMode.TWO_PLAYERS),
            (2, GameMode.ONE_PLAYER_CPU),
        ],
    )
    def test_title_screen_enter_starts_game(
        self, game_manager_at_title, key_down_event, selection, mode
    ):
        """Enter on a mode entry starts that mode with the curtain-close transition."""
        gm = game_manager_at_title
        gm._title_menu.selection = selection
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.STAGE_CURTAIN_CLOSE
        assert gm._game_mode is mode

    def test_title_menu_lists_cpu_mode_between_2_players_and_options(
        self, game_manager_at_title
    ):
        assert game_manager_at_title._title_menu.labels == [
            "1 Player",
            "2 Players",
            "1 Player + CPU",
            "Options",
            "Quit",
        ]

    def test_handle_events_quit(self, game_manager):
        """Test handling quit event sets state to EXIT."""
        event = pygame.event.Event(pygame.QUIT)
        pygame.event.post(event)
        game_manager.handle_events()
        assert game_manager.state == GameState.EXIT

    def test_restart_after_game_over_starts_a_fresh_battle(
        self, game_manager, _mock_game_deps
    ):
        """Restarting after game over builds a Battle with no carried progress."""
        game_manager.state = GameState.GAME_OVER
        _mock_game_deps.reset_mock()
        game_manager._reset_game()
        assert _mock_game_deps.call_args.kwargs["carried"] == {}

    @pytest.mark.parametrize(
        "state",
        [GameState.RUNNING, GameState.VICTORY, GameState.GAME_OVER_ANIMATION],
    )
    def test_r_does_nothing(self, game_manager, key_down_event, state):
        """R only confirms menus; it neither restarts nor skips an animation."""
        game_manager.state = state
        pygame.event.post(key_down_event(pygame.K_r))
        game_manager.handle_events()
        assert game_manager.state == state

    # --- Game State Tests --- #

    @pytest.mark.parametrize(
        "state",
        [
            GameState.GAME_OVER,
            GameState.PAUSED,
            GameState.OPTIONS_MENU,
            GameState.GAME_OVER_ANIMATION,
        ],
    )
    def test_battle_is_not_stepped_unless_running(self, game_manager, state):
        game_manager.state = state
        game_manager.update()
        game_manager.battle.step.assert_not_called()

    def test_events_are_passed_to_the_battle(self, game_manager, key_down_event):
        event = key_down_event(pygame.K_UP)
        with patch("pygame.event.get", return_value=[event]):
            game_manager.handle_events()
        game_manager.battle.handle_event.assert_called_once_with(event)

    class TestMenuActionHandlers:
        """Tests for menu handlers accepting MenuAction."""

        def test_options_difficulty_cycles_forward(self, game_manager):
            """MenuAction.RIGHT on difficulty row delegates with step=+1."""
            game_manager.state = GameState.OPTIONS_MENU
            game_manager._options_menu.selection = 0
            game_manager._options_menu.handle_action(MenuAction.RIGHT)
            game_manager.settings_manager.cycle_difficulty.assert_called_once_with(1)

        def test_options_difficulty_cycles_backward(self, game_manager):
            """MenuAction.LEFT on difficulty row delegates with step=-1."""
            game_manager.state = GameState.OPTIONS_MENU
            game_manager._options_menu.selection = 0
            game_manager._options_menu.handle_action(MenuAction.LEFT)
            game_manager.settings_manager.cycle_difficulty.assert_called_once_with(-1)

        def test_start_button_triggers_escape(self, game_manager):
            """Controller Start button triggers _handle_escape."""
            game_manager.state = GameState.RUNNING
            event = pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_START,
            )
            pygame.event.post(event)
            game_manager.handle_events()
            assert game_manager.state == GameState.PAUSED


class TestGameManagerSoundWiring:
    @pytest.fixture
    def gm_with_mock_sound(self, game_manager):
        """GameManager with SoundManager replaced by a mock."""
        game_manager.sound_manager = MagicMock()
        return game_manager

    def test_set_game_state_victory_stops_loops_and_plays_victory(
        self, gm_with_mock_sound
    ):
        gm = gm_with_mock_sound
        gm._set_game_state(GameState.VICTORY)
        gm.sound_manager.stop_loops.assert_called_once()
        gm.sound_manager.play.assert_called_once_with("victory")
        assert gm.state == GameState.VICTORY

    def test_set_game_state_game_over_stops_loops(self, gm_with_mock_sound):
        gm = gm_with_mock_sound
        gm._set_game_state(GameState.GAME_OVER)
        gm.sound_manager.stop_loops.assert_called_once()
        gm.sound_manager.play.assert_called_once_with("game_over")
        assert gm.state == GameState.GAME_OVER_ANIMATION

    def test_quit_game_stops_loops(self, gm_with_mock_sound):
        gm = gm_with_mock_sound
        gm._quit_game()
        gm.sound_manager.stop_loops.assert_called_once()
        assert gm.state == GameState.EXIT

    def test_handle_title_input_plays_menu_select(self, game_manager_at_title):
        gm = game_manager_at_title
        gm.sound_manager = MagicMock()
        gm._title_menu.handle_action(MenuAction.DOWN)
        gm.sound_manager.play.assert_any_call("menu_select")


class TestStageProgression:
    def test_stage_map_uses_current_stage_for_map_name(self, game_manager):
        game_manager.current_stage = 5
        with patch("src.managers.game_manager.os.path.exists", return_value=True):
            with patch("src.managers.game_manager.Map") as MockMap:
                game_manager._load_stage_map()
        call_args = MockMap.call_args[0][0]
        assert "level_05.tmx" in call_args

    def test_stage_map_falls_back_to_level_01_when_missing(self, game_manager):
        game_manager.current_stage = 99
        with patch("src.managers.game_manager.os.path.exists", return_value=False):
            with patch("src.managers.game_manager.Map") as MockMap:
                game_manager._load_stage_map()
        call_args = MockMap.call_args[0][0]
        assert "level_01.tmx" in call_args

    def test_victory_transitions_to_game_complete_at_max_stage(self, game_manager):
        game_manager.state = GameState.VICTORY
        game_manager.current_stage = MAX_STAGE
        game_manager._state_timer = VICTORY_PAUSE_DURATION + 0.1
        game_manager.sound_manager = MagicMock()
        game_manager.update()
        assert game_manager.state == GameState.GAME_COMPLETE

    def test_set_game_state_game_complete_stops_loops(self, game_manager):
        game_manager.sound_manager = MagicMock()
        game_manager._set_game_state(GameState.GAME_COMPLETE)
        game_manager.sound_manager.stop_loops.assert_called_once()
        assert game_manager.state == GameState.GAME_COMPLETE

    def test_key_r_returns_to_title_from_game_complete(self, game_manager):
        game_manager.state = GameState.GAME_COMPLETE
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        with patch("pygame.event.get", return_value=[event]):
            game_manager.handle_events()
        assert game_manager.state == GameState.TITLE_SCREEN
        assert game_manager._title_menu.selection == 0


class TestPauseAndOptionsStateMachine:
    """Tests for PAUSED and OPTIONS_MENU state transitions."""

    # --- ESC state transitions ---

    def test_esc_during_running_pauses(self, game_manager, key_down_event):
        """ESC during RUNNING transitions to PAUSED."""
        game_manager.state = GameState.RUNNING
        game_manager.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.PAUSED
        assert game_manager._pause_menu.selection == 0
        game_manager.sound_manager.stop_loops.assert_called_once()

    @pytest.mark.parametrize(
        "state",
        [
            GameState.TITLE_SCREEN,
            GameState.GAME_OVER,
            GameState.GAME_OVER_ANIMATION,
            GameState.GAME_COMPLETE,
            GameState.VICTORY,
            GameState.STAGE_CURTAIN_CLOSE,
        ],
    )
    def test_esc_does_nothing(self, game_manager, key_down_event, state):
        """ESC only acts in RUNNING, PAUSED and OPTIONS_MENU."""
        game_manager.state = state
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == state

    def test_esc_during_paused_resumes(self, game_manager, key_down_event):
        """ESC during PAUSED transitions back to RUNNING."""
        game_manager.state = GameState.PAUSED
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.RUNNING

    def test_esc_during_options_from_title_returns_to_title(
        self, game_manager_at_title, key_down_event
    ):
        """ESC during OPTIONS_MENU (from title) saves and returns to TITLE_SCREEN."""
        gm = game_manager_at_title
        gm.state = GameState.OPTIONS_MENU
        gm._options_from_pause = False
        gm.settings_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        gm.handle_events()
        assert gm.state == GameState.TITLE_SCREEN
        gm.settings_manager.save.assert_called_once()

    def test_esc_during_options_from_pause_returns_to_paused(
        self, game_manager, key_down_event
    ):
        """ESC during OPTIONS_MENU (from pause) saves and returns to PAUSED."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_from_pause = True
        gm.settings_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        gm.handle_events()
        assert gm.state == GameState.PAUSED
        gm.settings_manager.save.assert_called_once()

    # --- Title screen options and quit ---

    def test_title_options_transitions_to_options_menu(
        self, game_manager_at_title, key_down_event
    ):
        """Enter on OPTIONS (index 3) on title screen goes to OPTIONS_MENU."""
        gm = game_manager_at_title
        gm._title_menu.selection = 3
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.OPTIONS_MENU
        assert gm._options_from_pause is False
        assert gm._options_menu.selection == 0

    def test_title_quit_exits(self, game_manager_at_title, key_down_event):
        """Enter on QUIT (index 4) on title screen exits the game."""
        gm = game_manager_at_title
        gm._title_menu.selection = 4
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.EXIT

    # --- Pause menu navigation ---

    def test_pause_options(self, game_manager, key_down_event):
        """Enter on OPTIONS (1) in pause menu goes to OPTIONS_MENU."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 1
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.OPTIONS_MENU
        assert gm._options_from_pause is True
        assert gm._options_menu.selection == 0

    def test_pause_title_screen(self, game_manager, key_down_event):
        """Enter on TITLE SCREEN (2) in pause menu returns to title."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 2
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.TITLE_SCREEN
        assert gm._title_menu.selection == 0
        gm.sound_manager.stop_loops.assert_called_once()

    def test_pause_quit(self, game_manager, key_down_event):
        """Enter on QUIT (3) in pause menu exits the game."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 3
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.EXIT

    def test_pause_back_resumes(self, game_manager):
        """BACK action in pause menu resumes the game regardless of selection."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 2  # not on RESUME
        gm._pause_menu.handle_action(MenuAction.BACK)
        assert gm.state == GameState.RUNNING

    def test_options_back_exits(self, game_manager):
        """BACK action in options menu exits options (like ESC)."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_from_pause = True
        gm._options_menu.handle_action(MenuAction.BACK)
        assert gm.state == GameState.PAUSED

    def test_options_back_from_title_returns_to_title(self, game_manager):
        """BACK in options opened from title returns to the title screen."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_from_pause = False
        gm._options_menu.handle_action(MenuAction.BACK)
        assert gm.state == GameState.TITLE_SCREEN

    def test_held_direction_before_pause_does_not_move_selector(
        self, game_manager, key_down_event
    ):
        """A KEYDOWN queued while RUNNING must not jump the pause selector.

        Regression: previously, an UP KEYDOWN fired before pressing ESC would
        queue MenuAction.UP in InputHandler; on transition to PAUSED the stale
        action was consumed and moved the selector from 0 (Resume) to 3 (Quit).
        """
        gm = game_manager
        gm.state = GameState.RUNNING
        gm.sound_manager = MagicMock()
        # Both events land in the same handle_events batch: UP queues a menu
        # action, ESC pauses and should drain it before _process_menu_actions.
        pygame.event.post(key_down_event(pygame.K_UP))
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        gm.handle_events()
        assert gm.state == GameState.PAUSED
        assert gm._pause_menu.selection == 0

    def test_resume_clears_pending_shoot(self, game_manager, key_down_event):
        """Enter on RESUME (0) returns to RUNNING and clears buffered shoot input.

        Regression: pressing controller A to select Resume used to also fire a
        bullet on the first RUNNING frame because the press was captured as
        both a menu CONFIRM and a shoot.
        """
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 0
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.RUNNING
        gm.battle.clear_pending_shoot.assert_called_once()

    def test_pause_navigation_up_down(self, game_manager, key_down_event):
        """UP/DOWN navigation wraps through 4 pause items."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 0
        gm.sound_manager = MagicMock()
        # Down from 0 -> 1
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._pause_menu.selection == 1
        # Down from 1 -> 2
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._pause_menu.selection == 2
        # Down from 2 -> 3
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._pause_menu.selection == 3
        # Down from 3 -> 0 (wrap)
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._pause_menu.selection == 0
        # Up from 0 -> 3 (wrap)
        pygame.event.post(key_down_event(pygame.K_UP))
        gm.handle_events()
        assert gm._pause_menu.selection == 3

    def test_pause_plays_menu_select_on_navigation(self, game_manager, key_down_event):
        """Navigating pause menu plays menu_select sound."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 0
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        gm.sound_manager.play.assert_any_call("menu_select")

    # --- Options menu ---

    @pytest.mark.parametrize(
        "key, delta, new_volume",
        [
            (pygame.K_LEFT, -VOLUME_ADJUSTMENT_STEP, 0.4),
            (pygame.K_RIGHT, VOLUME_ADJUSTMENT_STEP, 0.6),
        ],
    )
    def test_options_volume_adjusts(
        self, game_manager, key_down_event, key, delta, new_volume
    ):
        """LEFT/RIGHT on VOLUME (1) adjusts the setting and applies it to sound."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_menu.selection = 1
        gm.settings_manager = MagicMock()
        gm.settings_manager.master_volume = new_volume  # what adjust_volume lands on
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(key))
        gm.handle_events()
        gm.settings_manager.adjust_volume.assert_called_once_with(delta)
        gm.sound_manager.set_master_volume.assert_called_once_with(new_volume)

    @pytest.mark.parametrize(
        "from_pause, expected",
        [(False, GameState.TITLE_SCREEN), (True, GameState.PAUSED)],
    )
    def test_options_back_saves_and_returns(
        self, game_manager, key_down_event, from_pause, expected
    ):
        """Enter on BACK (2) in options saves and returns to the opening screen."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_menu.selection = 2
        gm._options_from_pause = from_pause
        gm.settings_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == expected
        gm.settings_manager.save.assert_called_once()

    def test_options_navigation_up_down(self, game_manager, key_down_event):
        """UP/DOWN navigation wraps between 3 options items."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_menu.selection = 0
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._options_menu.selection == 1
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._options_menu.selection == 2
        pygame.event.post(key_down_event(pygame.K_DOWN))
        gm.handle_events()
        assert gm._options_menu.selection == 0

    # --- Render routing ---

    def test_render_paused_calls_render_pause_menu(self, game_manager):
        """PAUSED state renders pause menu overlay."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm.renderer = MagicMock()
        gm.render()
        gm.renderer.render_pause_menu.assert_called_once_with(
            gm._pause_menu.labels, gm._pause_menu.selection
        )

    def test_render_options_calls_render_options_menu(self, game_manager):
        """OPTIONS_MENU state renders options menu."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm.renderer = MagicMock()
        gm.settings_manager = MagicMock()
        gm.settings_manager.master_volume = 0.7
        gm.settings_manager.difficulty = Difficulty.NORMAL
        gm.render()
        gm.renderer.render_options_menu.assert_called_once_with(
            0.7, Difficulty.NORMAL, gm._options_menu.selection
        )

    def test_render_title_uses_title_selection(self, game_manager_at_title):
        """TITLE_SCREEN renders with _title_selection."""
        gm = game_manager_at_title
        gm.renderer = MagicMock()
        gm._title_menu.selection = 2
        gm.render()
        gm.renderer.render_title_screen.assert_called_once_with(
            gm._title_menu.labels, 2
        )
