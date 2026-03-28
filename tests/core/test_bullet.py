import pytest
import pygame
from src.core.bullet import Bullet
from src.utils.constants import (
    Direction,
    BULLET_SPEED,
    FPS,
    BULLET_WIDTH,
    BULLET_HEIGHT,
)


class TestBullet:
    """Unit test cases for the Bullet class."""

    @pytest.fixture
    def bullet(self):
        """Create a bullet instance for testing."""
        pygame.init()
        return Bullet(0, 0, Direction.UP, owner_type="test")

    def test_initialization(self, bullet):
        """Test bullet initialization."""
        assert bullet.x == 0
        assert bullet.y == 0
        assert bullet.direction == Direction.UP
        assert bullet.speed == BULLET_SPEED * FPS
        assert bullet.active
        assert bullet.owner_type == "test"
        assert bullet.width == BULLET_WIDTH
        assert bullet.height == BULLET_HEIGHT

    @pytest.mark.parametrize(
        "direction,expected_x,expected_y",
        [
            (Direction.UP, 0, -(BULLET_SPEED * FPS)),
            (Direction.DOWN, 0, BULLET_SPEED * FPS),
            (Direction.LEFT, -(BULLET_SPEED * FPS), 0),
            (Direction.RIGHT, BULLET_SPEED * FPS, 0),
        ],
    )
    def test_update(self, bullet, direction, expected_x, expected_y):
        """Test bullet movement in all directions."""
        # Reset bullet position
        bullet.direction = direction
        # Update bullet position
        bullet.update(1.0)
        # Verify movement
        assert bullet.x == expected_x
        assert bullet.y == expected_y

    def test_out_of_bounds(self, bullet):
        """Test bullet deactivation when out of bounds."""
        # Move bullet far out of bounds
        bullet.x = -1000
        bullet.y = -1000
        bullet.update(1.0)
        assert not bullet.active  # Bullet should be deactivated when out of bounds
