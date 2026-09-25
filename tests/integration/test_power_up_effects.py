"""Integration tests for power-up effects.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.utils.constants import (
    BULLET_SPEED,
    HELMET_INVINCIBILITY_DURATION,
    STAR_BULLET_SPEED_MULTIPLIER,
    PowerUpType,
)
from src.core.tile import TileType
from src.managers.outcomes import PowerUpCollected
from tests.integration.conftest import first_player, flush_pending_spawns, spawn_carrier


class TestPowerUpEffectsIntegration:
    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    def _collect_power_up(self, game, power_up_type):
        """Spawn a carrier, destroy it, spawn a specific power-up, collect it."""
        carrier = spawn_carrier(game)
        game.battle.enemy_manager.remove(carrier)
        game.battle.power_up_manager.spawn_power_up(
            [first_player(game), *game.battle.enemy_manager.enemies],
            power_up_type=power_up_type,
        )
        assert len(game.battle.power_up_manager.active_power_ups) == 1
        # Move player to power-up location to trigger collision
        pu = game.battle.power_up_manager.active_power_ups[0]
        first_player(game).set_position(pu.x, pu.y)
        first_player(game).rect.topleft = (round(pu.x), round(pu.y))

    def test_helmet_effect(self, game):
        self._collect_power_up(game, PowerUpType.HELMET)
        game.update()
        assert first_player(game).is_invincible is True
        assert (
            first_player(game).invincibility_duration == HELMET_INVINCIBILITY_DURATION
        )

    def test_extra_life_effect(self, game):
        lives_before = first_player(game).lives
        self._collect_power_up(game, PowerUpType.EXTRA_LIFE)
        game.update()
        assert first_player(game).lives == lives_before + 1

    def test_bomb_effect(self, game):
        flush_pending_spawns(game)
        enemies_before = len(game.battle.enemy_manager.enemies)
        assert enemies_before > 0
        self._collect_power_up(game, PowerUpType.BOMB)
        game.update()
        assert len(game.battle.enemy_manager.enemies) == 0


class TestRemainingPowerUpEffects:
    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    def test_clock_effect(self, game):
        game.battle.apply_outcomes(
            [PowerUpCollected(PowerUpType.CLOCK, first_player(game))]
        )
        assert game.battle.enemy_manager.enemies_frozen is True

    def test_shovel_effect(self, game):
        game.battle.apply_outcomes(
            [PowerUpCollected(PowerUpType.SHOVEL, first_player(game))]
        )
        assert game.battle.power_up_manager.shovel_timer > 0
        tiles = game.battle.map.get_base_surrounding_tiles()
        steel_tiles = [t for t in tiles if t.type == TileType.STEEL]
        assert len(steel_tiles) > 0

    def test_star_effect(self, game):
        game.battle.apply_outcomes(
            [PowerUpCollected(PowerUpType.STAR, first_player(game))]
        )
        assert first_player(game).star_level == 1
        expected_speed = BULLET_SPEED * STAR_BULLET_SPEED_MULTIPLIER
        assert first_player(game).bullet_speed == expected_speed
