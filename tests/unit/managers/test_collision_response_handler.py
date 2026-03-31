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
from src.utils.constants import Direction, TILE_SIZE


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
    return e


@pytest.fixture
def mock_player():
    p = MagicMock(spec=PlayerTank)
    p.owner_type = "player"
    p.is_invincible = False
    p.take_damage = MagicMock(return_value=False)
    p.respawn = MagicMock()
    p.revert_move = MagicMock()
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
    def test_bullet_destroys_brick_and_horizontal_sibling(self, handler, mock_map):
        """Bullet moving UP destroys hit tile and horizontal sibling."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.direction = Direction.UP
        tile = MagicMock(spec=Tile)
        tile.type = TileType.BRICK
        tile.x, tile.y = 4, 5
        sibling = MagicMock(spec=Tile)
        sibling.type = TileType.BRICK
        mock_map.get_tile_at.return_value = sibling

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        # Should destroy both the hit tile and its horizontal sibling
        mock_map.set_tile_type.assert_any_call(tile, TileType.EMPTY)
        mock_map.get_tile_at.assert_called_with(5, 5)  # x^1 = 5
        mock_map.set_tile_type.assert_any_call(sibling, TileType.EMPTY)

    def test_bullet_destroys_brick_and_vertical_sibling(self, handler, mock_map):
        """Bullet moving LEFT destroys hit tile and vertical sibling."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.direction = Direction.LEFT
        tile = MagicMock(spec=Tile)
        tile.type = TileType.BRICK
        tile.x, tile.y = 4, 4
        sibling = MagicMock(spec=Tile)
        sibling.type = TileType.BRICK
        mock_map.get_tile_at.return_value = sibling

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        mock_map.set_tile_type.assert_any_call(tile, TileType.EMPTY)
        mock_map.get_tile_at.assert_called_with(4, 5)  # y^1 = 5
        mock_map.set_tile_type.assert_any_call(sibling, TileType.EMPTY)

    def test_bullet_destroys_brick_sibling_already_gone(self, handler, mock_map):
        """If sibling is already EMPTY, only the hit tile is destroyed."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.direction = Direction.UP
        tile = MagicMock(spec=Tile)
        tile.type = TileType.BRICK
        tile.x, tile.y = 4, 5
        sibling = MagicMock(spec=Tile)
        sibling.type = TileType.EMPTY
        mock_map.get_tile_at.return_value = sibling

        handler.process_collisions([(bullet, tile)])

        assert not bullet.active
        mock_map.set_tile_type.assert_called_once_with(tile, TileType.EMPTY)

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
    def test_both_reverted(self, handler, mock_player, mock_enemy):
        handler.process_collisions([(mock_player, mock_enemy)])
        mock_player.revert_move.assert_called_once()
        mock_enemy.revert_move.assert_called_once()

    def test_enemy_vs_enemy_reverted(self, handler):
        """Test that two enemy tanks both get reverted on collision."""
        enemy1 = MagicMock(spec=EnemyTank)
        enemy1.owner_type = "enemy"
        enemy1.revert_move = MagicMock()
        enemy2 = MagicMock(spec=EnemyTank)
        enemy2.owner_type = "enemy"
        enemy2.revert_move = MagicMock()
        handler.process_collisions([(enemy1, enemy2)])
        enemy1.revert_move.assert_called_once()
        enemy2.revert_move.assert_called_once()


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
