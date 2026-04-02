import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.collision_response_handler import CollisionResponseHandler
from src.core.bullet import Bullet
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType
from src.core.map import Map
from src.states.game_state import GameState
from src.utils.constants import (
    Direction,
    TILE_SIZE,
    SEGMENT_LEFT,
    SEGMENT_RIGHT,
    SEGMENT_TOP,
    SEGMENT_BOTTOM,
)


@pytest.fixture
def mock_map():
    mock = MagicMock(spec=Map)
    mock.set_tile_type = MagicMock()
    return mock


@pytest.fixture
def handler(mock_map):
    set_state = MagicMock()
    return CollisionResponseHandler(game_map=mock_map, set_game_state=set_state)


@pytest.fixture
def mock_bullet():
    b = MagicMock(spec=Bullet)
    b.active = True
    b.owner_type = "player"
    b.owner = MagicMock()
    return b


@pytest.fixture
def mock_enemy():
    e = MagicMock(spec=EnemyTank)
    e.owner_type = "enemy"
    e.tank_type = "basic"
    e.take_damage = MagicMock(return_value=False)
    e.on_wall_hit = MagicMock()
    e.revert_move = MagicMock()
    e.x = 100.0
    e.y = 100.0
    e.prev_x = 100.0
    e.prev_y = 100.0
    e.width = TILE_SIZE
    e.height = TILE_SIZE
    e.direction = Direction.DOWN
    return e


@pytest.fixture
def mock_player():
    p = MagicMock(spec=PlayerTank)
    p.owner_type = "player"
    p.is_invincible = False
    p.take_damage = MagicMock(return_value=False)
    p.respawn = MagicMock()
    p.revert_move = MagicMock()
    p.x = 100.0
    p.y = 200.0
    p.prev_x = 100.0
    p.prev_y = 200.0
    p.width = TILE_SIZE
    p.height = TILE_SIZE
    p.direction = Direction.UP
    return p


@pytest.fixture
def mock_tile():
    t = MagicMock(spec=Tile)
    t.type = TileType.BRICK
    t.x = 0
    t.y = 0
    t.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
    return t


class TestDispatch:
    def test_lookup_forward_order(self, handler, mock_bullet, mock_enemy):
        """Test registry finds handler with (Bullet, EnemyTank) order."""
        mock_bullet.owner_type = "player"
        handler.process_collisions([(mock_bullet, mock_enemy)])
        assert not mock_bullet.active

    def test_lookup_swapped_order(self, handler, mock_bullet, mock_enemy):
        """Test registry finds handler with (EnemyTank, Bullet) order."""
        mock_bullet.owner_type = "player"
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
        mock_bullet.owner_type = "player"
        handler.process_collisions([(mock_bullet, mock_enemy)])
        assert not mock_bullet.active
        mock_enemy.take_damage.assert_called_once()

    def test_player_bullet_destroys_enemy(self, handler, mock_bullet, mock_enemy):
        mock_bullet.owner_type = "player"
        mock_enemy.take_damage.return_value = True
        enemies = handler.process_collisions([(mock_bullet, mock_enemy)])
        assert mock_enemy in enemies

    def test_enemy_bullet_does_not_damage_enemy(self, handler, mock_enemy):
        """Friendly fire — enemy bullet should not damage enemy."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        handler.process_collisions([(bullet, mock_enemy)])
        mock_enemy.take_damage.assert_not_called()
        assert bullet.active  # Bullet not consumed


class TestBulletVsPlayer:
    def test_enemy_bullet_damages_player(self, handler, mock_player):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        handler.process_collisions([(bullet, mock_player)])
        assert not bullet.active
        mock_player.take_damage.assert_called_once()
        mock_player.respawn.assert_called_once()

    def test_enemy_bullet_kills_player(self, handler, mock_player):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        mock_player.take_damage.return_value = True
        handler.process_collisions([(bullet, mock_player)])
        handler._set_game_state.assert_called_with(GameState.GAME_OVER)
        mock_player.respawn.assert_not_called()

    def test_bullet_vs_invincible_player(self, handler, mock_player):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        mock_player.is_invincible = True
        handler.process_collisions([(bullet, mock_player)])
        assert not bullet.active
        mock_player.take_damage.assert_not_called()

    def test_player_bullet_does_not_damage_player(self, handler, mock_player):
        """Friendly fire — player bullet should not damage player."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "player"
        bullet.owner = MagicMock()
        handler.process_collisions([(bullet, mock_player)])
        mock_player.take_damage.assert_not_called()
        assert bullet.active


