import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.collision_response_handler import CollisionResponseHandler
from src.managers.effect_manager import EffectManager
from src.managers.power_up_manager import PowerUpManager
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.tank import HitResult
from src.core.tile import Tile, TileType
from src.core.map import Map
from src.core.power_up import PowerUp
from src.managers.outcomes import (
    BaseDestroyed,
    CarrierHit,
    EnemyDestroyed,
    PlayerDestroyed,
    PowerUpCollected,
)
from src.utils.constants import (
    Direction,
    EffectType,
    FRIENDLY_FIRE_FREEZE_DURATION,
    OwnerType,
    TankType,
    TILE_SIZE,
    PowerUpType,
)


@pytest.fixture
def mock_map():
    mock = MagicMock(spec=Map)
    mock.set_tile_type = MagicMock()
    return mock


@pytest.fixture
def mock_effect_manager():
    return MagicMock(spec=EffectManager)


@pytest.fixture
def handler(mock_map, mock_effect_manager):
    return CollisionResponseHandler(
        game_map=mock_map,
        effect_manager=mock_effect_manager,
    )


@pytest.fixture
def mock_bullet(make_bullet):
    return make_bullet()


@pytest.fixture
def mock_enemy():
    e = MagicMock(spec=EnemyTank)
    e.owner_type = OwnerType.ENEMY
    e.tank_type = TankType.BASIC
    e.is_carrier = False
    e.take_damage = MagicMock(return_value=HitResult.ABSORBED)
    e.on_movement_blocked = MagicMock()
    e.revert_move = MagicMock()
    e.rect = pygame.Rect(0, 0, 32, 32)
    return e


def _make_player():
    """A mock Player that an Enemy bullet destroys."""
    p = MagicMock(spec=PlayerTank)
    p.owner_type = OwnerType.PLAYER
    p.is_invincible = False
    p.take_damage = MagicMock(return_value=HitResult.DESTROYED)
    p.revert_move = MagicMock()
    p.rect = pygame.Rect(0, 0, 32, 32)
    return p


@pytest.fixture
def mock_player():
    return _make_player()


@pytest.fixture
def mock_tile():
    t = MagicMock(spec=Tile)
    t.type = TileType.BRICK
    t.blocks_tanks = True
    t.blocks_bullets = True
    t.x = 0
    t.y = 0
    t.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
    return t


class TestDispatch:
    def test_lookup_swapped_order(self, handler, mock_bullet, mock_enemy):
        """Test registry finds handler with (EnemyTank, Bullet) order."""
        mock_bullet.owner_type = OwnerType.PLAYER
        handler.process_collisions([(mock_enemy, mock_bullet)])
        assert not mock_bullet.active

    def test_unregistered_pair_skipped(self, handler):
        """Test unregistered type pair logs warning and is skipped."""
        obj_a = MagicMock()
        obj_b = MagicMock()
        type(obj_a).__name__ = "Unknown"
        type(obj_b).__name__ = "Unknown"
        # Should not raise
        result = handler.process_collisions([(obj_a, obj_b)])
        assert result == []


