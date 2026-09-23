"""Integration tests for collision outcomes applied in one place (GameManager).

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.core.bullet import Bullet
from src.states.game_state import GameState
from src.utils.constants import (
    Direction,
    HELMET_INVINCIBILITY_DURATION,
    POWERUP_COLLECT_POINTS,
    TILE_SIZE,
    PowerUpType,
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
    game.tank_stepper.bullets.append(bullet)
    return bullet


def _idle_enemy(game):
    """An Enemy far from the Player that neither moves nor shoots."""
    enemy = spawn_enemy_at(game, 0, 0)
    enemy.speed = 0
    enemy.shoot_interval = 999
    enemy.direction_change_interval = 999
    return enemy


def _stop_spawning(game):
    """No Enemies left to spawn, so the stage can be won."""
    clear_enemies(game, reset_total=False)
    game.spawn_manager.total_enemy_spawns = game.spawn_manager.max_enemy_spawns


class TestPowerUps:
    def test_two_power_ups_in_one_frame_both_applied(self, game):
        player = first_player(game)
        place_player_at(game, 4 * TILE_SIZE, 6 * TILE_SIZE)
        lives_before = player.lives
        for power_up_type in (PowerUpType.EXTRA_LIFE, PowerUpType.HELMET):
            game.power_up_manager.spawn_power_up(
                power_up_type=power_up_type, position=(int(player.x), int(player.y))
            )

        game.update()

        assert player.lives == lives_before + 1
        assert player.invincibility_duration == HELMET_INVINCIBILITY_DURATION
        assert game.player_manager.get_score(1) == 2 * POWERUP_COLLECT_POINTS

    def test_grenade_kill_on_carrier_drops_a_power_up(self, game):
        carrier = spawn_carrier(game)
        carrier.speed = 0
        player = first_player(game)
        game.power_up_manager.spawn_power_up(
            power_up_type=PowerUpType.BOMB, position=(int(player.x), int(player.y))
        )

        game.update()

        assert carrier not in game.spawn_manager.enemy_tanks
        assert len(game.power_up_manager.active_power_ups) == 1
        # The Grenade kill scores nothing; only the pickup does.
        assert game.player_manager.get_score(1) == POWERUP_COLLECT_POINTS


class TestPlayerDestroyed:
    def test_two_bullets_in_one_frame_cost_one_life(self, game):
        player = first_player(game)
        player.is_invincible = False
        lives_before = player.lives
        enemy = _idle_enemy(game)
        _enemy_bullet_on(game, player.rect, enemy)
        _enemy_bullet_on(game, player.rect, enemy)

        game.update()

        assert player.lives == lives_before - 1
        assert game.state == GameState.RUNNING

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
        player.lives = 1
        _enemy_bullet_on(game, player.rect, _idle_enemy(game))

        game.update()

        assert game.state == GameState.GAME_OVER_ANIMATION


class TestBaseDestroyed:
    def test_base_hit_is_game_over(self, game):
        _enemy_bullet_on(game, game.map.get_base().rect, _idle_enemy(game))

        game.update()

        assert game.map.is_base_destroyed
        assert game.state == GameState.GAME_OVER_ANIMATION

    def test_game_over_wins_over_victory_in_the_same_frame(self, game):
        _stop_spawning(game)
        base_rect = game.map.get_base().rect
        # The bullet's owner is not on the battlefield, so no Enemies remain.
        _enemy_bullet_on(game, base_rect, spawn_enemy_at(game, 0, 0))
        clear_enemies(game, reset_total=False)

        game.update()

        assert game.spawn_manager.all_enemies_defeated()
        assert game.state == GameState.GAME_OVER_ANIMATION
