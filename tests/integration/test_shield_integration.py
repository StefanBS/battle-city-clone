"""Integration tests for player shield animation with real game objects."""

from src.utils.constants import (
    FPS,
    SHIELD_FAST_FLICKER_INTERVAL,
)
from tests.integration.conftest import first_player, tick


class TestShieldIntegration:
    def test_shield_active_after_spawn(self, battle):
        """Player tank has shield active after game start (spawn invincibility)."""
        assert first_player(battle).is_invincible

    def test_shield_stays_active_during_warning_phase(self, battle):
        """Shield remains active in warning phase but flickers faster."""
        # 3s duration, at 1.5s elapsed → 1.5s remaining (in warning phase)
        first_player(battle).invincibility_timer = 1.5
        assert first_player(battle).is_invincible is True
        assert (
            first_player(battle).shield_flicker_interval == SHIELD_FAST_FLICKER_INTERVAL
        )

    def test_frames_step_during_shield(self, battle):
        """Verify frames step during the shield phase."""
        assert first_player(battle).is_invincible
        tick(battle, 5)

    def test_shield_deactivates_when_invincibility_expires(self, battle):
        """Shield gone after invincibility expires."""
        first_player(battle).invincibility_timer = 4.0  # past 3s duration
        first_player(battle).update(1.0 / FPS)
        assert not first_player(battle).is_invincible
