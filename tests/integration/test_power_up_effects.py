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
from tests.integration.conftest import (
    first_player,
    let_spawning_enemies_appear,
    spawn_enemy_at,
)


class TestPowerUpEffectsIntegration:
    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    def _collect_power_up(self, game, power_up_type):
        """Drop a specific power-up and put the Player on it to collect it."""
        game.battle.drop_power_up(power_up_type)
        assert len(game.battle.scene().power_ups) == 1
        # Move player to power-up location to trigger collision
        pu = game.battle.scene().power_ups[0]
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
        let_spawning_enemies_appear(game)
        enemies_before = len(game.battle.scene().enemies)
        assert enemies_before > 0
        self._collect_power_up(game, PowerUpType.BOMB)
        game.update()
        assert len(game.battle.scene().enemies) == 0


class TestRemainingPowerUpEffects:
    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    def test_clock_effect(self, game):
        game.battle.apply_outcomes(
            [PowerUpCollected(PowerUpType.CLOCK, first_player(game))]
        )
        enemy = spawn_enemy_at(game, 0, 0)
        game.update()
        assert enemy.is_frozen is True

    def test_shovel_effect(self, game):
        game.battle.apply_outcomes(
            [PowerUpCollected(PowerUpType.SHOVEL, first_player(game))]
        )
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