class TestBulletVsEnemy:
    def test_player_bullet_damages_enemy(self, handler, mock_bullet, mock_enemy):
        mock_bullet.owner_type = OwnerType.PLAYER
        outcomes = handler.process_collisions([(mock_bullet, mock_enemy)])
        assert not mock_bullet.active
        mock_enemy.take_damage.assert_called_once()
        assert outcomes == []

    def test_player_bullet_destroys_enemy(self, handler, mock_bullet, mock_enemy):
        mock_bullet.owner_type = OwnerType.PLAYER
        mock_enemy.take_damage.return_value = HitResult.DESTROYED
        outcomes = handler.process_collisions([(mock_bullet, mock_enemy)])
        assert outcomes == [EnemyDestroyed(mock_enemy, by=mock_bullet.owner)]

    def test_second_bullet_passes_through_destroyed_enemy(
        self, handler, make_bullet, mock_enemy
    ):
        """Two bullets on one Enemy in a frame: the first gets the credit."""
        first = make_bullet()
        second = make_bullet()
        mock_enemy.take_damage.return_value = HitResult.DESTROYED
        outcomes = handler.process_collisions(
            [(first, mock_enemy), (second, mock_enemy)]
        )
        assert outcomes == [EnemyDestroyed(mock_enemy, by=first.owner)]
        mock_enemy.take_damage.assert_called_once()
        assert second.active

    def test_player_bullet_hits_carrier(self, handler, mock_bullet, mock_enemy):
        mock_enemy.is_carrier = True
        outcomes = handler.process_collisions([(mock_bullet, mock_enemy)])
        assert outcomes == [CarrierHit(mock_enemy)]

    def test_enemy_bullet_does_not_damage_enemy(self, handler, make_bullet, mock_enemy):
        """Friendly fire — enemy bullet should not damage enemy."""
        bullet = make_bullet(owner_type=OwnerType.ENEMY)
        handler.process_collisions([(bullet, mock_enemy)])
        mock_enemy.take_damage.assert_not_called()
        assert bullet.active  # Bullet not consumed


class TestBulletVsPlayer:
    def test_enemy_bullet_destroys_player_with_lives_left(
        self, handler, make_bullet, mock_player
    ):
        bullet = make_bullet(owner_type=OwnerType.ENEMY)
        outcomes = handler.process_collisions([(bullet, mock_player)])
        assert not bullet.active
        assert outcomes == [PlayerDestroyed(mock_player)]

    def test_enemy_bullet_eliminates_player_on_its_last_life(
        self, handler, make_bullet, mock_player
    ):
        bullet = make_bullet(owner_type=OwnerType.ENEMY)
        mock_player.take_damage.return_value = HitResult.ELIMINATED
        outcomes = handler.process_collisions([(bullet, mock_player)])
        assert outcomes == [PlayerDestroyed(mock_player)]

    def test_shielded_player_absorbs_enemy_bullet(
        self, handler, make_bullet, mock_player
    ):
        """The tank decides what its shield does to a hit, not the handler."""
        bullet = make_bullet(owner_type=OwnerType.ENEMY)
        mock_player.is_invincible = True
        mock_player.take_damage.return_value = HitResult.ABSORBED
        outcomes = handler.process_collisions([(bullet, mock_player)])
        assert not bullet.active
        mock_player.take_damage.assert_called_once()
        assert outcomes == []

    def test_second_bullet_passes_through_destroyed_player(
        self, handler, make_bullet, mock_player
    ):
        """A Player hit by two bullets in one frame loses only one life."""
        first = make_bullet(owner_type=OwnerType.ENEMY)
        second = make_bullet(owner_type=OwnerType.ENEMY)
        outcomes = handler.process_collisions(
            [(first, mock_player), (second, mock_player)]
        )
        assert outcomes == [PlayerDestroyed(mock_player)]
        mock_player.take_damage.assert_called_once()
        assert second.active


class TestBulletVsTile:
    """Bullet-vs-tile collision tests.

    Each tile is an 8x8 unit rendered at SUB_TILE_SIZE (16x16).
    Full bricks become half-bricks on first hit, then destroyed on second.
    """

    def test_bullet_damages_brick(self, handler, make_bullet, mock_map):
        """Bullet hitting a brick tile calls damage_brick with direction."""
        bullet = make_bullet(rect=pygame.Rect(64, 64, 4, 4), direction=Direction.RIGHT)
        tile = Tile(
            TileType.BRICK,
            4,
            4,
            blocks_tanks=True,
            blocks_bullets=True,
            is_destructible=True,
        )
        handler.process_collisions([(bullet, tile)])
        assert not bullet.active
        mock_map.damage_brick.assert_called_once_with(tile, "right", bullet.rect)

    def test_bullet_destroys_base(self, handler, make_bullet, mock_map):
        """Bullet hitting base destroys it and returns BaseDestroyed."""
        bullet = make_bullet(rect=pygame.Rect(0, 0, 4, 4), direction=Direction.DOWN)
        tile = MagicMock(spec=Tile)
        tile.type = TileType.BASE
        tile.blocks_bullets = True
        tile.is_destructible = False
        tile.x, tile.y = 0, 0
        outcomes = handler.process_collisions([(bullet, tile)])
        assert not bullet.active
        mock_map.destroy_base.assert_called_once()
        assert outcomes == [BaseDestroyed()]