class TestBulletVsTile:
    """Brick quadrant destruction tests (4x4 segment model).

    Each 32x32 brick = 4 sub-tiles (16x16, 2x2 grid).
    Each sub-tile has 4 quadrants (8x8, 2x2 grid) = 16 segments total.

    Sub-tile at grid (4,4) has pixel rect (64,64,16,16).
    Quadrants: TL=(64,64,8,8) TR=(72,64,8,8) BL=(64,72,8,8) BR=(72,72,8,8).
    """

    @staticmethod
    def _bullet(direction, px_x, px_y):
        """Create a mock bullet with a real rect at given pixel coords."""
        b = MagicMock(spec=Bullet)
        b.active = True
        b.owner = MagicMock()
        b.direction = direction
        b.rect = pygame.Rect(px_x, px_y, 2, 2)
        return b

    # -- Horizontal bullets (LEFT / RIGHT) --

    def test_right_bullet_destroys_entry_column(self, handler, mock_map):
        """RIGHT bullet destroys full left column (TL+BL) of sub-tile."""
        tile = Tile(TileType.BRICK, 4, 4)
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 4, 5)
        bullet = self._bullet(Direction.RIGHT, 64, 66)

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        assert tile.brick_segments == SEGMENT_RIGHT

    def test_left_bullet_destroys_entry_column(self, handler, mock_map):
        """LEFT bullet destroys full right column (TR+BR) of sub-tile."""
        tile = Tile(TileType.BRICK, 4, 4)
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 4, 5)
        bullet = self._bullet(Direction.LEFT, 72, 66)

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        assert tile.brick_segments == SEGMENT_LEFT

    def test_right_bullet_center_destroys_both_subtiles(self, handler, mock_map):
        """RIGHT bullet at row boundary → left column of both sub-tiles."""
        tile = Tile(TileType.BRICK, 4, 4)
        sibling = Tile(TileType.BRICK, 4, 5)
        mock_map.get_tile_at.return_value = sibling
        # Bullet straddles y=80 boundary
        bullet = self._bullet(Direction.RIGHT, 64, 79)

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        assert tile.brick_segments == SEGMENT_RIGHT
        assert sibling.brick_segments == SEGMENT_RIGHT

    def test_horizontal_bullet_sibling_already_gone(self, handler, mock_map):
        """If vertical sibling is EMPTY, only hit sub-tile loses entry column."""
        tile = Tile(TileType.BRICK, 4, 4)
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 4, 5)
        bullet = self._bullet(Direction.RIGHT, 64, 79)

        handler.process_collisions([(bullet, tile)])

        assert tile.brick_segments == SEGMENT_RIGHT

    def test_horizontal_bullet_entry_gone_passes_through(self, handler, mock_map):
        """If entry column is gone, bullet destroys remaining column."""
        tile = Tile(TileType.BRICK, 4, 4)
        tile.remove_brick_segment(SEGMENT_LEFT)  # left column destroyed
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 4, 5)
        bullet = self._bullet(Direction.RIGHT, 72, 66)

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        assert tile.brick_segments == 0
        mock_map.set_tile_type.assert_called_once_with(tile, TileType.EMPTY)

    # -- Vertical bullets (UP / DOWN) --

    def test_down_bullet_destroys_entry_row(self, handler, mock_map):
        """DOWN bullet destroys full top row (TL+TR) of sub-tile."""
        tile = Tile(TileType.BRICK, 4, 4)
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 5, 4)
        bullet = self._bullet(Direction.DOWN, 66, 64)

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        assert tile.brick_segments == SEGMENT_BOTTOM

    def test_up_bullet_destroys_entry_row(self, handler, mock_map):
        """UP bullet destroys full bottom row (BL+BR) of sub-tile."""
        tile = Tile(TileType.BRICK, 4, 4)
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 5, 4)
        bullet = self._bullet(Direction.UP, 66, 74)

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        assert tile.brick_segments == SEGMENT_TOP

    def test_down_bullet_center_destroys_both_subtiles(self, handler, mock_map):
        """DOWN bullet at column boundary → top row of both sub-tiles."""
        tile = Tile(TileType.BRICK, 4, 4)
        sibling = Tile(TileType.BRICK, 5, 4)
        mock_map.get_tile_at.return_value = sibling
        # Bullet straddles x=80 boundary
        bullet = self._bullet(Direction.DOWN, 79, 64)

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        assert tile.brick_segments == SEGMENT_BOTTOM
        assert sibling.brick_segments == SEGMENT_BOTTOM

    def test_vertical_bullet_sibling_already_gone(self, handler, mock_map):
        """If horizontal sibling is EMPTY, only hit sub-tile loses entry row."""
        tile = Tile(TileType.BRICK, 4, 4)
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 5, 4)
        bullet = self._bullet(Direction.DOWN, 66, 64)

        handler.process_collisions([(bullet, tile)])

        assert tile.brick_segments == SEGMENT_BOTTOM

    def test_vertical_bullet_entry_gone_passes_through(self, handler, mock_map):
        """If entry row is gone, bullet destroys remaining row."""
        tile = Tile(TileType.BRICK, 4, 4)
        tile.remove_brick_segment(SEGMENT_TOP)  # top row destroyed
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 5, 4)
        bullet = self._bullet(Direction.DOWN, 66, 72)

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        assert tile.brick_segments == 0
        mock_map.set_tile_type.assert_called_once_with(tile, TileType.EMPTY)

    # -- Non-brick tiles --

    def test_bullet_stops_at_steel(self, handler, mock_map):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        tile = MagicMock(spec=Tile)
        tile.type = TileType.STEEL
        tile.x, tile.y = 0, 0
        handler.process_collisions([(bullet, tile)])
        assert not bullet.active
        mock_map.set_tile_type.assert_not_called()

    def test_bullet_destroys_base(self, handler, mock_map):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        tile = MagicMock(spec=Tile)
        tile.type = TileType.BASE
        tile.x, tile.y = 0, 0
        handler.process_collisions([(bullet, tile)])
        assert not bullet.active
        mock_map.destroy_base_group.assert_called_with(tile)
        handler._set_game_state.assert_called_with(GameState.GAME_OVER)


