import pytest
import pygame
from src.managers.game_manager import GameManager
from src.states.game_state import GameState
from src.utils.constants import (
    CURTAIN_CLOSE_DURATION,
    CURTAIN_OPEN_DURATION,
    CURTAIN_STAGE_DISPLAY,
    VICTORY_PAUSE_DURATION,
    GAME_OVER_RISE_DURATION,
    GAME_OVER_HOLD_DURATION,
)


class TestNewGameAndLoadStage:
    @pytest.fixture
    def game(self):
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
        gm = GameManager()
        gm._new_game()
        return gm

    def test_new_game_resets_stage_and_score(self, game):
        assert game.current_stage == 1
        assert game.score == 0

    def test_load_stage_preserves_score(self, game):
        game.score = 500
        game._load_stage()
        assert game.score == 500

    def test_load_stage_preserves_lives(self, game):
        game.player_tank.lives = 5
        game._load_stage()
        assert game.player_tank.lives == 5

    def test_load_stage_preserves_star_level(self, game):
        game.player_tank.apply_star()
        game.player_tank.apply_star()
        game._load_stage()
        assert game.player_tank.star_level == 2


class TestCurtainTransitions:
    @pytest.fixture
    def game(self):
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
        gm = GameManager()
        gm._new_game()
        gm.state = GameState.RUNNING
        return gm

    def test_victory_auto_transitions_to_curtain(self, game):
        game.state = GameState.VICTORY
        game._state_timer = 0.0
        for _ in range(int(VICTORY_PAUSE_DURATION * game.fps) + 1):
            game.update()
        assert game.state == GameState.STAGE_CURTAIN_CLOSE

    def test_curtain_close_shows_stage_then_opens(self, game):
        game.state = GameState.STAGE_CURTAIN_CLOSE
        game._state_timer = 0.0
        total = CURTAIN_CLOSE_DURATION + CURTAIN_STAGE_DISPLAY
        for _ in range(int(total * game.fps) + 1):
            game.update()
        assert game.state == GameState.STAGE_CURTAIN_OPEN

    def test_curtain_open_transitions_to_running(self, game):
        game.state = GameState.STAGE_CURTAIN_OPEN
        game._state_timer = 0.0
        for _ in range(int(CURTAIN_OPEN_DURATION * game.fps) + 1):
            game.update()
        assert game.state == GameState.RUNNING

    def test_curtain_progress_clamps(self, game):
        game.state = GameState.STAGE_CURTAIN_CLOSE
        game._state_timer = CURTAIN_CLOSE_DURATION * 2
        assert game._curtain_progress == 1.0
        game.state = GameState.STAGE_CURTAIN_OPEN
        game._state_timer = CURTAIN_OPEN_DURATION * 2
        assert game._curtain_progress == 0.0

    def test_no_double_stage_increment(self, game):
        game.state = GameState.VICTORY
        game._state_timer = 0.0
        initial_stage = game.current_stage
        for _ in range(300):
            game.update()
            if game.state == GameState.RUNNING:
                break
        assert game.current_stage == initial_stage + 1

    def test_load_stage_increments_stage(self, game):
        game.state = GameState.VICTORY
        game._state_timer = 0.0
        for _ in range(300):
            game.update()
            if game.state == GameState.RUNNING:
                break
        assert game.current_stage == 2

    def test_r_key_does_nothing_during_victory(self, game):
        game.state = GameState.VICTORY
        game._state_timer = 0.0
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        pygame.event.post(event)
        game.handle_events()
        assert game.state == GameState.VICTORY

    def test_escape_does_nothing_during_curtain(self, game):
        game.state = GameState.STAGE_CURTAIN_CLOSE
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        pygame.event.post(event)
        game.handle_events()
        assert game.state == GameState.STAGE_CURTAIN_CLOSE

    def test_title_start_triggers_curtain(self, game):
        game.state = GameState.TITLE_SCREEN
        game._title_selection = 0
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        pygame.event.post(event)
        game.handle_events()
        assert game.state == GameState.STAGE_CURTAIN_CLOSE

    def test_curtain_close_progresses(self, game):
        game.state = GameState.STAGE_CURTAIN_CLOSE
        game._state_timer = 0.0
        assert game._curtain_progress == 0.0
        game._state_timer = CURTAIN_CLOSE_DURATION / 2
        assert 0.4 < game._curtain_progress < 0.6
        game._state_timer = CURTAIN_CLOSE_DURATION
        assert game._curtain_progress == 1.0


class TestGameOverAnimation:
    @pytest.fixture
    def game(self):
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
        gm = GameManager()
        gm._new_game()
        gm.state = GameState.RUNNING
        return gm

    def test_game_over_triggers_animation(self, game):
        """Setting GAME_OVER via _set_game_state should enter animation."""
        game._set_game_state(GameState.GAME_OVER)
        assert game.state == GameState.GAME_OVER_ANIMATION

    def test_animation_transitions_to_game_over(self, game):
        """After rise + hold duration, state becomes GAME_OVER."""
        game.state = GameState.GAME_OVER_ANIMATION
        game._state_timer = 0.0
        total = GAME_OVER_RISE_DURATION + GAME_OVER_HOLD_DURATION
        for _ in range(int(total * game.fps) + 1):
            game.update()
        assert game.state == GameState.GAME_OVER

    def test_animation_freezes_gameplay(self, game):
        """During animation, game subsystems should not update."""
        game.state = GameState.GAME_OVER_ANIMATION
        game._state_timer = 0.0
        initial_pos = (game.player_tank.x, game.player_tank.y)
        game.update()
        assert (game.player_tank.x, game.player_tank.y) == initial_pos

    def test_r_key_does_nothing_during_animation(self, game):
        """R key should not work during the rising text animation."""
        game.state = GameState.GAME_OVER_ANIMATION
        game._state_timer = 0.0
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        pygame.event.post(event)
        game.handle_events()
        assert game.state == GameState.GAME_OVER_ANIMATION