class TestBulletVsBullet:
    def test_both_deactivated(self, handler, make_bullet):
        b1 = make_bullet()
        b2 = make_bullet(rect=pygame.Rect(2, 0, 2, 2))
        handler.process_collisions([(b1, b2)])
        assert not b1.active
        assert not b2.active


class TestTankVsTank:
    """Tank-vs-tank collision tests using real tank objects."""

    @staticmethod
    def _simulate_move(tank, dx, dy, dt=1.0 / 60):
        """Move tank and set up prev position as Tank.update() would."""
        tank.prev_x, tank.prev_y = tank.x, tank.y
        tank._move(dx, dy, dt)

    def test_both_moving_toward_each_other(
        self, handler, create_player_tank, create_enemy_tank
    ):
        """Both tanks moving toward each other: both reverted."""
        player = create_player_tank(x=96, y=128)
        enemy = create_enemy_tank(x=96, y=96)
        enemy.direction = Direction.DOWN
        self._simulate_move(player, 0, -1)
        self._simulate_move(enemy, 0, 1)
        handler.process_collisions([(player, enemy)])
        # Both should be snapped back to prev positions
        assert player.x == player.prev_x and player.y == player.prev_y
        assert enemy.x == enemy.prev_x and enemy.y == enemy.prev_y

    def test_only_aggressor_reverted(
        self, handler, create_player_tank, create_enemy_tank
    ):
        """Stationary enemy is not reverted when player moves into it."""
        player = create_player_tank(x=96, y=128)
        enemy = create_enemy_tank(x=96, y=96)
        enemy_pos_before = (enemy.x, enemy.y)
        self._simulate_move(player, 0, -1)
        # Enemy didn't move (prev == current)
        enemy.prev_x, enemy.prev_y = enemy.x, enemy.y
        handler.process_collisions([(player, enemy)])
        assert player.x == player.prev_x and player.y == player.prev_y
        assert (enemy.x, enemy.y) == enemy_pos_before

    def test_perpendicular_tank_not_reverted(
        self, handler, create_player_tank, create_enemy_tank
    ):
        """Enemy moving perpendicular to collision axis keeps its move."""
        player = create_player_tank(x=96, y=128)
        enemy = create_enemy_tank(x=96, y=96)
        enemy.direction = Direction.RIGHT
        self._simulate_move(player, 0, -1)
        self._simulate_move(enemy, 1, 0)
        enemy_pos_after_move = (enemy.x, enemy.y)
        handler.process_collisions([(player, enemy)])
        # Player reverted, enemy kept its perpendicular movement
        assert player.x == player.prev_x and player.y == player.prev_y
        assert (enemy.x, enemy.y) == enemy_pos_after_move

    def test_enemy_vs_enemy_both_moving_toward(self, handler, create_enemy_tank):
        """Two enemies moving toward each other: both reverted."""
        e1 = create_enemy_tank(x=96, y=96)
        e2 = create_enemy_tank(x=128, y=96)
        e1.direction = Direction.RIGHT
        e2.direction = Direction.LEFT
        self._simulate_move(e1, 1, 0)
        self._simulate_move(e2, -1, 0)
        handler.process_collisions([(e1, e2)])
        assert e1.x == e1.prev_x and e1.y == e1.prev_y
        assert e2.x == e2.prev_x and e2.y == e2.prev_y

    def test_pre_existing_overlap_allows_movement(self, handler, create_enemy_tank):
        """When tanks are already overlapping (e.g. from spawn), neither
        should be reverted — both must be free to move apart."""
        e1 = create_enemy_tank(x=100, y=100)
        e2 = create_enemy_tank(x=100, y=100)
        e1.direction = Direction.LEFT
        e2.direction = Direction.RIGHT
        self._simulate_move(e1, -1, 0)
        self._simulate_move(e2, 1, 0)
        e1_pos_after_move = (e1.x, e1.y)
        e2_pos_after_move = (e2.x, e2.y)
        handler.process_collisions([(e1, e2)])
        # Neither should be reverted — they're moving apart
        assert (e1.x, e1.y) == e1_pos_after_move
        assert (e2.x, e2.y) == e2_pos_after_move

    def test_pre_existing_overlap_does_not_block_movement(
        self, handler, create_enemy_tank
    ):
        """Pre-existing overlap should not report blocked movement,
        so tanks don't get permanently stuck."""
        e1 = create_enemy_tank(x=100, y=100)
        e2 = create_enemy_tank(x=100, y=100)
        e1.prev_x, e1.prev_y = e1.x, e1.y
        e2.prev_x, e2.prev_y = e2.x, e2.y
        e1.on_movement_blocked = MagicMock()
        e2.on_movement_blocked = MagicMock()
        handler.process_collisions([(e1, e2)])
        e1.on_movement_blocked.assert_not_called()
        e2.on_movement_blocked.assert_not_called()

    def test_cornered_enemy_movement_blocked(
        self, handler, create_player_tank, create_enemy_tank, mock_tile
    ):
        """When a cornered enemy gets tile + tank collisions, it is
        told that its movement was blocked."""
        mock_tile.type = TileType.STEEL
        mock_tile.rect = pygame.Rect(68, 100, TILE_SIZE, TILE_SIZE)
        enemy = create_enemy_tank(x=100, y=100)
        enemy.direction = Direction.LEFT
        enemy.prev_x, enemy.prev_y = enemy.x, enemy.y
        enemy.on_movement_blocked = MagicMock()
        pusher = create_player_tank(x=130, y=100)
        self._simulate_move(pusher, -1, 0)
        handler.process_collisions(
            [
                (enemy, mock_tile),
                (pusher, enemy),
            ]
        )
        enemy.on_movement_blocked.assert_called()