class TestBulletVsBullet:
    def test_both_deactivated(self, handler):
        b1 = MagicMock(spec=Bullet)
        b2 = MagicMock(spec=Bullet)
        b1.active = True
        b1.owner = MagicMock()
        b2.active = True
        b2.owner = MagicMock()
        handler.process_collisions([(b1, b2)])
        assert not b1.active
        assert not b2.active


class TestTankVsTank:
    @staticmethod
    def _make_tank(spec_class, owner_type, x, y, prev_x, prev_y):
        """Create a mock tank with position and rect in sync."""
        t = MagicMock(spec=spec_class)
        t.owner_type = owner_type
        t.x, t.y = x, y
        t.prev_x, t.prev_y = prev_x, prev_y
        t.width = t.height = TILE_SIZE
        t.rect = pygame.Rect(round(x), round(y), TILE_SIZE, TILE_SIZE)
        return t

    def test_both_moving_toward_each_other(self, handler):
        """Both tanks moving toward each other: both reverted."""
        a = self._make_tank(PlayerTank, "player", 100, 130, 100, 134)
        b = self._make_tank(EnemyTank, "enemy", 100, 100, 100, 96)
        handler.process_collisions([(a, b)])
        a.revert_move.assert_called_once()
        b.revert_move.assert_called_once()
        a.on_wall_hit.assert_called_once()
        b.on_wall_hit.assert_called_once()

    def test_only_aggressor_gets_wall_hit(self, handler):
        """Only the tank that moved into the other gets on_wall_hit."""
        player = self._make_tank(PlayerTank, "player", 100, 130, 100, 134)
        enemy = self._make_tank(EnemyTank, "enemy", 100, 100, 100, 100)
        handler.process_collisions([(player, enemy)])
        player.revert_move.assert_called_once()
        enemy.revert_move.assert_not_called()
        player.on_wall_hit.assert_called_once()
        enemy.on_wall_hit.assert_not_called()

    def test_perpendicular_tank_not_reverted(self, handler):
        """Enemy moving perpendicular to collision axis is not reverted."""
        player = self._make_tank(PlayerTank, "player", 100, 130, 100, 134)
        enemy = self._make_tank(EnemyTank, "enemy", 100, 100, 98, 100)
        handler.process_collisions([(player, enemy)])
        player.revert_move.assert_called_once()
        enemy.revert_move.assert_not_called()
        player.on_wall_hit.assert_called_once()
        enemy.on_wall_hit.assert_not_called()

    def test_enemy_vs_enemy_both_moving_toward(self, handler):
        """Two enemies moving toward each other: both reverted."""
        e1 = self._make_tank(EnemyTank, "enemy", 100, 100, 96, 100)
        e2 = self._make_tank(EnemyTank, "enemy", 130, 100, 134, 100)
        handler.process_collisions([(e1, e2)])
        e1.revert_move.assert_called_once()
        e2.revert_move.assert_called_once()
        e1.on_wall_hit.assert_called_once()
        e2.on_wall_hit.assert_called_once()

    def test_pre_existing_overlap_reverts_and_notifies_both(self, handler):
        """When tanks are already overlapping (neither caused it),
        both should be reverted and notified so they can escape."""
        # Both at same position, neither moved
        e1 = self._make_tank(EnemyTank, "enemy", 100, 100, 100, 100)
        e2 = self._make_tank(EnemyTank, "enemy", 100, 100, 100, 100)
        handler.process_collisions([(e1, e2)])
        e1.revert_move.assert_called_once()
        e2.revert_move.assert_called_once()
        e1.on_wall_hit.assert_called_once()
        e2.on_wall_hit.assert_called_once()

    def test_cornered_tank_not_notified_twice(self, handler, mock_tile):
        """A tank already reverted by a tile collision should not get
        on_wall_hit again from a subsequent tank-vs-tank collision."""
        mock_tile.type = TileType.STEEL
        # Enemy cornered against a wall, pusher coming from the side
        enemy = self._make_tank(EnemyTank, "enemy", 100, 100, 100, 100)
        pusher = self._make_tank(PlayerTank, "player", 130, 100, 134, 100)
        # Tile collision first, then tank-vs-tank in the same frame
        handler.process_collisions([
            (enemy, mock_tile),
            (pusher, enemy),
        ])
        # Enemy gets on_wall_hit once (from the tile), not twice
        enemy.on_wall_hit.assert_called_once()
        # Pusher gets reverted and notified from the tank-vs-tank
        pusher.revert_move.assert_called_once()


