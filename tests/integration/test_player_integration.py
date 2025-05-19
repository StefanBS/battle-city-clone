import pytest
import pygame
from loguru import logger
from src.managers.game_manager import GameManager
from src.utils.constants import FPS, TILE_SIZE, BULLET_WIDTH, BULLET_HEIGHT
from src.core.tile import Tile, TileType

# Tests related to player actions: movement, shooting, respawn


@pytest.mark.parametrize(
    "key, axis, direction_sign, expected_direction",
    [
        (pygame.K_UP, 1, -1, "up"),  # UP: axis=1 (y), direction=-1 (decrease)
        (pygame.K_DOWN, 1, 1, "down"),  # DOWN: axis=1 (y), direction=1 (increase)
        (pygame.K_LEFT, 0, -1, "left"),  # LEFT: axis=0 (x), direction=-1 (decrease)
        (pygame.K_RIGHT, 0, 1, "right"),  # RIGHT: axis=0 (x), direction=1 (increase)
    ],
)
def test_player_movement(key, axis, direction_sign, expected_direction):
    """Test player tank movement and direction in all four directions."""
    # Use fresh instance to avoid side effects from other tests
    game_manager = GameManager()
    player_tank = game_manager.player_tank

    # Manually set position to an open space (grid 8, 8)
    start_grid_x, start_grid_y = 8, 8
    new_x = start_grid_x * TILE_SIZE
    new_y = start_grid_y * TILE_SIZE
    player_tank.set_position(new_x, new_y)
    player_tank.target_position = (new_x, new_y)  # Ensure target is also updated
    player_tank.prev_x, player_tank.prev_y = new_x, new_y  # Sync previous position

    initial_pos = player_tank.get_position()
    dt = 1.0 / FPS
    update_duration = 0.2
    num_updates = int(update_duration / dt)

    # Simulate key press
    key_down_event = pygame.event.Event(pygame.KEYDOWN, key=key)
    game_manager.player_tank.handle_event(key_down_event)

    # Update game state
    for _ in range(num_updates):
        game_manager.update()

    # Simulate key release
    key_up_event = pygame.event.Event(pygame.KEYUP, key=key)
    game_manager.player_tank.handle_event(key_up_event)

    final_pos = player_tank.get_position()

    # Assert position changed
    assert final_pos != initial_pos

    # Assert movement occurred in the correct direction
    if direction_sign == -1:
        assert final_pos[axis] < initial_pos[axis]
    else:
        assert final_pos[axis] > initial_pos[axis]

    # Assert the tank's direction is correct
    assert player_tank.direction == expected_direction


