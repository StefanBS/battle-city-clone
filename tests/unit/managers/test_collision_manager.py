"""Unit tests for CollisionManager: one frame's collisions in, outcomes out.

Real ``core/`` entities on a real Map, EffectManager and PowerUpManager; only
I/O (TextureManager, SoundManager) is mocked. See the Collision exception in
CLAUDE.md.
"""

import pygame
import pytest
from unittest.mock import MagicMock

from src.core.bullet import Bullet
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.core.tile import BrickVariant, TileType
from src.managers.collision_manager import CollisionManager
from src.managers.effect_manager import EffectManager
from src.managers.outcomes import (
    BaseDestroyed,
    CarrierHit,
    EnemyDestroyed,
    PlayerDestroyed,
    PowerUpCollected,
)
from src.managers.power_up_manager import PowerUpManager
from src.managers.sound_manager import SoundManager
from src.managers.texture_manager import TextureManager
from src.utils.constants import FPS, TILE_SIZE, Direction, PowerUpType, TankType
from src.utils.paths import resource_path

DT = 1.0 / FPS
LEVEL_01 = resource_path("assets/maps/level_01.tmx")


@pytest.fixture
def texture_manager():
    """Mock TextureManager whose sprites are blank surfaces.

    EffectManager colour-keys its frames, so a MagicMock surface won't do.
    """
    tm = MagicMock(spec=TextureManager)
    tm.get_sprite.side_effect = lambda *args, **kwargs: pygame.Surface(
        (TILE_SIZE, TILE_SIZE)
    )
    return tm


@pytest.fixture
def game_map(texture_manager):
    """Level 01 with every tile cleared, so each test places what it needs."""
    game_map = Map(LEVEL_01, texture_manager)
    for row in game_map.tiles:
        for tile in row:
            if tile is not None:
                game_map.set_tile_type(tile, TileType.EMPTY)
    return game_map


@pytest.fixture
def effects(texture_manager):
    return EffectManager(texture_manager)


@pytest.fixture
def power_ups(texture_manager, game_map):
    return PowerUpManager(texture_manager, game_map)


@pytest.fixture
def sound():
    return MagicMock(spec=SoundManager)


@pytest.fixture
def collisions(game_map, effects, power_ups, sound):
    return CollisionManager(
        game_map=game_map,
        effect_manager=effects,
        power_up_manager=power_ups,
        sound_manager=sound,
    )


@pytest.fixture
def make_player(texture_manager, game_map):
    def _make(x=0, y=0, player_id=1):
        return PlayerTank(
            x,
            y,
            TILE_SIZE,
            texture_manager,
            map_width_px=game_map.width_px,
            map_height_px=game_map.height_px,
            player_id=player_id,
        )

    return _make


@pytest.fixture
def make_enemy(texture_manager, game_map):
    def _make(x=0, y=0, tank_type=TankType.BASIC, is_carrier=False):
        return EnemyTank(
            x,
            y,
            TILE_SIZE,
            texture_manager,
            tank_type,
            map_width_px=game_map.width_px,
            map_height_px=game_map.height_px,
            is_carrier=is_carrier,
        )

    return _make


def place(game_map, tile_type, x, y):
    """Put a ``tile_type`` tile at grid cell (x, y) and return it."""
    tile = game_map.get_tile_at(x, y)
    game_map.set_tile_type(tile, tile_type)
    return tile


def step_move(tank, dx, dy):
    """One frame of ``tank`` moving by (dx, dy), as the TankStepper runs it."""
    tank.update(DT)
    tank.move(dx, dy, DT)


def stand_still(tank):
    """One frame of ``tank`` not moving."""
    tank.update(DT)


def bullet_on(target_rect, owner, direction=Direction.UP, power_bullet=False):
    """A bullet fired by ``owner``, sitting in the middle of ``target_rect``."""
    return Bullet(
        target_rect.centerx,
        target_rect.centery,
        direction,
        owner,
        power_bullet=power_bullet,
    )