class TestTankVsTile:
    def test_player_reverted_on_blocking_tile(self, handler, mock_player, mock_tile):
        mock_tile.type = TileType.STEEL
        mock_tile.blocks_tanks = True
        handler.process_collisions([(mock_player, mock_tile)])
        mock_player.revert_move.assert_called_once_with(mock_tile.rect)

    def test_enemy_reverted_and_wall_hit(self, handler, mock_enemy, mock_tile):
        mock_tile.type = TileType.STEEL
        mock_tile.blocks_tanks = True
        handler.process_collisions([(mock_enemy, mock_tile)])
        mock_enemy.revert_move.assert_called_once_with(mock_tile.rect)
        mock_enemy.on_movement_blocked.assert_called_once()

    def test_non_blocking_tile_does_not_revert(self, handler, mock_player, mock_tile):
        mock_tile.type = TileType.BUSH
        mock_tile.blocks_tanks = False
        handler.process_collisions([(mock_player, mock_tile)])
        mock_player.revert_move.assert_not_called()


class TestTracking:
    def test_processed_bullet_not_reprocessed(self, handler, make_bullet, mock_enemy):
        """Same bullet in two events should only be processed once."""
        bullet = make_bullet()
        enemy2 = MagicMock(spec=EnemyTank)
        enemy2.take_damage = MagicMock(return_value=HitResult.ABSORBED)
        enemy2.owner_type = OwnerType.ENEMY
        handler.process_collisions(
            [
                (bullet, mock_enemy),
                (bullet, enemy2),
            ]
        )
        # Only first enemy should be damaged
        mock_enemy.take_damage.assert_called_once()
        enemy2.take_damage.assert_not_called()

    def test_reverted_tank_not_re_reverted(self, handler, mock_player):
        """Tank hitting two tiles should only revert once."""
        tile1 = MagicMock(spec=Tile)
        tile1.type = TileType.STEEL
        tile1.blocks_tanks = True
        tile1.x, tile1.y = 0, 0
        tile1.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        tile2 = MagicMock(spec=Tile)
        tile2.type = TileType.BRICK
        tile2.blocks_tanks = True
        tile2.x, tile2.y = 32, 0
        tile2.rect = pygame.Rect(32, 0, TILE_SIZE, TILE_SIZE)
        handler.process_collisions(
            [
                (mock_player, tile1),
                (mock_player, tile2),
            ]
        )
        mock_player.revert_move.assert_called_once()


