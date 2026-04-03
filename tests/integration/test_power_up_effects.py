"""Integration tests for power-up effects.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.utils.constants import (
    HELMET_INVINCIBILITY_DURATION,
    PowerUpType,
)
from tests.integration.conftest import flush_pending_spawns, spawn_carrier


class TestPowerUpEffectsIntegration:
    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    def _collect_power_up(self, game, power_up_type):
        """Spawn a carrier, destroy it, spawn a specific power-up, collect it."""
        carrier = spawn_carrier(game)
        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            game.player_tank,
            game.spawn_manager.enemy_tanks,
            power_up_type=power_up_type,
        )
        assert game.power_up_manager.active_power_up is not None
        # Move player to power-up location to trigger collision
        pu = game.power_up_manager.active_power_up
        game.player_tank.set_position(pu.x, pu.y)
        game.player_tank.rect.topleft = (round(pu.x), round(pu.y))

    def test_helmet_effect(self, game):
        self._collect_power_up(game, PowerUpType.HELMET)
        game.update()
        assert game.player_tank.is_invincible is True
        assert game.player_tank.invincibility_duration == HELMET_INVINCIBILITY_DURATION

    def test_extra_life_effect(self, game):
        lives_before = game.player_tank.lives
        self._collect_power_up(game, PowerUpType.EXTRA_LIFE)
        game.update()
        assert game.player_tank.lives == lives_before + 1

    def test_bomb_effect(self, game):
        flush_pending_spawns(game)
        enemies_before = len(game.spawn_manager.enemy_tanks)
        assert enemies_before > 0
        self._collect_power_up(game, PowerUpType.BOMB)
        game.update()
        assert len(game.spawn_manager.enemy_tanks) == 0