@pytest.mark.parametrize(
    "blocking_tile_type",
    [
        TileType.STEEL,
        TileType.WATER,
        # TileType.BRICK, # Can add later if needed
        # TileType.BASE, # Can add later if needed
    ],
)
@pytest.mark.parametrize(
    "move_direction, key, start_pos_offset",
    [
        ("up", pygame.K_UP, (0, 1)),  # Try moving UP, start 1 tile below
        ("down", pygame.K_DOWN, (0, -1)),  # Try moving DOWN, start 1 tile above
        ("left", pygame.K_LEFT, (1, 0)),  # Try moving LEFT, start 1 tile right
        ("right", pygame.K_RIGHT, (-1, 0)),  # Try moving RIGHT, start 1 tile left
    ],
)
def test_player_movement_blocked_by_tile(
    game_manager_fixture, blocking_tile_type, move_direction, key, start_pos_offset
):
    """Test player tank movement is blocked by specific tile types."""
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank
    game_map = game_manager.map

    # Define target tile location
    target_x_grid = 7
    target_y_grid = 7  # Choose a location away from default obstacles

    # Manually place the specified tile type at the target location
    if 0 <= target_y_grid < game_map.height and 0 <= target_x_grid < game_map.width:
        target_tile = Tile(blocking_tile_type, target_x_grid, target_y_grid, TILE_SIZE)
        game_map.tiles[target_y_grid][target_x_grid] = target_tile
        logger.debug(
            f"Placed {blocking_tile_type.name} tile at "
            f"({target_x_grid}, {target_y_grid})"
        )
    else:
        pytest.fail(
            f"Target tile coordinates ({target_x_grid}, {target_y_grid}) "
            f"are out of bounds."
        )

    # Calculate player start position based on offset
    start_grid_x = target_x_grid + start_pos_offset[0]
    start_grid_y = target_y_grid + start_pos_offset[1]
    start_x = start_grid_x * TILE_SIZE
    start_y = start_grid_y * TILE_SIZE

    # Ensure start position is within bounds
    if not (0 <= start_grid_y < game_map.height and 0 <= start_grid_x < game_map.width):
        pytest.skip(
            f"Calculated start position ({start_grid_x}, {start_grid_y}) is out of "
            f"bounds for target ({target_x_grid}, {target_y_grid}). Skipping."
        )

    # Place player
    player_tank.set_position(start_x, start_y)
    player_tank.target_position = (start_x, start_y)
    player_tank.prev_x, player_tank.prev_y = start_x, start_y

    initial_pos = player_tank.get_position()
    dt = 1.0 / FPS
    update_duration = 0.2  # Simulate for a short duration
    num_updates = int(update_duration / dt)

    # Simulate key press
    key_down_event = pygame.event.Event(pygame.KEYDOWN, key=key)
    game_manager.player_tank.handle_event(key_down_event)

    # Update game state
    for _ in range(num_updates):
        game_manager.update()

    # Simulate key release (optional, but good practice)
    key_up_event = pygame.event.Event(pygame.KEYUP, key=key)
    game_manager.player_tank.handle_event(key_up_event)

    final_pos = player_tank.get_position()

    # Assert position has NOT changed
    assert final_pos == initial_pos, (
        f"Tank moved into {blocking_tile_type.name} when moving {move_direction}. "
        f"Start: {initial_pos}, End: {final_pos}"
    )

    # Assert the tank's direction is correct (it should face the obstacle)
    assert player_tank.direction == move_direction, (
        f"Tank direction incorrect when blocked by {blocking_tile_type.name}. "
        f"Expected {move_direction}, got {player_tank.direction}"
    )


def test_player_shooting():
    """Test player shooting mechanics."""
    # Use fresh instance
    game_manager = GameManager()
    player_tank = game_manager.player_tank

    # 1. Initial state: No bullet
    assert player_tank.bullet is None, "Player should not have a bullet initially."

    # 2. Fire the first bullet
    player_tank.direction = "right"  # Set a known direction
    player_tank.shoot()

    # 3. Verify bullet creation and properties
    assert player_tank.bullet is not None, "Bullet object was not created."
    assert player_tank.bullet.active, "Bullet should be active after shooting."
    assert player_tank.bullet.direction == "right", "Bullet direction is incorrect."
    assert player_tank.bullet.owner_type == "player", "Bullet owner type is incorrect."

    # 4. Verify bullet initial position (centered on tank)
    expected_x = player_tank.x + player_tank.width // 2 - BULLET_WIDTH // 2
    expected_y = player_tank.y + player_tank.height // 2 - BULLET_HEIGHT // 2
    actual_pos = player_tank.bullet.get_position()
    assert actual_pos == (expected_x, expected_y), (
        f"Bullet spawn position incorrect. Expected ({expected_x}, {expected_y}), "
        f"got {actual_pos}"
    )

    # 5. Attempt to fire a second bullet immediately
    original_bullet_instance = player_tank.bullet  # Keep reference
    player_tank.shoot()

    # 6. Verify no new bullet was created
    assert player_tank.bullet is original_bullet_instance, (
        "Firing again should not create a new bullet instance while the first "
        "is active."
    )
    assert player_tank.bullet.active, "Original bullet should still be active."


