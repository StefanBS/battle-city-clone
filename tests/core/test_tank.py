import pytest
import pygame
from src.core.tank import Tank
from src.core.bullet import Bullet
from src.utils.constants import (
    Direction,
    OwnerType,
    TILE_SIZE,
    TANK_SPEED,
    BULLET_WIDTH,
    BULLET_HEIGHT,
    FPS,
)

MAP_WIDTH_PX = 16 * TILE_SIZE
MAP_HEIGHT_PX = 16 * TILE_SIZE


class TestTank:
    """Test cases for the Tank class."""

    @pytest.fixture
    def tank(self, mock_texture_manager):
        """Create a tank instance for testing."""
        return Tank(
            0, 0, mock_texture_manager, tile_size=TILE_SIZE,
            owner_type=OwnerType.PLAYER,
            map_width_px=MAP_WIDTH_PX, map_height_px=MAP_HEIGHT_PX,
        )

    @pytest.fixture
    def tank_two_lives(self, mock_texture_manager):
        """Create a tank instance with two lives for testing."""
        return Tank(
            0, 0, mock_texture_manager, tile_size=TILE_SIZE, lives=2,
            owner_type=OwnerType.PLAYER,
            map_width_px=MAP_WIDTH_PX, map_height_px=MAP_HEIGHT_PX,
        )

    @pytest.fixture
    def tank_two_health(self, mock_texture_manager):
        """Create a tank instance with two health for testing."""
        return Tank(
            0, 0, mock_texture_manager, tile_size=TILE_SIZE, health=2,
            owner_type=OwnerType.PLAYER,
            map_width_px=MAP_WIDTH_PX, map_height_px=MAP_HEIGHT_PX,
        )

    @pytest.mark.parametrize(
        "direction",
        [Direction.UP, Direction.RIGHT, Direction.DOWN, Direction.LEFT],
    )
    def test_shoot_direction(self, tank, direction):
        """Test shooting in different directions."""
        tank.direction = direction
        bullet = tank.shoot()

        assert bullet is not None
        assert bullet.direction == direction

    def test_initialization(self, tank):
        """Test tank initialization."""
        assert tank.x == 0
        assert tank.y == 0
        assert tank.width == TILE_SIZE
        assert tank.height == TILE_SIZE
        assert tank.speed == TANK_SPEED
        assert tank.direction == Direction.UP
        assert not hasattr(tank, "bullet")
        assert tank.max_bullets == 1
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
        bullet = tank.shoot()
        assert bullet is not None
        assert isinstance(bullet, Bullet)
        assert bullet.active

        expected_x = tank.x + tank.width // 2 - BULLET_WIDTH // 2
        expected_y = tank.y + tank.height // 2 - BULLET_HEIGHT // 2
        assert bullet.x == expected_x
        assert bullet.y == expected_y

        assert bullet.owner is tank
        assert bullet.owner_type == tank.owner_type

    def test_move(self, tank):
        """Test continuous movement functionality."""
        dt = 1.0 / FPS

        # Store previous position before moving
        tank.prev_x = tank.x
        tank.prev_y = tank.y

        # Movement should succeed immediately (no timer gating)
        assert tank._move(1, 0, dt)
        assert tank.x == pytest.approx(TANK_SPEED * dt)
        assert tank.y == 0

        # Move again without any timer reset needed
        tank.prev_x = tank.x
        tank.prev_y = tank.y
        assert tank._move(0, 1, dt)
        assert tank.x == pytest.approx(TANK_SPEED * dt)
        assert tank.y == pytest.approx(TANK_SPEED * dt)

    def test_move_edge_cases(self, tank):
        """Test edge cases for movement attempts."""
        dt = 1.0 / FPS

        # Test moving with zero delta — should return False and not change state
        tank.prev_x = tank.x
        tank.prev_y = tank.y
        initial_frame = tank.animation_frame
        assert not tank._move(0, 0, dt)
        assert tank.x == 0
        assert tank.y == 0
        assert tank.animation_frame == initial_frame

        # Test moving diagonally (should return False)
        tank.prev_x = tank.x
        tank.prev_y = tank.y
        assert not tank._move(1, 1, dt)
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

    def test_revert_move_clamps_to_map_bounds(self, tank):
        """Test that revert_move clamps position within map bounds."""
        map_width = MAP_WIDTH_PX
        map_height = MAP_HEIGHT_PX

        # Simulate tank moving left at left edge — obstacle snaps to negative x
        tank.direction = Direction.LEFT
        tank.x = 5.0
        tank.y = 100.0
        # right edge = -8, produces negative snap
        obstacle = pygame.Rect(-40, 100, 32, 32)
        tank.revert_move(obstacle)
        assert tank.x >= 0, f"Tank x={tank.x} should be >= 0"

        # Simulate tank moving up at top edge — obstacle snaps to negative y
        tank.direction = Direction.UP
        tank.x = 100.0
        tank.y = 5.0
        # bottom edge = -8, produces negative snap
        obstacle = pygame.Rect(100, -40, 32, 32)
        tank.revert_move(obstacle)
        assert tank.y >= 0, f"Tank y={tank.y} should be >= 0"

        # Simulate tank moving right at right edge — obstacle snaps past right bound
        tank.direction = Direction.RIGHT
        tank.x = map_width - 10
        tank.y = 100.0
        obstacle = pygame.Rect(map_width + 10, 100, 32, 32)
        tank.revert_move(obstacle)
        assert tank.x <= map_width - tank.width, (
            f"Tank x={tank.x} should be <= {map_width - tank.width}"
        )

        # Simulate tank moving down at bottom edge — obstacle snaps past bottom bound
        tank.direction = Direction.DOWN
        tank.x = 100.0
        tank.y = map_height - 10
        obstacle = pygame.Rect(100, map_height + 10, 32, 32)
        tank.revert_move(obstacle)
        assert tank.y <= map_height - tank.height, (
            f"Tank y={tank.y} should be <= {map_height - tank.height}"
        )

    def test_update_stores_previous_position(self, tank):
        """Test that update() stores current position as prev before any movement."""
        tank.x = 100.0
        tank.y = 200.0
        tank.update(1.0 / FPS)
        assert tank.prev_x == 100.0
        assert tank.prev_y == 200.0

    def test_shoot_forwards_bullet_speed(self, mock_texture_manager):
        """Test that shoot() creates a bullet with the tank's bullet_speed."""
        custom_speed = 999.0
        tank = Tank(
            0, 0, mock_texture_manager, tile_size=TILE_SIZE,
            bullet_speed=custom_speed,
            owner_type=OwnerType.PLAYER,
            map_width_px=512, map_height_px=512,
        )
        bullet = tank.shoot()
        assert bullet.speed == custom_speed