class TestPlayerBulletVsEnemy:
    def test_destroys_a_basic_enemy(self, collisions, make_player, make_enemy):
        player = make_player(0, 300)
        enemy = make_enemy(100, 100)
        bullet = bullet_on(enemy.rect, player)

        outcomes = collisions.resolve(
            players=[player], enemies=[enemy], bullets=[bullet]
        )

        assert outcomes == [EnemyDestroyed(enemy, by=player)]
        assert not bullet.active

    def test_armored_enemy_absorbs_a_hit(self, collisions, make_player, make_enemy):
        player = make_player(0, 300)
        enemy = make_enemy(100, 100, TankType.ARMOR)
        health = enemy.health
        bullet = bullet_on(enemy.rect, player)

        outcomes = collisions.resolve(
            players=[player], enemies=[enemy], bullets=[bullet]
        )

        assert outcomes == []
        assert enemy.health == health - 1
        assert not bullet.active

    def test_hitting_a_carrier_drops_its_power_up_first(
        self, collisions, make_player, make_enemy
    ):
        player = make_player(0, 300)
        enemy = make_enemy(100, 100, is_carrier=True)
        bullet = bullet_on(enemy.rect, player)

        outcomes = collisions.resolve(
            players=[player], enemies=[enemy], bullets=[bullet]
        )

        assert outcomes == [CarrierHit(enemy), EnemyDestroyed(enemy, by=player)]

    def test_second_bullet_passes_through_an_enemy_destroyed_this_frame(
        self, collisions, make_player, make_enemy
    ):
        player = make_player(0, 300)
        enemy = make_enemy(100, 100)
        first, second = bullet_on(enemy.rect, player), bullet_on(enemy.rect, player)

        outcomes = collisions.resolve(
            players=[player], enemies=[enemy], bullets=[first, second]
        )

        assert outcomes == [EnemyDestroyed(enemy, by=player)]
        assert not first.active
        assert second.active

    def test_enemy_bullet_passes_through_an_enemy(self, collisions, make_enemy):
        shooter = make_enemy(300, 300)
        enemy = make_enemy(100, 100)
        bullet = bullet_on(enemy.rect, shooter)

        outcomes = collisions.resolve(
            players=[], enemies=[shooter, enemy], bullets=[bullet]
        )

        assert outcomes == []
        assert bullet.active
        assert enemy.health == enemy.max_health

    def test_a_bullet_stops_at_the_first_enemy_it_hits(
        self, collisions, make_player, make_enemy
    ):
        player = make_player(0, 300)
        first, second = make_enemy(100, 100), make_enemy(100, 100)
        bullet = bullet_on(first.rect, player)

        outcomes = collisions.resolve(
            players=[player], enemies=[first, second], bullets=[bullet]
        )

        assert outcomes == [EnemyDestroyed(first, by=player)]
        assert second.health == second.max_health


class TestBulletVsPlayer:
    def test_enemy_bullet_destroys_a_player_who_loses_a_life(
        self, collisions, make_player, make_enemy
    ):
        player = make_player(100, 100)
        lives = player.lives
        bullet = bullet_on(player.rect, make_enemy(300, 300))

        outcomes = collisions.resolve(players=[player], enemies=[], bullets=[bullet])

        assert outcomes == [PlayerDestroyed(player)]
        assert player.lives == lives - 1
        assert not bullet.active

    def test_invincible_player_absorbs_an_enemy_bullet(
        self, collisions, make_player, make_enemy
    ):
        player = make_player(100, 100)
        player.is_invincible = True
        lives = player.lives
        bullet = bullet_on(player.rect, make_enemy(300, 300))

        outcomes = collisions.resolve(players=[player], enemies=[], bullets=[bullet])

        assert outcomes == []
        assert player.lives == lives
        assert not bullet.active

    def test_second_bullet_passes_through_a_player_destroyed_this_frame(
        self, collisions, make_player, make_enemy
    ):
        player = make_player(100, 100)
        lives = player.lives
        shooter = make_enemy(300, 300)
        first, second = bullet_on(player.rect, shooter), bullet_on(player.rect, shooter)

        outcomes = collisions.resolve(
            players=[player], enemies=[], bullets=[first, second]
        )

        assert outcomes == [PlayerDestroyed(player)]
        assert player.lives == lives - 1
        assert second.active

    def test_friendly_fire_freezes_the_other_player(self, collisions, make_player):
        shooter, target = make_player(0, 300), make_player(100, 100, player_id=2)
        lives = target.lives
        bullet = bullet_on(target.rect, shooter)

        outcomes = collisions.resolve(
            players=[shooter, target], enemies=[], bullets=[bullet]
        )

        assert outcomes == []
        assert target.is_frozen
        assert target.lives == lives
        assert not bullet.active

    def test_friendly_fire_does_not_freeze_an_invincible_player(
        self, collisions, make_player
    ):
        shooter, target = make_player(0, 300), make_player(100, 100, player_id=2)
        target.is_invincible = True
        bullet = bullet_on(target.rect, shooter)

        collisions.resolve(players=[shooter, target], enemies=[], bullets=[bullet])

        assert not target.is_frozen
        assert not bullet.active

    def test_a_players_own_bullet_does_not_hit_it(self, collisions, make_player):
        player = make_player(100, 100)
        bullet = bullet_on(player.rect, player)

        outcomes = collisions.resolve(players=[player], enemies=[], bullets=[bullet])

        assert outcomes == []
        assert not player.is_frozen
        assert bullet.active


