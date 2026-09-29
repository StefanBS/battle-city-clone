"""Integration tests for power-up effects.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

from src.utils.constants import (
    BULLET_SPEED,
    HELMET_INVINCIBILITY_DURATION,
    STAR_BULLET_SPEED_MULTIPLIER,
    PowerUpType,
)
from src.core.tile import TileType
from src.battle.outcomes import PowerUpCollected
from tests.integration.conftest import (
    first_player,
    let_spawning_enemies_appear,
    spawn_enemy_at,
    tick,
)


class TestPowerUpEffectsIntegration:
    def _collect_power_up(self, battle, power_up_type):
        """Drop a specific power-up and put the Player on it to collect it."""
        battle.drop_power_up(power_up_type)
        assert len(battle.scene().power_ups) == 1
        # Move player to power-up location to trigger collision
        pu = battle.scene().power_ups[0]
        first_player(battle).set_position(pu.x, pu.y)
        first_player(battle).rect.topleft = (round(pu.x), round(pu.y))

    def test_helmet_effect(self, battle):
        self._collect_power_up(battle, PowerUpType.HELMET)
        tick(battle)
        assert first_player(battle).is_invincible is True
        assert (
            first_player(battle).invincibility_duration == HELMET_INVINCIBILITY_DURATION
        )

    def test_extra_life_effect(self, battle):
        lives_before = first_player(battle).lives
        self._collect_power_up(battle, PowerUpType.EXTRA_LIFE)
        tick(battle)
        assert first_player(battle).lives == lives_before + 1

    def test_grenade_effect(self, battle):
        let_spawning_enemies_appear(battle)
        enemies_before = len(battle.scene().enemies)
        assert enemies_before > 0
        self._collect_power_up(battle, PowerUpType.GRENADE)
        tick(battle)
        assert len(battle.scene().enemies) == 0


class TestRemainingPowerUpEffects:
    def test_clock_effect(self, battle):
        battle.apply_outcomes(
            [PowerUpCollected(PowerUpType.CLOCK, first_player(battle))]
        )
        enemy = spawn_enemy_at(battle, 0, 0)
        tick(battle)
        assert enemy.is_frozen is True

    def test_shovel_effect(self, battle):
        battle.apply_outcomes(
            [PowerUpCollected(PowerUpType.SHOVEL, first_player(battle))]
        )
        tiles = battle.map.get_base_surrounding_tiles()
        steel_tiles = [t for t in tiles if t.type == TileType.STEEL]
        assert len(steel_tiles) > 0

    def test_star_effect(self, battle):
        battle.apply_outcomes(
            [PowerUpCollected(PowerUpType.STAR, first_player(battle))]
        )
        assert first_player(battle).star_level == 1
        expected_speed = BULLET_SPEED * STAR_BULLET_SPEED_MULTIPLIER
        assert first_player(battle).bullet_speed == expected_speed