class TestExplosionEffects:
    @pytest.mark.parametrize(
        "tile_type, is_destructible",
        [
            (TileType.BRICK, True),
            (TileType.STEEL, False),
            (TileType.BASE, False),
        ],
        ids=["brick", "steel", "base"],
    )
    def test_bullet_vs_tile_spawns_small_explosion(
        self, handler, make_bullet, mock_effect_manager, tile_type, is_destructible
    ):
        bullet = make_bullet(rect=pygame.Rect(50, 50, 2, 2))
        tile = MagicMock(spec=Tile)
        tile.type = tile_type
        tile.blocks_bullets = True
        tile.is_destructible = is_destructible
        tile.x, tile.y = 0, 0
        handler.process_collisions([(bullet, tile)])
        mock_effect_manager.spawn_at_rect.assert_called_once_with(
            EffectType.SMALL_EXPLOSION, bullet.rect
        )

    def test_bullet_vs_bullet_no_explosion(
        self, handler, make_bullet, mock_effect_manager
    ):
        b1 = make_bullet(rect=pygame.Rect(50, 50, 2, 2))
        b2 = make_bullet(rect=pygame.Rect(52, 50, 2, 2))
        handler.process_collisions([(b1, b2)])
        mock_effect_manager.spawn.assert_not_called()
        mock_effect_manager.spawn_at_rect.assert_not_called()


class TestPlayerVsPowerUp:
    """Tests for player-vs-powerup collision handling."""

    @pytest.fixture
    def mock_power_up_manager(self):
        manager = MagicMock(spec=PowerUpManager)
        manager.collect_power_up.return_value = PowerUpType.HELMET
        return manager

    @pytest.fixture
    def handler_with_powerup(
        self, mock_map, mock_effect_manager, mock_power_up_manager
    ):
        return CollisionResponseHandler(
            game_map=mock_map,
            effect_manager=mock_effect_manager,
            power_up_manager=mock_power_up_manager,
        )

    @pytest.fixture
    def mock_power_up(self):
        return MagicMock(spec=PowerUp)

    def test_player_collects_power_up(
        self, handler_with_powerup, mock_power_up_manager, mock_player, mock_power_up
    ):
        outcomes = handler_with_powerup.process_collisions(
            [(mock_player, mock_power_up)]
        )
        mock_power_up_manager.collect_power_up.assert_called_once_with(mock_power_up)
        assert outcomes == [PowerUpCollected(PowerUpType.HELMET, mock_player)]

    def test_power_up_not_collected_without_manager(
        self, mock_map, mock_effect_manager, mock_player, mock_power_up
    ):
        handler = CollisionResponseHandler(
            game_map=mock_map,
            effect_manager=mock_effect_manager,
        )
        result = handler.process_collisions([(mock_player, mock_power_up)])
        assert result == []

    def test_power_up_already_taken_this_frame_not_returned(
        self, handler_with_powerup, mock_power_up_manager, mock_player, mock_power_up
    ):
        mock_power_up_manager.collect_power_up.return_value = None
        outcomes = handler_with_powerup.process_collisions(
            [(mock_player, mock_power_up)]
        )
        assert outcomes == []

    def test_destroyed_player_cannot_collect(
        self,
        handler_with_powerup,
        mock_power_up_manager,
        mock_player,
        mock_power_up,
        make_bullet,
    ):
        bullet = make_bullet(owner_type=OwnerType.ENEMY)
        outcomes = handler_with_powerup.process_collisions(
            [(bullet, mock_player), (mock_player, mock_power_up)]
        )
        assert outcomes == [PlayerDestroyed(mock_player)]
        mock_power_up_manager.collect_power_up.assert_not_called()


