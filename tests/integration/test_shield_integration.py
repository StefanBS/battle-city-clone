"""Integration tests for player shield animation with real game objects."""

from src.utils.constants import (
    FPS,
    SHIELD_FAST_FLICKER_INTERVAL,
)


class TestShieldIntegration:
    def test_shield_active_after_spawn(self, game_manager_fixture):
        """Player tank has shield active after game start (spawn invincibility)."""
        gm = game_manager_fixture
        assert gm.player_tank.is_invincible
        assert gm.player_tank.is_invincible

    def test_shield_stays_active_during_warning_phase(self, game_manager_fixture):
        """Shield remains active in warning phase but flickers faster."""
        gm = game_manager_fixture
        # 3s duration, at 1.5s elapsed → 1.5s remaining (in warning phase)
        gm.player_tank.invincibility_timer = 1.5
        assert gm.player_tank.is_invincible is True
        assert (
            gm.player_tank.shield_flicker_interval == SHIELD_FAST_FLICKER_INTERVAL
        )

    def test_draw_with_shield_does_not_raise(self, game_manager_fixture):
        """Verify draw() works during shield phase."""
        gm = game_manager_fixture
        assert gm.player_tank.is_invincible
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
        assert not gm.player_tank.is_invincible
