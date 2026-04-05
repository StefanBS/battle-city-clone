import pytest
import pygame
from src.core.bullet import Bullet
from src.utils.constants import (
    Direction,
    TILE_SIZE,
    SUB_TILE_SIZE,
    TANK_SPEED,
    TANK_ALIGN_THRESHOLD,
    BULLET_WIDTH,
    BULLET_HEIGHT,
    FPS,
    ICE_SLIDE_DISTANCE,
)

MAP_WIDTH_PX = 16 * TILE_SIZE
MAP_HEIGHT_PX = 16 * TILE_SIZE


class TestTank:
    """Test cases for the Tank class."""

    @pytest.fixture
    def tank(self, create_tank):
        """Create a tank instance for testing."""
        return create_tank()

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

    @pytest.mark.parametrize(
        "health,lives,expected_destroyed,post_health,post_lives",
        [
            (2, 1, False, 1, 1),
            (1, 2, False, 1, 1),
            (1, 1, True, 0, 0),
        ],
        ids=["survive", "lose_life", "game_over"],
    )
    def test_take_damage(
        self,
        create_tank,
        health,
        lives,
        expected_destroyed,
        post_health,
        post_lives,
    ):
        """Test taking damage with various health/lives configurations."""
        tank = create_tank(health=health, lives=lives)
        assert tank.take_damage() == expected_destroyed
        assert tank.health == post_health
        assert tank.lives == post_lives

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
        # Steering assist nudges x toward nearest grid line (0) when moving vertically
        tank.prev_x = tank.x
        tank.prev_y = tank.y
        assert tank._move(0, 1, dt)
        assert tank.x == pytest.approx(0.0)
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

    @staticmethod
    def _offset_tank(tank, x=None, y=None):
        """Set tank position after init (bypasses constructor grid snap)."""
        if x is not None:
            tank.x = float(x)
        if y is not None:
            tank.y = float(y)
        tank.rect.topleft = (round(tank.x), round(tank.y))

    def test_steering_assist_nudges_within_threshold(self, create_tank):
        """Moving horizontally nudges Y toward nearest grid line."""
        tank = create_tank(x=0, y=0)
        self._offset_tank(tank, y=SUB_TILE_SIZE + 3)
        dt = 1.0 / FPS
        tank._move(1, 0, dt)
        assert tank.y < SUB_TILE_SIZE + 3

    def test_steering_assist_snaps_when_close(self, create_tank):
        """Small offset snaps exactly to grid in one frame."""
        tank = create_tank(x=0, y=0)
        self._offset_tank(tank, y=SUB_TILE_SIZE + 1)
        dt = 1.0 / FPS
        tank._move(1, 0, dt)
        assert tank.y == pytest.approx(float(SUB_TILE_SIZE))

    def test_steering_assist_ignores_beyond_threshold(self, create_tank):
        """Offset beyond threshold is not corrected."""
        tank = create_tank(x=0, y=0)
        offset = TANK_ALIGN_THRESHOLD + 1
        self._offset_tank(tank, y=SUB_TILE_SIZE + offset)
        dt = 1.0 / FPS
        tank._move(1, 0, dt)
        assert tank.y == pytest.approx(SUB_TILE_SIZE + offset)

    def test_steering_assist_vertical_nudges_x(self, create_tank):
        """Moving vertically nudges X toward nearest grid line."""
        tank = create_tank(x=0, y=0)
        self._offset_tank(tank, x=SUB_TILE_SIZE + 2)
        dt = 1.0 / FPS
        tank._move(0, 1, dt)
        # X should move toward SUB_TILE_SIZE but may not arrive in one frame
        assert tank.x < SUB_TILE_SIZE + 2

    @pytest.mark.parametrize(
        "start_x,start_y,dx,dy",
        [
            (0, 100, -1, 0),  # left edge, moving left
            (100, 0, 0, -1),  # top edge, moving up
        ],
        ids=["left_boundary", "top_boundary"],
    )
    def test_move_clamps_to_min_bounds(self, create_tank, start_x, start_y, dx, dy):
        """Test that _move() clamps position to minimum map bounds."""
        tank = create_tank(x=start_x, y=start_y)
        tank.prev_x = tank.x
        tank.prev_y = tank.y
        tank._move(dx, dy, 1.0 / FPS)
        assert tank.x >= 0
        assert tank.y >= 0

    def test_move_clamps_to_max_bounds(self, create_tank):
        """Test that _move() clamps position to maximum map bounds."""
        max_x = MAP_WIDTH_PX - TILE_SIZE
        max_y = MAP_HEIGHT_PX - TILE_SIZE
        tank = create_tank(x=max_x, y=max_y)
        tank.prev_x = tank.x
        tank.prev_y = tank.y
        # Move right — should clamp at max_x
        tank._move(1, 0, 1.0 / FPS)
        assert tank.x <= max_x
        # Move down — should clamp at max_y
        tank._move(0, 1, 1.0 / FPS)
        assert tank.y <= max_y

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

    def test_shoot_forwards_bullet_speed(self, create_tank):
        """Test that shoot() creates a bullet with the tank's bullet_speed."""
        tank = create_tank(bullet_speed=999.0)
        bullet = tank.shoot()
        assert bullet.speed == 999.0

    @pytest.mark.parametrize(
        "direction",
        [Direction.UP, Direction.RIGHT, Direction.DOWN, Direction.LEFT],
    )
    def test_shoot_passes_bullet_sprite(
        self, tank, mock_texture_manager, direction
    ):
        """Test that shoot() passes the directional sprite to the bullet."""
        tank.direction = direction
        bullet = tank.shoot()
        mock_texture_manager.get_sprite.assert_called_with(
            f"bullet_{direction}"
        )
        assert bullet.sprite is mock_texture_manager.get_sprite.return_value

    def test_shoot_sprite_none_when_missing(
        self, create_tank, mock_texture_manager
    ):
        """Test that bullet gets None sprite when texture is missing."""
        mock_texture_manager.get_sprite.side_effect = KeyError("not found")
        tank = create_tank()
        bullet = tank.shoot()
        assert bullet.sprite is None


