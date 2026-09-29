"""Integration tests for the power-up spawn system.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.battle.outcomes import EnemyDestroyed
from src.utils.constants import POWERUP_TIMEOUT
from tests.integration.conftest import clear_enemies, spawn_carrier, tick_for


class TestPowerUpIntegration:
    """Full-cycle integration tests for the power-up system."""

    @pytest.fixture
    def carrier(self, battle):
        return spawn_carrier(battle)

    def test_carrier_enemy_exists(self, carrier):
        """The 4th spawned enemy should be a carrier."""
        assert carrier.is_carrier is True

    def test_destroying_carrier_spawns_power_up(self, battle, carrier):
        """Killing a carrier enemy should spawn a power-up on the map."""
        battle.apply_outcomes([EnemyDestroyed(carrier, by=None)])
        assert len(battle.scene().power_ups) == 1

    def test_power_up_timeout(self, battle):
        """Power-up should disappear after timeout."""
        clear_enemies(battle)
        battle.drop_power_up()
        tick_for(battle, POWERUP_TIMEOUT + 0.1)
        assert len(battle.scene().power_ups) == 0

    def test_carrier_spawning_clears_power_up(self, battle):
        """A new carrier appearing removes the power-up on the battlefield."""
        battle.drop_power_up()
        spawn_carrier(battle)
        assert battle.scene().power_ups == ()
