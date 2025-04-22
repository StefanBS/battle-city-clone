import pytest
import pygame
from core.tank import Tank
from core.bullet import Bullet
from utils.constants import TILE_SIZE, TANK_SPEED, BULLET_WIDTH, BULLET_HEIGHT


class TestTank:
    """Test cases for the Tank class."""

    @pytest.fixture
    def tank(self):
        """Create a tank instance for testing."""
        pygame.init()
        return Tank(0, 0, TILE_SIZE)

    @pytest.fixture
    def tank_two_lives(self):
        """Create a tank instance with two lives for testing."""
        pygame.init()
        return Tank(0, 0, TILE_SIZE, lives=2)

    @pytest.fixture
    def tank_two_health(self):
        """Create a tank instance with two health for testing."""
        pygame.init()
        return Tank(0, 0, TILE_SIZE, health=2)

    @pytest.mark.parametrize("direction", ["up", "right", "down", "left"])
    def test_shoot_direction(self, tank, direction):
        """Test shooting in different directions."""
        # Set direction and shoot
        tank.direction = direction
        tank.shoot()

        # Verify bullet direction
        assert tank.bullet is not None
        assert tank.bullet.direction == direction

    def test_initialization(self, tank):
        """Test tank initialization."""
        assert tank.x == 0
        assert tank.y == 0
        assert tank.width == TILE_SIZE
        assert tank.height == TILE_SIZE
        assert tank.speed == TANK_SPEED
        assert tank.direction == "up"
        assert tank.bullet is None
        assert tank.health == 1
        assert tank.lives == 1
        assert not tank.is_invincible

    def test_take_damage_survive(self, tank_two_health):
        """Test taking damage without dying."""
        # Take 1 damage, should survive
        assert not tank_two_health.take_damage()
        assert tank_two_health.health == 1
        assert tank_two_health.lives == 1

    def test_take_damage_die(self, tank_two_lives):
        """Test taking damage and dying."""
        # Take 1 damage, should die and lose a life
        assert (
            not tank_two_lives.take_damage()
        )  # Returns False because tank still has lives left
        assert tank_two_lives.health == 1
        assert tank_two_lives.lives == 1

    def test_take_damage_game_over(self, tank):
        """Test taking damage with no lives left."""
        # Take 1 damage, should die and trigger game over
        assert tank.take_damage()  # Returns True because tank has no lives left
        assert tank.health == 0
        assert tank.lives == 0

    def test_invincibility(self, tank):
        """Test invincibility mechanics."""
        # Set invincibility
        tank.is_invincible = True
        tank.invincibility_duration = 3.0

        # Try to take damage while invincible
        assert not tank.take_damage()
        assert tank.health == 1
        assert tank.lives == 1

        # Update with time less than duration
        tank.update(1.0)
        assert tank.is_invincible

        # Update with time more than duration
        tank.update(3.0)
        assert not tank.is_invincible

    def test_shoot(self, tank):
        """Test shooting functionality."""
        # Test shooting
        tank.shoot()
        assert tank.bullet is not None
        assert isinstance(tank.bullet, Bullet)
        assert tank.bullet.active

        # Test bullet position (should be centered on tank)
        expected_x = tank.x + tank.width // 2 - BULLET_WIDTH // 2
        expected_y = tank.y + tank.height // 2 - BULLET_HEIGHT // 2
        assert tank.bullet.x == expected_x
        assert tank.bullet.y == expected_y

    def test_move(self, tank):
        """Test movement attempt functionality."""
        # First move attempt should fail due to move_timer
        assert not tank._move(1, 0)
        assert tank.x == 0
        assert tank.y == 0

        # Advance the move_timer past the delay
        tank.move_timer = tank.move_delay

        # Store previous position before moving
        tank.prev_x = tank.x
        tank.prev_y = tank.y

        # Now movement attempt should succeed
        assert tank._move(1, 0)
        assert tank.x == TILE_SIZE
        assert tank.y == 0

        # Reset timer for next move
        tank.move_timer = tank.move_delay
        tank.prev_x = tank.x
        tank.prev_y = tank.y

        # Test moving down
        assert tank._move(0, 1)
        assert tank.x == TILE_SIZE
        assert tank.y == TILE_SIZE

    def test_move_edge_cases(self, tank):
        """Test edge cases for movement attempts."""
        tank.move_timer = tank.move_delay

        # Test moving with zero delta
        # Zero movement attempt should succeed but not change position
        tank.prev_x = tank.x
        tank.prev_y = tank.y
        assert tank._move(0, 0)
        assert tank.x == 0
        assert tank.y == 0

        # Test moving diagonally (should return False)
        tank.prev_x = tank.x
        tank.prev_y = tank.y
        assert not tank._move(1, 1)
        # Position should not change after failed diagonal attempt
        assert tank.x == 0
        assert tank.y == 0

    def test_revert_move(self, tank):
        """Test the revert_move functionality."""
        initial_x, initial_y = tank.x, tank.y
        tank.prev_x = initial_x
        tank.prev_y = initial_y

        # Simulate a move
        tank.x = initial_x + TILE_SIZE
        tank.y = initial_y
        tank.rect.topleft = (tank.x, tank.y)

        # Revert the move
        tank.revert_move()

        # Assert position is back to the stored previous position
        assert tank.x == initial_x
        assert tank.y == initial_y
        assert tank.rect.topleft == (initial_x, initial_y)
