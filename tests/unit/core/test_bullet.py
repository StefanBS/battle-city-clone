import pytest
import pygame
from unittest.mock import MagicMock, patch
from src.core.bullet import Bullet
from src.utils.constants import (
    Direction,
    BULLET_SPEED,
    BULLET_WIDTH,
    BULLET_HEIGHT,
    TILE_SIZE,
)


class TestBullet:
    """Unit test cases for the Bullet class."""

    @pytest.fixture
    def bullet(self):
        """Create a bullet instance for testing."""
        pygame.init()
        mock_owner = MagicMock()
        mock_owner.owner_type = "test"
        mock_owner.map_width_px = 16 * TILE_SIZE
        mock_owner.map_height_px = 16 * TILE_SIZE
        return Bullet(0, 0, Direction.UP, owner=mock_owner)

    def test_initialization(self, bullet):
        """Test bullet initialization."""
        assert bullet.x == 0
        assert bullet.y == 0
        assert bullet.direction == Direction.UP
        assert bullet.speed == BULLET_SPEED
        assert bullet.active
        assert bullet.owner.owner_type == "test"
        assert bullet.owner_type == "test"
        assert bullet.width == BULLET_WIDTH
        assert bullet.height == BULLET_HEIGHT

    @pytest.mark.parametrize(
        "direction,expected_x,expected_y",
        [
            (Direction.UP, 0, -BULLET_SPEED),
            (Direction.DOWN, 0, BULLET_SPEED),
            (Direction.LEFT, -BULLET_SPEED, 0),
            (Direction.RIGHT, BULLET_SPEED, 0),
        ],
    )
    def test_update(self, bullet, direction, expected_x, expected_y):
        """Test bullet movement in all directions."""
        bullet.direction = direction
        bullet.update(1.0)
        assert bullet.x == expected_x
        assert bullet.y == expected_y

    def test_update_inactive_bullet_does_not_move(self, bullet):
        """Test that an inactive bullet does not move on update."""
        bullet.active = False
        bullet.x = 100.0
        bullet.y = 100.0
        bullet.update(1.0)
        assert bullet.x == 100.0
        assert bullet.y == 100.0

    def test_out_of_bounds(self, bullet):
        """Test bullet deactivation when out of bounds."""
        bullet.x = -1000
        bullet.y = -1000
        bullet.update(1.0)
        assert not bullet.active

    def test_draw_active_with_sprite(self, bullet):
        """Test that active bullet with sprite blits to surface."""
        mock_surface = MagicMock(spec=pygame.Surface)
        mock_sprite = MagicMock(spec=pygame.Surface)
        bullet.sprite = mock_sprite
        bullet.active = True
        bullet.draw(mock_surface)
        mock_surface.blit.assert_called_once_with(mock_sprite, bullet.rect)

    def test_draw_active_without_sprite(self, bullet):
        """Test that active bullet without sprite draws colored rect."""
        mock_surface = MagicMock(spec=pygame.Surface)
        bullet.sprite = None
        bullet.active = True
        with patch("pygame.draw.rect") as mock_draw:
            bullet.draw(mock_surface)
        mock_draw.assert_called_once_with(mock_surface, bullet.color, bullet.rect)

    def test_draw_inactive_does_nothing(self, bullet):
        """Test that inactive bullet does not draw."""
        mock_surface = MagicMock(spec=pygame.Surface)
        bullet.active = False
        bullet.draw(mock_surface)
        mock_surface.blit.assert_not_called()