class TestBulletVsTile:
    def test_bullet_damages_a_brick(self, collisions, game_map, effects, make_player):
        brick = place(game_map, TileType.BRICK, 6, 6)
        bullet = bullet_on(brick.rect, make_player(0, 300))

        outcomes = collisions.resolve(players=[], enemies=[], bullets=[bullet])

        assert outcomes == []
        assert brick.brick_variant is not BrickVariant.FULL
        assert not bullet.active
        assert len(effects.effects) == 1

    def test_steel_stops_a_bullet_and_stays(self, collisions, game_map, make_player):
        steel = place(game_map, TileType.STEEL, 6, 6)
        bullet = bullet_on(steel.rect, make_player(0, 300))

        collisions.resolve(players=[], enemies=[], bullets=[bullet])

        assert steel.type is TileType.STEEL
        assert not bullet.active

    def test_power_bullet_clears_steel(self, collisions, game_map, make_player):
        steel = place(game_map, TileType.STEEL, 6, 6)
        bullet = bullet_on(steel.rect, make_player(0, 300), power_bullet=True)

        collisions.resolve(players=[], enemies=[], bullets=[bullet])

        assert steel.type is TileType.EMPTY
        assert not bullet.active

    def test_bullet_destroys_the_base(self, collisions, game_map, make_enemy):
        base = place(game_map, TileType.BASE, 12, 24)
        bullet = bullet_on(base.rect, make_enemy(0, 0), Direction.DOWN)

        outcomes = collisions.resolve(players=[], enemies=[], bullets=[bullet])

        assert outcomes == [BaseDestroyed()]
        assert game_map.is_base_destroyed
        assert not bullet.active

    def test_bullet_hits_an_enemy_before_the_brick_under_it(
        self, collisions, game_map, make_player, make_enemy
    ):
        enemy = make_enemy(96, 96)
        brick = place(game_map, TileType.BRICK, 6, 6)
        player = make_player(0, 300)
        bullet = bullet_on(brick.rect, player)

        outcomes = collisions.resolve(
            players=[player], enemies=[enemy], bullets=[bullet]
        )

        assert outcomes == [EnemyDestroyed(enemy, by=player)]
        assert brick.brick_variant is BrickVariant.FULL


class TestBulletVsBullet:
    def test_bullets_heading_at_each_other_cannot_pass_through(
        self, collisions, effects, make_player, make_enemy
    ):
        player_bullet = Bullet(100, 110, Direction.UP, make_player(0, 300))
        enemy_bullet = Bullet(100, 100, Direction.DOWN, make_enemy(300, 0))
        # A long frame, so they cross without ever overlapping.
        player_bullet.update(0.1)
        enemy_bullet.update(0.1)
        assert not player_bullet.rect.colliderect(enemy_bullet.rect)

        outcomes = collisions.resolve(
            players=[], enemies=[], bullets=[player_bullet, enemy_bullet]
        )

        assert outcomes == []
        assert not player_bullet.active
        assert not enemy_bullet.active
        assert effects.effects == []


class TestTankVsTile:
    @pytest.mark.parametrize("tile_type", [TileType.STEEL, TileType.WATER])
    def test_tank_is_stopped_flush_against_a_blocking_tile(
        self, collisions, game_map, make_player, tile_type
    ):
        place(game_map, tile_type, 4, 5)
        player = make_player(64, 96)
        step_move(player, 0, -1)
        assert player.y < 96

        collisions.resolve(players=[player], enemies=[], bullets=[])

        assert player.y == 96

    def test_tank_against_two_tiles_is_stopped_once(
        self, collisions, game_map, make_enemy
    ):
        place(game_map, TileType.STEEL, 4, 5)
        place(game_map, TileType.STEEL, 5, 5)
        enemy = make_enemy(64, 96)
        enemy.movement_blocked_listener = MagicMock()
        step_move(enemy, 0, -1)

        collisions.resolve(players=[], enemies=[enemy], bullets=[])

        assert enemy.y == 96
        enemy.movement_blocked_listener.assert_called_once()

    def test_tank_moves_over_a_bush(self, collisions, game_map, make_player):
        place(game_map, TileType.BUSH, 4, 5)
        player = make_player(64, 96)
        step_move(player, 0, -1)
        moved_to = player.y

        collisions.resolve(players=[player], enemies=[], bullets=[])

        assert player.y == moved_to


