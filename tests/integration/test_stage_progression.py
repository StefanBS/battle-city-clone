"""Integration tests for the screen flow between Battles: new game, stage
transitions with the curtain, game complete and the Game Over wipe."""

import pytest
from src.states.game_state import GameState
from src.utils.constants import (
    CURTAIN_CLOSE_DURATION,
    CURTAIN_OPEN_DURATION,
    CURTAIN_STAGE_DISPLAY,
    FPS,
    GAME_OVER_HOLD_DURATION,
    GAME_OVER_RISE_DURATION,
    MAX_STAGE,
    VICTORY_PAUSE_DURATION,
)
from tests.integration.conftest import first_player


def run_until(game, state, max_frames):
    """Update until `game` reaches `state`; return the states visited in order."""
    visited = [game.state]
    for _ in range(max_frames):
        game.update()
        if game.state != visited[-1]:
            visited.append(game.state)
        if game.state == state:
            break
    return visited


def frames(seconds):
    """Frames to cover `seconds`, with slack for float accumulation."""
    return int(seconds * FPS) + 2


class TestNewGameAndNextStage:
    def test_new_game_resets_stage_and_score(self, game_manager_fixture):
        game = game_manager_fixture
        game.current_stage = 3
        game.battle.player_manager.add_score(500)
        game._new_game()
        assert game.current_stage == 1
        assert game.battle.player_manager.score == 0

    def test_next_stage_keeps_score(self, game_manager_fixture):
        game = game_manager_fixture
        game.battle.player_manager.add_score(500)
        game._on_victory_finished()
        assert game.battle.player_manager.score == 500

    def test_next_stage_keeps_lives(self, game_manager_fixture):
        game = game_manager_fixture
        first_player(game).lives = 5
        game._on_victory_finished()
        assert first_player(game).lives == 5

    def test_next_stage_keeps_star_level(self, game_manager_fixture):
        game = game_manager_fixture
        first_player(game).apply_star()
        first_player(game).apply_star()
        game._on_victory_finished()
        assert first_player(game).star_level == 2


class TestStageTransition:
    def test_full_stage_transition_cycle(self, game_manager_fixture):
        """Clearing the Roster runs victory → curtain close → curtain open →
        running, and advances the stage exactly once."""
        game = game_manager_fixture
        assert game.current_stage == 1

        game.battle.enemy_manager.enemies = []
        game.battle.spawn_manager._pending_spawns = []
        game.battle.spawn_manager.total_enemy_spawns = (
            game.battle.spawn_manager.max_enemy_spawns
        )
        game.update()
        assert game.state == GameState.VICTORY

        total = (
            VICTORY_PAUSE_DURATION
            + CURTAIN_CLOSE_DURATION
            + CURTAIN_STAGE_DISPLAY
            + CURTAIN_OPEN_DURATION
        )
        visited = run_until(game, GameState.RUNNING, frames(total))

        assert visited == [
            GameState.VICTORY,
            GameState.STAGE_CURTAIN_CLOSE,
            GameState.STAGE_CURTAIN_OPEN,
            GameState.RUNNING,
        ]
        assert game.current_stage == 2

    def test_curtain_progress(self, game_manager_fixture):
        """Closing runs 0 → 1 and opening runs 1 → 0, clamped past the end."""
        game = game_manager_fixture
        game.state = GameState.STAGE_CURTAIN_CLOSE
        game._state_timer = 0.0
        assert game._curtain_progress == 0.0
        game._state_timer = CURTAIN_CLOSE_DURATION / 2
        assert game._curtain_progress == pytest.approx(0.5)
        game._state_timer = CURTAIN_CLOSE_DURATION * 2
        assert game._curtain_progress == 1.0

        game.state = GameState.STAGE_CURTAIN_OPEN
        game._state_timer = CURTAIN_OPEN_DURATION * 2
        assert game._curtain_progress == 0.0

    def test_game_complete_at_max_stage(self, game_manager_fixture):
        """Beating MAX_STAGE shows GAME_COMPLETE instead of another stage."""
        game = game_manager_fixture
        game.current_stage = MAX_STAGE
        game._set_game_state(GameState.VICTORY)
        run_until(game, GameState.GAME_COMPLETE, frames(VICTORY_PAUSE_DURATION))
        assert game.state == GameState.GAME_COMPLETE
        assert game.current_stage == MAX_STAGE
        game.render()


class TestGameOverWipe:
    def test_game_over_wipes_to_title(self, game_manager_fixture):
        """After the rise and hold, the curtain wipes to the title screen."""
        game = game_manager_fixture
        game._set_game_state(GameState.GAME_OVER)

        total = (
            GAME_OVER_RISE_DURATION
            + GAME_OVER_HOLD_DURATION
            + CURTAIN_CLOSE_DURATION
            + CURTAIN_STAGE_DISPLAY
            + CURTAIN_OPEN_DURATION
        )
        visited = run_until(game, GameState.TITLE_SCREEN, frames(total))

        assert visited == [
            GameState.GAME_OVER_ANIMATION,
            GameState.STAGE_CURTAIN_CLOSE,
            GameState.STAGE_CURTAIN_OPEN,
            GameState.TITLE_SCREEN,
        ]
        assert game._title_menu.selection == 0
        assert game._post_curtain_state == GameState.RUNNING
