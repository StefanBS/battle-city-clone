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

        game.spawn_manager.enemy_tanks = []
        game.spawn_manager._pending_spawns = []
        game.spawn_manager.total_enemy_spawns = game.spawn_manager.max_enemy_spawns
        game.update()
        assert game.state == GameState.VICTORY

        # Transition ~4s: VICTORY_PAUSE (1.0) + CURTAIN_CLOSE (0.75) +
        # CURTAIN_STAGE_DISPLAY (1.5) + CURTAIN_OPEN (0.75); 300 frames is comfortable.
        for _ in range(300):
            game.update()
            if game.state == GameState.RUNNING:
                break

        assert game.state == GameState.RUNNING
        assert game.current_stage == 2
