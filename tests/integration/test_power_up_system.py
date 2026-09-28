"""Integration tests for the power-up spawn system.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.battle.outcomes import EnemyDestroyed
from src.utils.constants import FPS, POWERUP_TIMEOUT
from tests.integration.conftest import clear_enemies, spawn_carrier


class TestPowerUpIntegration:
    """Full-cycle integration tests for the power-up system."""

    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    @pytest.fixture
    def carrier(self, game):
        return spawn_carrier(game)

    def test_carrier_enemy_exists(self, carrier):
        """The 4th spawned enemy should be a carrier."""
        assert carrier.is_carrier is True

    def test_destroying_carrier_spawns_power_up(self, game, carrier):
        """Killing a carrier enemy should spawn a power-up on the map."""
        game.battle.apply_outcomes([EnemyDestroyed(carrier, by=None)])
        assert len(game.battle.scene().power_ups) == 1

    def test_power_up_timeout(self, game):
        """Power-up should disappear after timeout."""
        clear_enemies(game)
        game.battle.drop_power_up()
        for _ in range(int((POWERUP_TIMEOUT + 0.1) * FPS)):
            game.battle.step(1.0 / FPS)
        assert len(game.battle.scene().power_ups) == 0

    def test_carrier_spawning_clears_power_up(self, game):
        """A new carrier appearing removes the power-up on the battlefield."""
        game.battle.drop_power_up()
        spawn_carrier(game)
        assert game.battle.scene().power_ups == ()
