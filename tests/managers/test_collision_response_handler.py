import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.collision_response_handler import CollisionResponseHandler
from src.core.bullet import Bullet
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType
from src.core.map import Map
from src.utils.constants import TILE_SIZE


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
