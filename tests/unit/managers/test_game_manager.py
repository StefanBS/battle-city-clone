import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.states.game_state import GameState
from src.core.enemy_tank import EnemyTank
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

    def test_title_screen_enter_starts_game(
        self, game_manager_at_title, key_down_event
    ):
        """Test Enter on '1 PLAYER' begins the curtain-close transition."""
        gm = game_manager_at_title
        gm._title_menu.selection = 0
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.STAGE_CURTAIN_CLOSE

    def test_title_screen_enter_on_2_players_starts_game(
        self, game_manager_at_title, key_down_event
    ):
        """Test Enter on '2 PLAYERS' (index 1) starts the game in two-player mode."""
        gm = game_manager_at_title
        gm._title_menu.selection = 1
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.STAGE_CURTAIN_CLOSE
        assert gm._two_player_mode is True

    def test_victory_r_does_nothing(self, game_manager, key_down_event):
        """Test pressing R during VICTORY does nothing (auto-advances instead)."""
        game_manager.state = GameState.VICTORY
        game_manager._state_timer = 0.0
        pygame.event.post(key_down_event(pygame.K_r))
        game_manager.handle_events()
        assert game_manager.state == GameState.VICTORY

    def test_title_screen_r_confirms_selection(
        self, game_manager_at_title, key_down_event
    ):
        """Test that R key acts as CONFIRM on title screen."""
        game_manager_at_title._title_menu.selection = 0
        pygame.event.post(key_down_event(pygame.K_r))
        game_manager_at_title.handle_events()
        assert game_manager_at_title.state == GameState.STAGE_CURTAIN_CLOSE

    def test_handle_events_quit(self, game_manager):
        """Test handling quit event sets state to EXIT."""
        event = pygame.event.Event(pygame.QUIT)
        pygame.event.post(event)
        game_manager.handle_events()
        assert game_manager.state == GameState.EXIT

    def test_handle_events_escape_during_running_pauses(
        self, game_manager, key_down_event
    ):
        """Test ESC during RUNNING pauses the game."""
        game_manager.state = GameState.RUNNING
        game_manager.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.PAUSED
        game_manager.sound_manager.stop_loops.assert_called_once()

    def test_handle_events_restart_not_game_over(self, game_manager, key_down_event):
        """Test that restart key does nothing when game is running."""
        initial_state = game_manager.state
        pygame.event.post(key_down_event(pygame.K_r))
        game_manager.handle_events()
        assert game_manager.state == initial_state

    def test_restart_after_game_over_resets_lives(self, game_manager):
        """Test that restarting after game over restores default lives."""
        game_manager.state = GameState.GAME_OVER
        game_manager._reset_game()
        players = game_manager.player_manager.get_active_players()
        assert players[0].lives == 3

    # --- Game State Tests --- #

    def test_current_stage_initialized(self, game_manager):
        """Test that current_stage starts at 1."""
        assert game_manager.current_stage == 1

    def test_update_stops_when_not_running(self, game_manager):
        """Test that update method does nothing if state is not RUNNING."""
        game_manager.state = GameState.GAME_OVER
        game_manager.player_manager = MagicMock()
        # Use a real list for enemy_tanks for the update loop check
        mock_enemy = MagicMock(spec=EnemyTank)
        mock_enemy.tank_type = "basic"
        game_manager.spawn_manager.enemy_tanks = [mock_enemy]
        game_manager.spawn_manager = MagicMock()
        game_manager.collision_response_handler = MagicMock()

        game_manager.update()

        game_manager.player_manager.update.assert_not_called()
        mock_enemy.update.assert_not_called()
        game_manager.spawn_manager.update.assert_not_called()
        game_manager.collision_response_handler.process_collisions.assert_not_called()

    class TestMenuActionHandlers:
        """Tests for menu handlers accepting MenuAction."""

        def test_title_input_down(self, game_manager_at_title):
            """MenuAction.DOWN navigates title screen down."""
            gm = game_manager_at_title
            gm._title_menu.selection = 2
            gm._title_menu.handle_action(MenuAction.DOWN)
            assert gm._title_menu.selection == 3

        def test_title_input_confirm(self, game_manager_at_title):
            """MenuAction.CONFIRM starts the game."""
            gm = game_manager_at_title
            gm._title_menu.selection = 0
            gm._title_menu.handle_action(MenuAction.CONFIRM)
            assert gm.state == GameState.STAGE_CURTAIN_CLOSE

        def test_pause_input_down(self, game_manager):
            """MenuAction.DOWN navigates pause menu."""
            game_manager.state = GameState.PAUSED
            game_manager._pause_menu.selection = 0
            game_manager._pause_menu.handle_action(MenuAction.DOWN)
            assert game_manager._pause_menu.selection == 1

        def test_pause_input_confirm_resume(self, game_manager):
            """MenuAction.CONFIRM on Resume resumes game."""
            game_manager.state = GameState.PAUSED
            game_manager._pause_menu.selection = 0
            game_manager._pause_menu.handle_action(MenuAction.CONFIRM)
            assert game_manager.state == GameState.RUNNING

        def test_options_input_right_volume(self, game_manager):
            """MenuAction.RIGHT on volume row delegates to settings_manager."""
            game_manager.state = GameState.OPTIONS_MENU
            game_manager._options_menu.selection = 1  # volume is now index 1
            game_manager._options_menu.handle_action(MenuAction.RIGHT)
            game_manager.settings_manager.adjust_volume.assert_called_once_with(
                VOLUME_ADJUSTMENT_STEP
            )

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

        def test_options_input_confirm_back(self, game_manager):
            """MenuAction.CONFIRM on Back returns to previous screen."""
            game_manager.state = GameState.OPTIONS_MENU
            game_manager._options_menu.selection = 2  # back is now index 2
            game_manager._options_from_pause = False
            game_manager._options_menu.handle_action(MenuAction.CONFIRM)
            assert game_manager.state == GameState.TITLE_SCREEN

        def test_game_complete_confirm(self, game_manager):
            """MenuAction.CONFIRM in GAME_COMPLETE returns to title."""
            game_manager.state = GameState.GAME_COMPLETE
            game_manager.input_handler._menu_actions = [MenuAction.CONFIRM]
            game_manager._process_menu_actions()
            assert game_manager.state == GameState.TITLE_SCREEN

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
    def test_load_stage_uses_current_stage_for_map_name(self, game_manager):
        game_manager.current_stage = 5
        with patch("src.managers.game_manager.os.path.exists", return_value=True):
            with patch("src.managers.game_manager.Map") as MockMap:
                MockMap.return_value = game_manager.map
                game_manager._load_stage()
        call_args = MockMap.call_args[0][0]
        assert "level_05.tmx" in call_args

    def test_load_stage_falls_back_to_level_01_when_missing(self, game_manager):
        game_manager.current_stage = 99
        with patch("src.managers.game_manager.os.path.exists", return_value=False):
            with patch("src.managers.game_manager.Map") as MockMap:
                MockMap.return_value = game_manager.map
                game_manager._load_stage()
        call_args = MockMap.call_args[0][0]
        assert "level_01.tmx" in call_args

    def test_victory_transitions_to_game_complete_at_max_stage(self, game_manager):
        game_manager.state = GameState.VICTORY
        game_manager.current_stage = MAX_STAGE
        game_manager._state_timer = VICTORY_PAUSE_DURATION + 0.1
        game_manager.sound_manager = MagicMock()
        game_manager.update()
        assert game_manager.state == GameState.GAME_COMPLETE

    def test_victory_advances_stage_when_below_max(self, game_manager):
        game_manager.state = GameState.VICTORY
        game_manager.current_stage = 1
        game_manager._state_timer = VICTORY_PAUSE_DURATION + 0.1
        game_manager.sound_manager = MagicMock()
        original_stage = game_manager.current_stage
        game_manager.update()
        assert game_manager.current_stage == original_stage + 1

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

    def test_esc_during_paused_resumes(self, game_manager, key_down_event):
        """ESC during PAUSED transitions back to RUNNING."""
        game_manager.state = GameState.PAUSED
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.RUNNING

    def test_esc_during_title_screen_does_nothing(
        self, game_manager_at_title, key_down_event
    ):
        """ESC during TITLE_SCREEN does nothing."""
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager_at_title.handle_events()
        assert game_manager_at_title.state == GameState.TITLE_SCREEN

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

    def test_esc_during_game_over_does_nothing(self, game_manager, key_down_event):
        """ESC during GAME_OVER does nothing."""
        game_manager.state = GameState.GAME_OVER
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.GAME_OVER

    def test_esc_during_game_over_animation_does_nothing(
        self, game_manager, key_down_event
    ):
        """ESC during GAME_OVER_ANIMATION does nothing."""
        game_manager.state = GameState.GAME_OVER_ANIMATION
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.GAME_OVER_ANIMATION

    def test_esc_during_game_complete_does_nothing(self, game_manager, key_down_event):
        """ESC during GAME_COMPLETE does nothing."""
        game_manager.state = GameState.GAME_COMPLETE
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.GAME_COMPLETE

    def test_esc_during_victory_does_nothing(self, game_manager, key_down_event):
        """ESC during VICTORY does nothing."""
        game_manager.state = GameState.VICTORY
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.VICTORY

    # --- Title screen options and quit ---

    def test_title_options_transitions_to_options_menu(
        self, game_manager_at_title, key_down_event
    ):
        """Enter on OPTIONS (index 2) on title screen goes to OPTIONS_MENU."""
        gm = game_manager_at_title
        gm._title_menu.selection = 2
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.OPTIONS_MENU
        assert gm._options_from_pause is False
        assert gm._options_menu.selection == 0

    def test_title_quit_exits(self, game_manager_at_title, key_down_event):
        """Enter on QUIT (index 3) on title screen exits the game."""
        gm = game_manager_at_title
        gm._title_menu.selection = 3
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.EXIT

    # --- Pause menu navigation ---

    def test_pause_resume(self, game_manager, key_down_event):
        """Enter on RESUME (0) in pause menu returns to RUNNING."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 0
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.RUNNING

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

    def test_resume_clears_pending_shoot(self, game_manager):
        """Resuming from pause clears buffered shoot input on all players.

        Regression: pressing controller A to select Resume used to also fire a
        bullet on the first RUNNING frame because the press was captured as
        both a menu CONFIRM and a shoot.
        """
        gm = game_manager
        gm.state = GameState.PAUSED
        gm._pause_menu.selection = 0
        gm._pause_menu.handle_action(MenuAction.CONFIRM)
        assert gm.state == GameState.RUNNING
        gm.player_manager.clear_pending_shoot.assert_called_once()

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

    def test_options_volume_left_decreases(self, game_manager, key_down_event):
        """LEFT on VOLUME (1) delegates to settings_manager.adjust_volume."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_menu.selection = 1
        gm.settings_manager = MagicMock()
        gm.settings_manager.master_volume = 0.4  # value adjust_volume would land on
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_LEFT))
        gm.handle_events()
        gm.settings_manager.adjust_volume.assert_called_once_with(
            -VOLUME_ADJUSTMENT_STEP
        )
        gm.sound_manager.set_master_volume.assert_called_once_with(0.4)

    def test_options_volume_right_increases(self, game_manager, key_down_event):
        """RIGHT on VOLUME (1) delegates to settings_manager.adjust_volume."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_menu.selection = 1
        gm.settings_manager = MagicMock()
        gm.settings_manager.master_volume = 0.6  # value adjust_volume would land on
        gm.sound_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RIGHT))
        gm.handle_events()
        gm.settings_manager.adjust_volume.assert_called_once_with(
            VOLUME_ADJUSTMENT_STEP
        )
        gm.sound_manager.set_master_volume.assert_called_once_with(0.6)

    def test_options_back_saves_and_returns_to_title(
        self, game_manager, key_down_event
    ):
        """Enter on BACK (2) in options saves and returns to origin."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_menu.selection = 2
        gm._options_from_pause = False
        gm.settings_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.TITLE_SCREEN
        gm.settings_manager.save.assert_called_once()

    def test_options_back_saves_and_returns_to_pause(
        self, game_manager, key_down_event
    ):
        """Enter on BACK (2) in options from pause saves and returns to PAUSED."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm._options_menu.selection = 2
        gm._options_from_pause = True
        gm.settings_manager = MagicMock()
        pygame.event.post(key_down_event(pygame.K_RETURN))
        gm.handle_events()
        assert gm.state == GameState.PAUSED
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

    # --- Update early return for PAUSED/OPTIONS_MENU ---

    def test_update_does_nothing_when_paused(self, game_manager):
        """Update does not process game logic when PAUSED."""
        gm = game_manager
        gm.state = GameState.PAUSED
        gm.player_manager = MagicMock()
        gm.update()
        gm.player_manager.update.assert_not_called()

    def test_update_does_nothing_when_in_options(self, game_manager):
        """Update does not process game logic when in OPTIONS_MENU."""
        gm = game_manager
        gm.state = GameState.OPTIONS_MENU
        gm.player_manager = MagicMock()
        gm.update()
        gm.player_manager.update.assert_not_called()

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
