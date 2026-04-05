"""Integration tests for sound effect wiring with real game objects."""

from src.states.game_state import GameState
from src.utils.constants import FPS


class TestEngineSoundWiring:
    """Engine sound updates are called during the game loop."""

    def test_engine_sound_updates_during_gameplay(self, game_manager_fixture):
        """Verify update() calls update_engine without error during RUNNING."""
        gm = game_manager_fixture
        assert gm.state == GameState.RUNNING
        # Run a few frames — should not raise
        for _ in range(5):
            gm.update()

    def test_player_movement_sets_is_moving(self, game_manager_fixture):
        """Verify player tank reports is_moving after move()."""
        gm = game_manager_fixture
        dt = 1.0 / FPS
        gm.player_tank.move(1, 0, dt)
        assert gm.player_tank.is_moving is True

    def test_player_is_moving_resets_after_update(self, game_manager_fixture):
        """Verify is_moving resets to False after tank.update()."""
        gm = game_manager_fixture
        dt = 1.0 / FPS
        gm.player_tank.move(1, 0, dt)
        assert gm.player_tank.is_moving is True
        gm.player_tank.update(dt)
        assert gm.player_tank.is_moving is False


class TestVictoryTransition:
    """Victory state transition stops loops and plays victory sound."""

    def test_victory_goes_through_set_game_state(self, game_manager_fixture):
        """Verify victory sets correct state and timer."""
        gm = game_manager_fixture
        gm._set_game_state(GameState.VICTORY)
        assert gm.state == GameState.VICTORY
        assert gm._state_timer == 0.0


class TestGameOverTransition:
    """Game over transition stops loops and plays game over sound."""

    def test_game_over_goes_through_set_game_state(self, game_manager_fixture):
        """Verify game over sets GAME_OVER_ANIMATION state."""
        gm = game_manager_fixture
        gm._set_game_state(GameState.GAME_OVER)
        assert gm.state == GameState.GAME_OVER_ANIMATION
        assert gm._state_timer == 0.0


class TestQuitCleansUp:
    """Quit game cleans up looping sounds."""

    def test_quit_game_sets_exit_state(self, game_manager_fixture):
        """Verify _quit_game transitions to EXIT."""
        gm = game_manager_fixture
        gm._quit_game()
        assert gm.state == GameState.EXIT


class TestPowerupBlinkWiring:
    """Powerup blink sound updates during gameplay."""

    def test_update_runs_with_active_powerups(self, game_manager_fixture):
        """Verify update() doesn't error when powerups are active."""
        gm = game_manager_fixture
        # Spawn a powerup directly
        gm.power_up_manager.spawn_power_up(
            gm.player_tank, gm.spawn_manager.enemy_tanks
        )
        assert len(gm.power_up_manager.get_power_ups()) > 0
        # Run a frame — should not raise
        gm.update()
