"""Integration tests for the power-up spawn system.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.utils.constants import POWERUP_TIMEOUT
from tests.integration.conftest import spawn_carrier


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
        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            game.player_tank, game.spawn_manager.enemy_tanks
        )
        assert len(game.power_up_manager.active_power_ups) == 1

    def test_power_up_timeout(self, game, carrier):
        """Power-up should disappear after timeout."""
        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            game.player_tank, game.spawn_manager.enemy_tanks
        )
        game.power_up_manager.update(POWERUP_TIMEOUT + 0.1)
        assert len(game.power_up_manager.active_power_ups) == 0

    def test_multiple_power_ups_allowed(self, game, carrier):
        """Multiple spawn calls should accumulate power-ups."""
        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            game.player_tank, game.spawn_manager.enemy_tanks
        )
        game.power_up_manager.spawn_power_up(
            game.player_tank, game.spawn_manager.enemy_tanks
        )
        assert len(game.power_up_manager.active_power_ups) == 2
