"""Integration tests for collision outcomes applied in one place (the Battle).

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

from src.core.bullet import Bullet
from src.states.battle_result import BattleResult
from src.utils.constants import (
    Direction,
    POWERUP_COLLECT_POINTS,
    TILE_SIZE,
    PowerUpType,
    TankType,
)
from tests.integration.conftest import (
    first_player,
    place_player_at,
    score_of,
    spawn_carrier,
    spawn_enemy_at,
    tick,
    use_up_roster,
)


def _enemy_bullet_on(battle, target_rect, owner):
    """An Enemy bullet sitting in the middle of ``target_rect``."""
    bullet = Bullet(target_rect.centerx, target_rect.centery, Direction.DOWN, owner)
    battle.add_bullet(bullet)
    return bullet


def _idle_enemy(battle):
    """An Enemy far from the Player that neither moves nor shoots."""
    enemy = spawn_enemy_at(battle, 0, 0, fires=False, turns=False)
    enemy.speed = 0
    return enemy


class TestPowerUps:
    def test_first_hit_on_armored_carrier_drops_its_power_up(self, battle):
        carrier = spawn_enemy_at(
            battle, 0, 0, TankType.ARMOR, fires=False, is_carrier=True
        )
        carrier.speed = 0
        player = first_player(battle)

        for _ in range(2):
            bullet = Bullet(
                carrier.rect.centerx, carrier.rect.centery, Direction.UP, player
            )
            battle.add_bullet(bullet)
            tick(battle)

        assert carrier in battle.scene().enemies
        assert not carrier.is_carrier
        assert len(battle.scene().power_ups) == 1

    def test_grenade_kill_on_carrier_drops_a_power_up(self, battle):
        carrier = spawn_carrier(battle)
        carrier.speed = 0
        player = first_player(battle)
        battle.drop_power_up(
            PowerUpType.GRENADE, position=(int(player.x), int(player.y))
        )

        tick(battle)

        assert carrier not in battle.scene().enemies
        assert len(battle.scene().power_ups) == 1
        # The Grenade kill scores nothing; only the pickup does.
        assert score_of(battle) == POWERUP_COLLECT_POINTS


class TestPlayerDestroyed:
    def test_losing_a_life_respawns_the_player(self, battle):
        player = first_player(battle)
        player.is_invincible = False
        place_player_at(battle, 4 * TILE_SIZE, 6 * TILE_SIZE)
        _enemy_bullet_on(battle, player.rect, _idle_enemy(battle))

        tick(battle)

        assert (player.x, player.y) == player.initial_position
        assert player.is_invincible
        assert battle.result is None

    def test_losing_the_last_life_is_game_over(self, battle):
        player = first_player(battle)
        player.is_invincible = False
        player.restore_lives(1)
        _enemy_bullet_on(battle, player.rect, _idle_enemy(battle))

        tick(battle)

        assert battle.result is BattleResult.GAME_OVER


class TestBaseDestroyed:
    def test_game_over_wins_over_victory_in_the_same_frame(self, battle):
        base_rect = battle.map.get_base().rect
        _enemy_bullet_on(battle, base_rect, spawn_enemy_at(battle, 0, 0))
        # The bullet's owner is not on the battlefield, so no Enemies remain.
        use_up_roster(battle)

        tick(battle)

        assert battle.map.is_base_destroyed
        assert not battle.scene().enemies
        assert battle.result is BattleResult.GAME_OVER
