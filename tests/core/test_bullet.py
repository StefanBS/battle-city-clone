import pytest
import pygame
from src.core.bullet import Bullet
from utils.constants import TILE_SIZE, BULLET_SPEED


class TestBullet:
    """Test cases for the Bullet class."""

    @pytest.fixture
    def bullet(self):
        """Create a bullet instance for testing."""
        pygame.init()
        return Bullet(0, 0, "up", TILE_SIZE)

    def test_initialization(self, bullet):
        """Test bullet initialization."""
        assert bullet.x == 0
        assert bullet.y == 0
        assert bullet.direction == "up"
        assert bullet.speed == BULLET_SPEED
        assert bullet.active
        assert bullet.width == TILE_SIZE // 4
        assert bullet.height == TILE_SIZE // 4

    def test_update(self, bullet):
        """Test bullet movement."""
        # Test moving up
        bullet.update([])  # Empty list for no collisions
        assert bullet.y == -BULLET_SPEED

        # Test moving right
        bullet.direction = "right"
        bullet.x = 0
        bullet.y = 0
        bullet.update([])
        assert bullet.x == BULLET_SPEED

    def test_collision(self, bullet):
        """Test bullet collision."""
        # Create a wall rect that would cause collision
        wall_rect = pygame.Rect(0, -BULLET_SPEED, TILE_SIZE, TILE_SIZE)
        map_rects = [wall_rect]

        # Test collision with wall
        bullet.update(map_rects)
        assert not bullet.active  # Bullet should be deactivated after collision

    def test_out_of_bounds(self, bullet):
        """Test bullet deactivation when out of bounds."""
        # Move bullet far out of bounds
        bullet.x = -1000
        bullet.y = -1000
        bullet.update([])
        assert not bullet.active  # Bullet should be deactivated when out of bounds