class TestPowerBulletVsSteel:
    @pytest.fixture
    def power_bullet(self, make_bullet):
        return make_bullet(
            power_bullet=True,
            rect=pygame.Rect(100, 100, 4, 4),
            direction=Direction.RIGHT,
        )

    @pytest.fixture
    def normal_bullet(self, make_bullet):
        return make_bullet(
            rect=pygame.Rect(100, 100, 4, 4),
            direction=Direction.RIGHT,
        )

    @pytest.fixture
    def steel_tile(self):
        t = MagicMock(spec=Tile)
        t.type = TileType.STEEL
        t.blocks_bullets = True
        t.x = 6
        t.y = 6
        t.rect = pygame.Rect(96, 96, 16, 16)
        return t

    def test_power_bullet_destroys_steel(
        self, handler, power_bullet, steel_tile, mock_map
    ):
        handler.process_collisions([(power_bullet, steel_tile)])
        mock_map.set_tile_type.assert_called()
        assert not power_bullet.active

    def test_normal_bullet_blocked_by_steel(
        self, handler, normal_bullet, steel_tile, mock_map
    ):
        handler.process_collisions([(normal_bullet, steel_tile)])
        mock_map.set_tile_type.assert_not_called()
        assert not normal_bullet.active

    def test_power_bullet_destroys_base(self, handler, power_bullet, mock_map):
        """A power bullet destroys the Base the same way a normal bullet does."""
        base_tile = MagicMock(spec=Tile)
        base_tile.type = TileType.BASE
        base_tile.blocks_bullets = True
        base_tile.is_destructible = False
        base_tile.x = 8
        base_tile.y = 14
        base_tile.rect = pygame.Rect(128, 224, 16, 16)
        outcomes = handler.process_collisions([(power_bullet, base_tile)])
        assert not power_bullet.active
        mock_map.destroy_base.assert_called_once()
        assert outcomes == [BaseDestroyed()]


class TestFriendlyFire:
    def test_player_bullet_freezes_other_player(self, handler, make_bullet):
        """Player bullet hitting another player freezes instead of damaging."""
        bullet = make_bullet(owner=MagicMock(spec=PlayerTank))
        target = _make_player()

        outcomes = handler.process_collisions([(bullet, target)])

        assert bullet.active is False
        target.freeze.assert_called_once_with(FRIENDLY_FIRE_FREEZE_DURATION)
        target.take_damage.assert_not_called()
        assert outcomes == []

    def test_player_bullet_does_not_freeze_invincible_player(
        self, handler, make_bullet
    ):
        """Friendly fire on invincible player deactivates bullet but doesn't freeze."""
        bullet = make_bullet()
        target = _make_player()
        target.is_invincible = True

        handler.process_collisions([(bullet, target)])

        assert bullet.active is False
        target.freeze.assert_not_called()

    def test_player_bullet_does_not_hit_self(self, handler, make_bullet):
        """A player's own bullet cannot hit themselves (self-hit guard)."""
        player = _make_player()
        bullet = make_bullet(owner=player)

        handler.process_collisions([(bullet, player)])

        assert bullet.active is True
        player.freeze.assert_not_called()

    def test_enemy_bullet_hits_frozen_player(self, handler, make_bullet):
        """A frozen player can still be hit by enemy bullets (real damage)."""
        bullet = make_bullet(owner_type=OwnerType.ENEMY)
        target = _make_player()
        target.is_frozen = True

        outcomes = handler.process_collisions([(bullet, target)])

        assert outcomes == [PlayerDestroyed(target)]
