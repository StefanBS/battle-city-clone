"""Integration tests for the power-up spawn system.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.utils.constants import POWERUP_TIMEOUT, PowerUpType
from tests.integration.conftest import first_player, spawn_carrier


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
            [first_player(game), *game.spawn_manager.enemy_tanks]
        )
        assert len(game.power_up_manager.active_power_ups) == 1

    def test_power_up_timeout(self, game, carrier):
        """Power-up should disappear after timeout."""
        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            [first_player(game), *game.spawn_manager.enemy_tanks]
        )
        game.power_up_manager.update(POWERUP_TIMEOUT + 0.1)
        assert len(game.power_up_manager.active_power_ups) == 0

    def test_new_power_up_replaces_existing(self, game, carrier):
        """Only one power-up is on the battlefield at a time."""
        game.power_up_manager.spawn_power_up(
            [first_player(game)], power_up_type=PowerUpType.CLOCK
        )
        game.power_up_manager.spawn_power_up(
            [first_player(game)], power_up_type=PowerUpType.BOMB
        )
        types = [p.power_up_type for p in game.power_up_manager.active_power_ups]
        assert types == [PowerUpType.BOMB]

    def test_carrier_spawning_clears_power_up(self, game):
        """A new carrier appearing removes the power-up on the battlefield."""
        game.power_up_manager.spawn_power_up([first_player(game)])
        spawn_carrier(game)
        assert game.power_up_manager.active_power_ups == []
