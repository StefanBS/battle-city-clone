"""Integration tests for player shield animation with real game objects."""

from src.utils.constants import FPS


class TestShieldIntegration:
    def test_shield_active_after_spawn(self, game_manager_fixture):
        """Player tank has shield active after game start (spawn invincibility)."""
        gm = game_manager_fixture
        assert gm.player_tank.is_invincible
        assert gm.player_tank.is_shield_active

    def test_shield_deactivates_during_warning(self, game_manager_fixture):
        """Shield deactivates when remaining time <= warning duration."""
        gm = game_manager_fixture
        # 3s duration - 2s warning = 1s shield. At 1.5s, only 1.5s remain < 2s warning
        gm.player_tank.invincibility_timer = 1.5
        assert gm.player_tank.is_shield_active is False

    def test_draw_with_shield_does_not_raise(self, game_manager_fixture):
        """Verify draw() works during shield phase."""
        gm = game_manager_fixture
        assert gm.player_tank.is_shield_active
        for _ in range(5):
            gm.update()

    def test_shield_deactivates_when_invincibility_expires(
        self, game_manager_fixture
    ):
        """Shield gone after invincibility expires."""
        gm = game_manager_fixture
        gm.player_tank.invincibility_timer = 4.0  # past 3s duration
        gm.player_tank.update(1.0 / FPS)
        assert not gm.player_tank.is_invincible
        assert not gm.player_tank.is_shield_active