class TestIceSlide:
    @pytest.fixture
    def tank(self, create_tank):
        return create_tank(x=128, y=128)

    def test_initial_slide_state(self, tank):
        assert tank._on_ice is False
        assert tank._sliding is False
        assert tank._slide_remaining == 0.0

    def test_start_slide_when_on_ice(self, tank):
        tank._on_ice = True
        tank.direction = Direction.RIGHT
        tank._was_moving = True
        tank.start_slide()
        assert tank._sliding is True
        assert tank._slide_direction == Direction.RIGHT
        assert tank._slide_remaining == ICE_SLIDE_DISTANCE

    def test_start_slide_ignored_when_not_on_ice(self, tank):
        tank._on_ice = False
        tank._was_moving = True
        tank.start_slide()
        assert tank._sliding is False

    def test_start_slide_ignored_when_not_moving(self, tank):
        tank._on_ice = True
        tank._was_moving = False
        tank.start_slide()
        assert tank._sliding is False

    def test_start_slide_ignored_when_already_sliding(self, tank):
        tank._on_ice = True
        tank._was_moving = True
        tank.direction = Direction.RIGHT
        tank.start_slide()
        tank._slide_remaining = 10.0
        tank.direction = Direction.LEFT
        tank.start_slide()
        assert tank._slide_direction == Direction.RIGHT
        assert tank._slide_remaining == 10.0

    def test_slide_moves_tank(self, tank):
        tank._on_ice = True
        tank._was_moving = True
        tank.direction = Direction.RIGHT
        tank.start_slide()
        old_x = tank.x
        dt = 1.0 / 60
        tank.update(dt)
        assert tank.x > old_x
        assert tank._slide_remaining < ICE_SLIDE_DISTANCE

    def test_slide_stops_when_distance_exhausted(self, tank):
        tank._on_ice = True
        tank._was_moving = True
        tank.direction = Direction.RIGHT
        tank.start_slide()
        dt = 1.0 / 60
        for _ in range(120):
            tank.update(dt)
        assert tank._sliding is False
        assert tank._slide_remaining <= 0.0

    def test_on_movement_blocked_cancels_slide(self, tank):
        tank._on_ice = True
        tank._was_moving = True
        tank.direction = Direction.RIGHT
        tank.start_slide()
        tank.on_movement_blocked()
        assert tank._sliding is False
        assert tank._slide_remaining == 0.0


class TestIsMoving:
    def test_is_moving_false_by_default(self, create_tank):
        tank = create_tank()
        assert tank.is_moving is False

    def test_is_moving_true_after_move(self, create_tank):
        tank = create_tank()
        tank._move(1, 0, 1.0 / 60)
        assert tank.is_moving is True

    def test_is_moving_true_when_sliding(self, create_tank):
        tank = create_tank()
        tank._on_ice = True
        tank._was_moving = True
        tank.start_slide()
        tank._moving_this_frame = False
        assert tank.is_moving is True

    def test_is_moving_resets_after_update(self, create_tank):
        tank = create_tank()
        tank._move(1, 0, 1.0 / 60)
        assert tank.is_moving is True
        tank.update(1.0 / 60)
        assert tank.is_moving is False


class TestStartSlideReturnValue:
    def test_start_slide_returns_true_when_slide_begins(self, create_tank):
        tank = create_tank()
        tank._on_ice = True
        tank._was_moving = True
        assert tank.start_slide() is True
        assert tank.is_sliding is True

    def test_start_slide_returns_false_when_not_on_ice(self, create_tank):
        tank = create_tank()
        tank._was_moving = True
        assert tank.start_slide() is False

    def test_start_slide_returns_false_when_already_sliding(self, create_tank):
        tank = create_tank()
        tank._on_ice = True
        tank._was_moving = True
        tank.start_slide()
        assert tank.start_slide() is False

    def test_start_slide_returns_false_when_not_moving(self, create_tank):
        tank = create_tank()
        tank._on_ice = True
        tank._was_moving = False
        assert tank.start_slide() is False