@pytest.mark.parametrize(
    "direction_str, axis_index, direction_sign",
    [
        ("up", 1, -1),  # UP: axis=1 (y), sign=-1 (decrease)
        ("down", 1, 1),  # DOWN: axis=1 (y), sign=1 (increase)
        ("left", 0, -1),  # LEFT: axis=0 (x), sign=-1 (decrease)
        ("right", 0, 1),  # RIGHT: axis=0 (x), sign=1 (increase)
    ],
)
def test_player_bullet_movement(direction_str, axis_index, direction_sign):
    """Test that the player's bullet moves correctly after firing."""
    # Use fresh instance
    game_manager = GameManager()
    player_tank = game_manager.player_tank

    # Set tank direction and fire
    player_tank.direction = direction_str
    player_tank.shoot()

    assert player_tank.bullet is not None, "Bullet failed to spawn."
    assert player_tank.bullet.active, "Bullet spawned but is not active."
    assert player_tank.bullet.direction == direction_str, "Bullet has wrong direction."

    initial_pos = player_tank.bullet.get_position()

    # Simulate game time
    dt = 1.0 / FPS
    update_duration = 0.1  # Short duration to see movement
    num_updates = int(update_duration / dt)

    for _ in range(num_updates):
        game_manager.update()  # Update game (which updates bullet)

    final_pos = player_tank.bullet.get_position()

    # Assert position changed
    assert final_pos != initial_pos, f"Bullet did not move from {initial_pos}"

    # Assert movement occurred in the correct direction
    if direction_sign == -1:
        assert final_pos[axis_index] < initial_pos[axis_index], (
            f"Bullet moved wrong way ({direction_str}). "
            f"Start: {initial_pos[axis_index]}, End: {final_pos[axis_index]}"
        )
    else:
        assert final_pos[axis_index] > initial_pos[axis_index], (
            f"Bullet moved wrong way ({direction_str}). "
            f"Start: {initial_pos[axis_index]}, End: {final_pos[axis_index]}"
        )

    # Assert movement occurred ONLY along the expected axis
    other_axis_index = 1 - axis_index
    assert final_pos[other_axis_index] == initial_pos[other_axis_index], (
        f"Bullet moved unexpectedly along axis {other_axis_index}. "
        f"Start: {initial_pos[other_axis_index]}, End: {final_pos[other_axis_index]}"
    )


def test_player_respawn():
    """Test player respawn mechanics after taking lethal damage with lives remaining."""
    # Use fresh instance
    game_manager = GameManager()
    player_tank = game_manager.player_tank

    initial_lives = player_tank.lives
    initial_health = player_tank.health
    initial_max_health = player_tank.max_health
    spawn_pos = player_tank.initial_position

    assert initial_lives > 1, "Test requires player to start with more than 1 life."

    # Simulate taking lethal damage (enough to reduce health to 0 or less)
    # We call take_damage directly to isolate the respawn logic test
    was_destroyed_permanently = player_tank.take_damage(amount=initial_health)

    # Assert that the tank wasn't *permanently* destroyed (still had lives)
    assert not was_destroyed_permanently, "Tank was permanently destroyed unexpectedly."

    # In the actual game loop, GameManager would call respawn here
    # We call it directly for this integration test focused on respawn effects
    player_tank.respawn()

    # 1. Verify lives decreased
    assert player_tank.lives == initial_lives - 1, (
        f"Player lives did not decrease. Expected {initial_lives - 1}, "
        f"got {player_tank.lives}"
    )

    # 2. Verify health reset (assuming respawn resets health)
    # Note: take_damage() already resets health if lives > 0
    # respawn() itself doesn't reset health in the current implementation
    # We check it was reset by take_damage
    assert player_tank.health == initial_max_health, (
        f"Player health not reset after taking damage. Expected {initial_max_health}, "
        f"got {player_tank.health}"
    )

    # 3. Verify position reset to spawn point
    current_pos = player_tank.get_position()
    assert current_pos == spawn_pos, (
        f"Player did not respawn at initial position. Expected {spawn_pos}, "
        f"got {current_pos}"
    )

    # 4. Verify invincibility is active
    assert player_tank.is_invincible, "Player should be invincible after respawning."
    assert player_tank.invincibility_timer == 0, "Invincibility timer should be reset."

    # 5. Verify invincibility wears off after duration
    invincibility_duration = player_tank.invincibility_duration
    dt = 1.0 / FPS
    # Calculate number of updates to *exceed* the duration slightly
    num_updates_to_exceed_duration = int(invincibility_duration / dt) + 2

    # Update until invincibility should have worn off
    for i in range(num_updates_to_exceed_duration):
        # Check if invincibility wore off early (optional, but good for debugging)
        if not player_tank.is_invincible and i * dt < invincibility_duration:
            logger.warning(
                f"Invincibility wore off early at frame {i + 1} ({i * dt:.2f}s)"
            )
            # We can continue or fail here depending on strictness
            break
        game_manager.update()  # Need to update game manager for timers

        # Exit loop once invincibility wears off
        if not player_tank.is_invincible:
            logger.info(
                f"Invincibility wore off as expected at frame {i + 1} ({i * dt:.2f}s)"
            )
            break

    assert not player_tank.is_invincible, "Player invincibility did not wear off."
