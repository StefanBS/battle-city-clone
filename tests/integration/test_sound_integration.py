"""Integration tests for sound effect wiring with real game objects."""

from src.states.screen import Screen
from src.utils.constants import FPS
from tests.integration.conftest import first_player


class TestEngineSoundWiring:
    """Engine sound updates are called during the game loop."""

    def test_engine_sound_updates_during_gameplay(self, game_manager_fixture):
        """Verify update() calls update_engine without error during RUNNING."""
        gm = game_manager_fixture
        assert gm.flow.screen == Screen.RUNNING
        for _ in range(5):
            gm.update()

    def test_player_movement_sets_is_moving(self, game_manager_fixture):
        """Verify player tank reports is_moving after move()."""
        gm = game_manager_fixture
        dt = 1.0 / FPS
        first_player(gm).move(1, 0, dt)
        assert first_player(gm).is_moving is True

    def test_player_is_moving_resets_after_update(self, game_manager_fixture):
        """Verify is_moving resets to False after tank.update()."""
        gm = game_manager_fixture
        dt = 1.0 / FPS
        first_player(gm).move(1, 0, dt)
        assert first_player(gm).is_moving is True
        first_player(gm).update(dt)
        assert first_player(gm).is_moving is False


class TestPowerupBlinkWiring:
    """Powerup blink sound updates during gameplay."""

    def test_update_runs_with_active_powerups(self, game_manager_fixture):
        """Verify update() doesn't error when powerups are active."""
        gm = game_manager_fixture
        gm.battle.drop_power_up()
        assert len(gm.battle.scene().power_ups) > 0
        gm.update()
