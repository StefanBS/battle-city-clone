"""Integration tests for stage transition curtain."""

import pytest
from src.states.game_state import GameState


class TestStageTransition:
    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    def test_full_stage_transition_cycle(self, game):
        """Complete cycle: running → victory → curtain → running (stage 2)."""
        assert game.state == GameState.RUNNING
        assert game.current_stage == 1

        # Force victory
        game.spawn_manager.enemy_tanks = []
        game.spawn_manager._pending_spawns = []
        game.spawn_manager.total_enemy_spawns = game.spawn_manager.max_enemy_spawns
        game.update()
        assert game.state == GameState.VICTORY

        # Tick through entire transition
        for _ in range(600):
            game.update()
            if game.state == GameState.RUNNING:
                break

        assert game.state == GameState.RUNNING
        assert game.current_stage == 2