class TestTankVsTank:
    def test_both_moving_toward_each_other_are_stopped(
        self, collisions, make_player, make_enemy
    ):
        player, enemy = make_player(96, 128), make_enemy(96, 96)
        step_move(player, 0, -1)
        step_move(enemy, 0, 1)

        collisions.resolve(players=[player], enemies=[enemy], bullets=[])

        assert (player.x, player.y) == (96, 128)
        assert (enemy.x, enemy.y) == (96, 96)

    def test_only_the_tank_that_moved_in_is_stopped(
        self, collisions, make_player, make_enemy
    ):
        player, enemy = make_player(96, 128), make_enemy(96, 96)
        step_move(player, 0, -1)
        stand_still(enemy)

        collisions.resolve(players=[player], enemies=[enemy], bullets=[])

        assert (player.x, player.y) == (96, 128)
        assert (enemy.x, enemy.y) == (96, 96)

    @pytest.mark.parametrize("standing_first", [True, False])
    def test_a_standing_enemy_is_not_told_it_was_blocked(
        self, collisions, make_enemy, standing_first
    ):
        standing, mover = make_enemy(96, 128), make_enemy(96, 96)
        standing.movement_blocked_listener = MagicMock()
        mover.movement_blocked_listener = MagicMock()
        stand_still(standing)
        step_move(mover, 0, 1)
        enemies = [standing, mover] if standing_first else [mover, standing]

        collisions.resolve(players=[], enemies=enemies, bullets=[])

        standing.movement_blocked_listener.assert_not_called()
        mover.movement_blocked_listener.assert_called_once()
        assert (mover.x, mover.y) == (96, 96)

    def test_tank_moving_across_keeps_its_move(
        self, collisions, make_player, make_enemy
    ):
        player, enemy = make_player(96, 128), make_enemy(96, 96)
        step_move(player, 0, -1)
        step_move(enemy, 1, 0)
        enemy_moved_to = (enemy.x, enemy.y)

        collisions.resolve(players=[player], enemies=[enemy], bullets=[])

        assert (player.x, player.y) == (96, 128)
        assert (enemy.x, enemy.y) == enemy_moved_to

    def test_two_enemies_moving_toward_each_other_are_stopped(
        self, collisions, make_enemy
    ):
        left, right = make_enemy(96, 96), make_enemy(128, 96)
        step_move(left, 1, 0)
        step_move(right, -1, 0)

        collisions.resolve(players=[], enemies=[left, right], bullets=[])

        assert (left.x, left.y) == (96, 96)
        assert (right.x, right.y) == (128, 96)

    def test_tanks_already_overlapping_are_free_to_separate(
        self, collisions, make_enemy
    ):
        first, second = make_enemy(96, 96), make_enemy(96, 96)
        step_move(first, -1, 0)
        step_move(second, 1, 0)
        first_moved_to, second_moved_to = (first.x, first.y), (second.x, second.y)

        collisions.resolve(players=[], enemies=[first, second], bullets=[])

        assert (first.x, first.y) == first_moved_to
        assert (second.x, second.y) == second_moved_to


class TestPlayerVsPowerUp:
    def test_player_collects_a_power_up(self, collisions, power_ups, make_player):
        player = make_player(100, 100)
        power_ups.spawn_power_up(power_up_type=PowerUpType.STAR, position=(100, 100))

        outcomes = collisions.resolve(players=[player], enemies=[], bullets=[])

        assert outcomes == [PowerUpCollected(PowerUpType.STAR, player)]
        assert power_ups.active_power_ups == []

    def test_only_the_first_player_on_it_collects_it(
        self, collisions, power_ups, make_player
    ):
        first, second = make_player(100, 100), make_player(100, 100, player_id=2)
        power_ups.spawn_power_up(power_up_type=PowerUpType.STAR, position=(100, 100))

        outcomes = collisions.resolve(players=[first, second], enemies=[], bullets=[])

        assert outcomes == [PowerUpCollected(PowerUpType.STAR, first)]

    def test_a_player_destroyed_this_frame_cannot_collect(
        self, collisions, power_ups, make_player, make_enemy
    ):
        player = make_player(100, 100)
        power_ups.spawn_power_up(power_up_type=PowerUpType.STAR, position=(100, 100))
        bullet = bullet_on(player.rect, make_enemy(300, 300))

        outcomes = collisions.resolve(players=[player], enemies=[], bullets=[bullet])

        assert outcomes == [PlayerDestroyed(player)]
        assert len(power_ups.active_power_ups) == 1

    def test_an_enemy_does_not_collect(self, collisions, power_ups, make_enemy):
        enemy = make_enemy(100, 100)
        power_ups.spawn_power_up(power_up_type=PowerUpType.STAR, position=(100, 100))

        outcomes = collisions.resolve(players=[], enemies=[enemy], bullets=[])

        assert outcomes == []
        assert len(power_ups.active_power_ups) == 1
