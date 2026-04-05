"""Integration tests for stage progression with real game objects."""

from src.states.game_state import GameState
from src.utils.constants import MAX_STAGE


class TestStageProgressionIntegration:
    def test_victory_increments_stage(self, game_manager_fixture):
        """Winning a stage increments current_stage."""
        gm = game_manager_fixture
        assert gm.current_stage == 1
        gm._set_game_state(GameState.VICTORY)
        assert gm.state == GameState.VICTORY
        # Advance past victory pause
        while gm.state == GameState.VICTORY:
            gm.update()
        assert gm.current_stage == 2

    def test_game_complete_at_max_stage(self, game_manager_fixture):
        """Beating MAX_STAGE transitions to GAME_COMPLETE."""
        gm = game_manager_fixture
        gm.current_stage = MAX_STAGE
        gm._set_game_state(GameState.VICTORY)
        while gm.state == GameState.VICTORY:
            gm.update()
        assert gm.state == GameState.GAME_COMPLETE
        assert gm.current_stage == MAX_STAGE  # not incremented

    def test_game_complete_render_does_not_raise(self, game_manager_fixture):
        """Verify render() works in GAME_COMPLETE state."""
        gm = game_manager_fixture
        gm.current_stage = MAX_STAGE
        gm._set_game_state(GameState.VICTORY)
        while gm.state == GameState.VICTORY:
            gm.update()
        assert gm.state == GameState.GAME_COMPLETE
        gm.render()  # should not raise