class TestTankVsTile:
    def test_player_reverted_on_impassable(self, handler, mock_player, mock_tile):
        mock_tile.type = TileType.STEEL
        handler.process_collisions([(mock_player, mock_tile)])
        mock_player.revert_move.assert_called_once_with(mock_tile.rect)

    def test_enemy_reverted_and_wall_hit(self, handler, mock_enemy, mock_tile):
        mock_tile.type = TileType.STEEL
        handler.process_collisions([(mock_enemy, mock_tile)])
        mock_enemy.revert_move.assert_called_once_with(mock_tile.rect)
        mock_enemy.on_wall_hit.assert_called_once()


class TestTracking:
    def test_processed_bullet_not_reprocessed(self, handler, mock_enemy):
        """Same bullet in two events should only be processed once."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "player"
        bullet.owner = MagicMock()
        enemy2 = MagicMock(spec=EnemyTank)
        enemy2.take_damage = MagicMock(return_value=False)
        enemy2.owner_type = "enemy"
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
        tile1.x, tile1.y = 0, 0
        tile1.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        tile2 = MagicMock(spec=Tile)
        tile2.type = TileType.BRICK
        tile2.x, tile2.y = 32, 0
        tile2.rect = pygame.Rect(32, 0, TILE_SIZE, TILE_SIZE)
        handler.process_collisions(
            [
                (mock_player, tile1),
                (mock_player, tile2),
            ]
        )
        mock_player.revert_move.assert_called_once()
