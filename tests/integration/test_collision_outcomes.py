"""Integration tests for collision outcomes applied in one place (GameManager).

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.core.bullet import Bullet
from src.states.game_state import GameState
from src.utils.constants import (
    Direction,
    POWERUP_COLLECT_POINTS,
    TILE_SIZE,
    PowerUpType,
    TankType,
)
from tests.integration.conftest import (
    clear_enemies,
    first_player,
    place_player_at,
    spawn_carrier,
    spawn_enemy_at,
)


@pytest.fixture
def game(game_manager_fixture):
    game_manager_fixture.state = GameState.RUNNING
    return game_manager_fixture


def _enemy_bullet_on(game, target_rect, owner):
    """An Enemy bullet sitting in the middle of ``target_rect``."""
    bullet = Bullet(target_rect.centerx, target_rect.centery, Direction.DOWN, owner)
    game.battle.tank_stepper.bullets.append(bullet)
    return bullet


def _idle_enemy(game):
    """An Enemy far from the Player that neither moves nor shoots."""
    enemy = spawn_enemy_at(game, 0, 0, fires=False, turns=False)
    enemy.speed = 0
    return enemy


def _stop_spawning(game):
    """No Enemies left to spawn, so the stage can be won."""
    clear_enemies(game, reset_total=False)
    game.battle.spawn_manager.total_enemy_spawns = (
        game.battle.spawn_manager.max_enemy_spawns
    )


class TestPowerUps:
    def test_first_hit_on_armored_carrier_drops_its_power_up(self, game):
        carrier = spawn_enemy_at(
            game, 0, 0, TankType.ARMOR, fires=False, is_carrier=True
        )
        carrier.speed = 0
        player = first_player(game)

        for _ in range(2):
            bullet = Bullet(
                carrier.rect.centerx, carrier.rect.centery, Direction.UP, player
            )
            game.battle.tank_stepper.bullets.append(bullet)
            game.update()

        assert carrier in game.battle.enemy_manager.enemies
        assert not carrier.is_carrier
        assert len(game.battle.power_up_manager.active_power_ups) == 1

    def test_grenade_kill_on_carrier_drops_a_power_up(self, game):
        carrier = spawn_carrier(game)
        carrier.speed = 0
        player = first_player(game)
        game.battle.power_up_manager.spawn_power_up(
            power_up_type=PowerUpType.BOMB, position=(int(player.x), int(player.y))
        )

        game.update()

        assert carrier not in game.battle.enemy_manager.enemies
        assert len(game.battle.power_up_manager.active_power_ups) == 1
        # The Grenade kill scores nothing; only the pickup does.
        assert game.battle.player_manager.get_score(1) == POWERUP_COLLECT_POINTS


class TestPlayerDestroyed:
    def test_losing_a_life_respawns_the_player(self, game):
        player = first_player(game)
        player.is_invincible = False
        place_player_at(game, 4 * TILE_SIZE, 6 * TILE_SIZE)
        _enemy_bullet_on(game, player.rect, _idle_enemy(game))

        game.update()

        assert (player.x, player.y) == player.initial_position
        assert player.is_invincible
        assert game.state == GameState.RUNNING

    def test_losing_the_last_life_is_game_over(self, game):
        player = first_player(game)
        player.is_invincible = False
        player.restore_lives(1)
        _enemy_bullet_on(game, player.rect, _idle_enemy(game))

        game.update()

        assert game.state == GameState.GAME_OVER_ANIMATION


class TestBaseDestroyed:
    def test_game_over_wins_over_victory_in_the_same_frame(self, game):
        _stop_spawning(game)
        base_rect = game.battle.map.get_base().rect
        # The bullet's owner is not on the battlefield, so no Enemies remain.
        _enemy_bullet_on(game, base_rect, spawn_enemy_at(game, 0, 0))
        clear_enemies(game, reset_total=False)

        game.update()

        assert game.battle.map.is_base_destroyed
        assert game.battle.spawn_manager.is_exhausted
        assert not game.battle.enemy_manager.enemies
        assert game.state == GameState.GAME_OVER_ANIMATION
