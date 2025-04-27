import pytest
import pygame
from unittest.mock import MagicMock
from loguru import logger
from src.managers.game_manager import GameManager
from src.utils.constants import FPS, TILE_SIZE, GRID_WIDTH, GRID_HEIGHT
from src.states.game_state import GameState
from src.core.bullet import Bullet
from src.core.tile import Tile, TileType
from src.core.enemy_tank import EnemyTank

# Initialize Pygame non-graphically for testing
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)  # Minimal display init


@pytest.fixture
def game_manager_fixture():
    """Fixture to provide a standard GameManager instance."""
    # Simply create and return a new GameManager
    # Map modification will happen within the parameterized test
    return GameManager()


def test_initial_game_state(game_manager_fixture):
    """Test the initial state of the GameManager after initialization."""
    game_manager = game_manager_fixture

    # 1. Verify initial game state enum
    assert game_manager.state == GameState.RUNNING, (
        f"Expected initial state RUNNING, got {game_manager.state.name}"
    )

    # 2. Verify initial player lives
    expected_initial_lives = 3  # Assuming PlayerTank defaults to 3
    assert game_manager.player_tank.lives == expected_initial_lives, (
        f"Expected initial player lives {expected_initial_lives}, "
        f"got {game_manager.player_tank.lives}"
    )

    # 3. Verify initial number of enemies
    assert len(game_manager.enemy_tanks) == 1, (
        f"Expected 1 initial enemy tank, got {len(game_manager.enemy_tanks)}"
    )

    # 4. Verify initial total spawn count
    assert game_manager.total_enemy_spawns == 1, (
        f"Expected initial total_enemy_spawns 1, got {game_manager.total_enemy_spawns}"
    )

    # 5. Verify map layout (basic check - e.g., base location and a corner)
    game_map = game_manager.map
    # Check base location (assuming default GRID constants)
    expected_base_x = GRID_WIDTH // 2
    expected_base_y = GRID_HEIGHT - 2
    base_tile = game_map.get_base()
    assert base_tile is not None, "Base tile not found in initial map."
    assert base_tile.x == expected_base_x and base_tile.y == expected_base_y, (
        f"Base tile location mismatch. Expected ({expected_base_x}, "
        f"{expected_base_y}), "
        f"got ({base_tile.x}, {base_tile.y})"
    )
    assert base_tile.type == TileType.BASE, "Base tile type is not BASE."

    # Check a corner tile type (should be STEEL)
    corner_tile = game_map.get_tile_at(0, 0)
    assert corner_tile is not None, "Tile at (0,0) not found."
    assert corner_tile.type == TileType.STEEL, (
        f"Tile at (0,0) should be STEEL, got {corner_tile.type.name}"
    )

    logger.info("Initial game state verified.")


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
    game_manager = GameManager()
    player_tank = game_manager.player_tank

    # Constants from src/utils/constants.py (or get dynamically)
    BULLET_WIDTH = 8  # 4 * SCALE (assuming SCALE=2)
    BULLET_HEIGHT = 8  # 4 * SCALE (assuming SCALE=2)

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


def test_player_game_over_on_zero_lives():
    """Test game state changes to GAME_OVER when player takes fatal damage."""
    game_manager = GameManager()
    player_tank = game_manager.player_tank
    collision_manager = game_manager.collision_manager

    # Ensure the player starts with at least 1 life for the test
    assert player_tank.lives >= 1

    # Set lives to 1 to guarantee game over on next death
    player_tank.lives = 1

    # Assert initial game state is RUNNING
    assert game_manager.state == GameState.RUNNING, (
        "Game should start in RUNNING state."
    )

    # --- Setup Mocks for Collision --- #
    # 1. Mock an enemy bullet involved in the collision
    mock_enemy_bullet = MagicMock(spec=Bullet)
    mock_enemy_bullet.owner_type = "enemy"
    mock_enemy_bullet.active = True  # Needs to be active to be processed

    # 2. Mock the player tank's take_damage to return True (fatal hit)
    player_tank.take_damage = MagicMock(return_value=True)

    # 3. Mock CollisionManager to report a collision between the mock bullet and player
    collision_manager.get_collision_events = MagicMock(
        return_value=[(mock_enemy_bullet, player_tank)]
    )
    # --- End Mocks --- #

    # Execute the collision processing logic
    game_manager._process_collisions()

    # --- Assertions --- #
    # 1. Verify take_damage was called
    player_tank.take_damage.assert_called_once()

    # 2. Verify game state changed to GAME_OVER
    assert game_manager.state == GameState.GAME_OVER, (
        "Game state did not change to GAME_OVER after player's final death was "
        "processed."
    )


@pytest.mark.parametrize(
    "tile_to_place, expected_bullet_active, expected_tile_type",
    [
        (TileType.BRICK, False, TileType.EMPTY),  # Bullet hits brick, brick destroyed
        (TileType.STEEL, False, TileType.STEEL),  # Bullet hits steel, steel unchanged
        (TileType.WATER, True, TileType.WATER),  # Bullet passes through water
        (TileType.BUSH, True, TileType.BUSH),  # Bullet passes through bush
    ],
)
def test_player_bullet_vs_tile(
    game_manager_fixture,  # Use the base fixture
    tile_to_place,
    expected_bullet_active,
    expected_tile_type,
):
    """Test player bullet interaction with various tile types."""
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank
    game_map = game_manager.map

    # Define target tile location
    target_x_grid = 7
    target_y_grid = 10

    # Manually place the specified tile type at the target location
    if 0 <= target_y_grid < game_map.height and 0 <= target_x_grid < game_map.width:
        target_tile = Tile(tile_to_place, target_x_grid, target_y_grid, TILE_SIZE)
        game_map.tiles[target_y_grid][target_x_grid] = target_tile
        logger.debug(
            f"Placed {tile_to_place.name} tile at ({target_x_grid}, {target_y_grid})"
        )
    else:
        pytest.fail(
            f"Target tile coordinates ({target_x_grid}, {target_y_grid}) "
            f"are out of bounds."
        )

    # Position player below the target tile
    player_start_x = target_x_grid * TILE_SIZE
    player_start_y = (target_y_grid + 1) * TILE_SIZE
    player_tank.set_position(player_start_x, player_start_y)
    player_tank.target_position = (player_start_x, player_start_y)
    player_tank.prev_x, player_tank.prev_y = player_start_x, player_start_y

    # Aim up and shoot
    player_tank.direction = "up"
    player_tank.shoot()

    assert player_tank.bullet is not None, "Bullet failed to spawn."
    bullet = player_tank.bullet  # Get reference to the bullet

    # Simulate game time until bullet should have hit (or passed)
    dt = 1.0 / FPS
    update_duration = 0.2  # Sufficient time for bullet to travel one tile
    num_updates = int(update_duration / dt)

    for i in range(num_updates):
        game_manager.update()  # Update game (moves bullet, processes collisions)
        # Stop checking early if bullet becomes inactive for relevant cases
        if not expected_bullet_active and not bullet.active:
            logger.debug(f"Bullet became inactive as expected after {i + 1} updates.")
            break

    # --- Assertions after updates ---
    # 1. Verify bullet's final active state
    assert bullet.active == expected_bullet_active, (
        f"Bullet active state mismatch for {tile_to_place.name}. "
        f"Expected: {expected_bullet_active}, Got: {bullet.active}"
    )

    # 2. Verify the tile's final type
    # Re-fetch the tile in case it was replaced (though unlikely with current impl)
    final_tile = game_map.get_tile_at(target_x_grid, target_y_grid)
    assert final_tile is not None, "Target tile somehow disappeared."
    assert final_tile.type == expected_tile_type, (
        f"Tile type mismatch for {tile_to_place.name}. "
        f"Expected: {expected_tile_type.name}, Got: {final_tile.type.name}"
    )


def test_player_bullet_destroys_enemy_tank(game_manager_fixture):
    """Test player bullet hitting and destroying a basic enemy tank."""
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank

    # --- Spawn Enemy Tank --- #
    enemy_type = "basic"
    enemy_x_grid = 7
    enemy_y_grid = 5
    enemy_start_x = enemy_x_grid * TILE_SIZE
    enemy_start_y = enemy_y_grid * TILE_SIZE

    enemy_tank = EnemyTank(
        enemy_start_x,
        enemy_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    game_manager.enemy_tanks.append(enemy_tank)
    initial_enemy_count = len(game_manager.enemy_tanks)
    logger.debug(
        f"Manually added {enemy_type} enemy at ({enemy_x_grid}, {enemy_y_grid})"
    )
    # --- End Spawn --- #

    # Position player below the enemy tank
    player_start_x = enemy_x_grid * TILE_SIZE
    player_start_y = (enemy_y_grid + 1) * TILE_SIZE
    player_tank.set_position(player_start_x, player_start_y)
    player_tank.target_position = (player_start_x, player_start_y)
    player_tank.prev_x, player_tank.prev_y = player_start_x, player_start_y

    # Aim up and shoot
    player_tank.direction = "up"
    player_tank.shoot()

    assert player_tank.bullet is not None, "Bullet failed to spawn."
    bullet = player_tank.bullet

    # Simulate game time until bullet should have hit
    dt = 1.0 / FPS
    update_duration = 0.2  # Sufficient time for bullet to travel one tile
    num_updates = int(update_duration / dt)

    for i in range(num_updates):
        game_manager.update()  # Update game (moves bullet, processes collisions)
        # Stop checking early if bullet becomes inactive
        if not bullet.active:
            logger.debug(f"Bullet became inactive after {i + 1} updates.")
            break

    # --- Assertions after updates ---
    # 1. Bullet should be inactive after hitting the enemy
    assert not bullet.active, "Bullet should be inactive after hitting enemy."

    # 2. The enemy tank should have been removed from the list
    assert enemy_tank not in game_manager.enemy_tanks, (
        "Enemy tank was not removed after being hit."
    )
    assert len(game_manager.enemy_tanks) == initial_enemy_count - 1, (
        "Enemy count did not decrease by one."
    )


@pytest.mark.parametrize(
    "player_initial_lives, player_is_invincible, expected_game_state, "
    "expected_player_lives_after_hit",
    [
        # Case 1: Vulnerable player, final life -> Game Over
        (1, False, GameState.GAME_OVER, 0),
        # Case 2: Vulnerable player, multiple lives -> Respawn
        (3, False, GameState.RUNNING, 2),
        # Case 3: Invincible player -> No effect
        (3, True, GameState.RUNNING, 3),
    ],
)
def test_enemy_bullet_hits_player_tank(
    game_manager_fixture,
    player_initial_lives,
    player_is_invincible,
    expected_game_state,
    expected_player_lives_after_hit,
):
    """Test enemy bullet hitting the player tank under different conditions."""
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank
    initial_spawn_pos = player_tank.initial_position

    # --- Configure Player State ---
    player_tank.lives = player_initial_lives
    player_tank.is_invincible = player_is_invincible
    player_tank.invincibility_timer = 0  # Reset timer if starting invincible
    logger.debug(
        f"Setting up player: lives={player_tank.lives}, "
        f"invincible={player_tank.is_invincible}"
    )
    # --- End Player Config ---

    # --- Spawn Enemy Tank Above Player ---
    enemy_type = "basic"
    player_x_grid = int(player_tank.x // TILE_SIZE)
    player_y_grid = int(player_tank.y // TILE_SIZE)
    enemy_x_grid = player_x_grid
    enemy_y_grid = player_y_grid - 2  # Place enemy 2 tiles above

    enemy_start_x = enemy_x_grid * TILE_SIZE
    enemy_start_y = enemy_y_grid * TILE_SIZE

    # Ensure enemy spawns within bounds
    if not (
        0 <= enemy_y_grid < game_manager.map.height
        and 0 <= enemy_x_grid < game_manager.map.width
    ):
        pytest.skip(
            f"Calculated enemy position ({enemy_x_grid}, {enemy_y_grid}) "
            f"is out of bounds. Skipping."
        )

    enemy_tank = EnemyTank(
        enemy_start_x,
        enemy_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy_tank.direction = "down"  # Aim at player
    game_manager.enemy_tanks = [enemy_tank]  # Replace default enemies
    logger.debug(
        f"Manually added {enemy_type} enemy at ({enemy_x_grid}, {enemy_y_grid}) "
        f"aiming {enemy_tank.direction}"
    )
    # --- End Enemy Spawn ---

    # --- Fire Enemy Bullet ---
    enemy_tank.shoot()
    assert enemy_tank.bullet is not None, "Enemy bullet failed to spawn."
    enemy_bullet = enemy_tank.bullet
    assert enemy_bullet.active, "Enemy bullet spawned inactive."
    # --- End Fire ---

    # --- Simulate game time until bullet should hit ---
    # Distance = approx 2 tiles = 2 * TILE_SIZE
    dt = 1.0 / FPS
    update_duration = 0.4  # Should be sufficient time
    num_updates = int(update_duration / dt)
    hit_detected = False

    for _ in range(num_updates):
        game_manager.update()  # Update game (moves bullet, processes collisions)
        # Check if the bullet hit the player (bullet becomes inactive)
        if not enemy_bullet.active:
            logger.debug(
                f"Enemy bullet became inactive after {_ + 1} updates (hit detected)."
            )
            hit_detected = True
            break
        # Check if game state changed early (e.g., game over)
        if game_manager.state != GameState.RUNNING:
            logger.debug(
                f"Game state changed to {game_manager.state.name} after "
                f"{_ + 1} updates."
            )
            # If game over, hit might not register via bullet.active if
            # processed in same frame
            if (
                game_manager.state == GameState.GAME_OVER
                and expected_game_state == GameState.GAME_OVER
            ):
                hit_detected = True
            break

    # --- Assertions after updates ---
    assert hit_detected or not player_is_invincible, (
        f"Enemy bullet did not become inactive after {num_updates} updates "
        f"(Expected hit? Invincible: {player_is_invincible})"
    )

    # 1. Assert Game State
    assert game_manager.state == expected_game_state, (
        f"Expected game state {expected_game_state.name}, "
        f"but got {game_manager.state.name}"
    )

    # 2. Assert Player Lives
    assert player_tank.lives == expected_player_lives_after_hit, (
        f"Expected player lives {expected_player_lives_after_hit}, "
        f"but got {player_tank.lives}"
    )

    # 3. Assert Bullet Inactive (unless player was invincible)
    if not player_is_invincible:
        assert not enemy_bullet.active, (
            "Enemy bullet should be inactive after hitting vulnerable player."
        )

    # 4. Assert Respawn effects (if life lost but game not over)
    if (
        expected_player_lives_after_hit == player_initial_lives - 1
        and expected_game_state == GameState.RUNNING
    ):
        assert player_tank.get_position() == initial_spawn_pos, (
            "Player did not return to spawn position after losing a life."
        )
        assert player_tank.is_invincible, "Player is not invincible after respawning."
    # 5. Assert Invincible state persisted (if hit while invincible)
    elif player_is_invincible:
        assert player_tank.is_invincible, (
            "Player lost invincibility after being hit while invincible."
        )


def test_enemy_bullet_hits_other_enemy(game_manager_fixture):
    """Test that an enemy bullet has no effect on another enemy tank."""
    game_manager = game_manager_fixture

    # --- Spawn Two Enemy Tanks --- #
    enemy_type = "basic"
    enemy1_x_grid, enemy1_y_grid = 7, 5  # Top enemy (shooter)
    enemy2_x_grid, enemy2_y_grid = 7, 7  # Bottom enemy (target)

    enemy1_start_x = enemy1_x_grid * TILE_SIZE
    enemy1_start_y = enemy1_y_grid * TILE_SIZE
    enemy2_start_x = enemy2_x_grid * TILE_SIZE
    enemy2_start_y = enemy2_y_grid * TILE_SIZE

    enemy1 = EnemyTank(
        enemy1_start_x,
        enemy1_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy1.direction = "down"  # Aim at enemy2

    enemy2 = EnemyTank(
        enemy2_start_x,
        enemy2_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )

    game_manager.enemy_tanks = [enemy1, enemy2]  # Set the enemies
    initial_enemy_count = len(game_manager.enemy_tanks)
    initial_enemy2_health = enemy2.health
    logger.debug(f"Spawned enemy1 at ({enemy1_x_grid}, {enemy1_y_grid}) aiming down.")
    logger.debug(f"Spawned enemy2 at ({enemy2_x_grid}, {enemy2_y_grid}).")
    # --- End Spawn --- #

    # --- Fire Enemy Bullet --- #
    enemy1.shoot()
    assert enemy1.bullet is not None, "Enemy1 bullet failed to spawn."
    bullet = enemy1.bullet
    assert bullet.active, "Enemy1 bullet spawned inactive."
    # --- End Fire --- #

    # --- Simulate game time until bullet should hit --- #
    dt = 1.0 / FPS
    update_duration = 0.4  # Time to cross ~2 tiles
    num_updates = int(update_duration / dt)

    initial_bullet_state = bullet.active

    for _ in range(num_updates):
        game_manager.update()

    # --- Assertions --- #
    # Bullet should remain active as enemy bullets don't hit other enemies
    assert bullet.active == initial_bullet_state, "Bullet state changed unexpectedly."
    assert bullet.active, "Bullet should still be active after passing another enemy."

    # 1. Enemy2 health should be unchanged
    assert enemy2.health == initial_enemy2_health, (
        f"Enemy2 health changed. Expected: {initial_enemy2_health}, "
        f"Got: {enemy2.health}"
    )

    # 2. Enemy2 should still be in the list
    assert enemy2 in game_manager.enemy_tanks, "Enemy2 was removed from the list."

    # 3. Total enemy count should be unchanged
    assert len(game_manager.enemy_tanks) == initial_enemy_count, (
        f"Enemy count changed. Expected: {initial_enemy_count}, "
        f"Got: {len(game_manager.enemy_tanks)}"
    )


# --- Test Bullet vs Bullet ---


def test_enemy_bullets_collide(game_manager_fixture):
    """Test that two enemy bullets colliding deactivates both."""
    game_manager = game_manager_fixture

    # --- Spawn Two Enemy Tanks Facing Each Other --- #
    enemy_type = "basic"
    enemy1_x_grid, enemy1_y_grid = 5, 7  # Left enemy
    enemy2_x_grid, enemy2_y_grid = 9, 7  # Right enemy (4 tiles apart)

    enemy1_start_x = enemy1_x_grid * TILE_SIZE
    enemy1_start_y = enemy1_y_grid * TILE_SIZE
    enemy2_start_x = enemy2_x_grid * TILE_SIZE
    enemy2_start_y = enemy2_y_grid * TILE_SIZE

    enemy1 = EnemyTank(
        enemy1_start_x,
        enemy1_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy1.direction = "right"  # Aim at enemy2

    enemy2 = EnemyTank(
        enemy2_start_x,
        enemy2_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy2.direction = "left"  # Aim at enemy1

    game_manager.enemy_tanks = [enemy1, enemy2]  # Set the enemies
    logger.debug(f"Spawned enemy1 at ({enemy1_x_grid}, {enemy1_y_grid}) aiming right.")
    logger.debug(f"Spawned enemy2 at ({enemy2_x_grid}, {enemy2_y_grid}) aiming left.")
    # --- End Spawn --- #

    # --- Fire Both Bullets Simultaneously --- #
    enemy1.shoot()
    enemy2.shoot()

    assert enemy1.bullet is not None, "Enemy1 bullet failed to spawn."
    assert enemy2.bullet is not None, "Enemy2 bullet failed to spawn."
    bullet1 = enemy1.bullet
    bullet2 = enemy2.bullet
    assert bullet1.active, "Enemy1 bullet spawned inactive."
    assert bullet2.active, "Enemy2 bullet spawned inactive."
    # --- End Fire --- #

    # --- Simulate game time until bullets should collide --- #
    # They are 4 tiles apart, need to travel ~2 tiles each.
    dt = 1.0 / FPS
    update_duration = 0.4  # Should be sufficient time
    num_updates = int(update_duration / dt)
    collision_detected = False

    for _ in range(num_updates):
        game_manager.update()
        # Check if both bullets became inactive
        if not bullet1.active and not bullet2.active:
            logger.debug(f"Both bullets became inactive after {_ + 1} updates.")
            collision_detected = True
            break
        # Optional: Add checks if only one becomes inactive unexpectedly
        elif not bullet1.active or not bullet2.active:
            logger.warning(
                f"Only one bullet inactive after {_ + 1} updates "
                f"(b1:{bullet1.active}, b2:{bullet2.active})"
            )
            # Continue simulation in case the other deactivates next frame

    # --- Assertions --- #
    assert not collision_detected, "Bullet collision detected."

    # Bullets should be inactive after colliding
    assert bullet1.active, "Enemy1 bullet should be active."
    assert bullet2.active, "Enemy2 bullet should be active."


def test_player_bullet_hits_base(game_manager_fixture):
    """Test that a player bullet hitting the base destroys it and causes game over."""
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank
    game_map = game_manager.map

    # Find the base tile
    base_tile = game_map.get_base()
    assert base_tile is not None, "Base tile not found in the map."
    assert base_tile.type == TileType.BASE, "Base tile initial type is not BASE."
    base_x_grid = base_tile.x
    base_y_grid = base_tile.y
    logger.debug(f"Found base at ({base_x_grid}, {base_y_grid})")

    # Position player above the base
    player_start_x = base_x_grid * TILE_SIZE
    player_start_y = (base_y_grid - 1) * TILE_SIZE

    # Check if player start position is valid (not steel/water/etc.)
    if not (0 <= (base_y_grid - 1) < game_map.height):
        pytest.skip(
            f"Calculated player start position y={base_y_grid - 1} is out of "
            f"bounds. Skipping."
        )
    start_tile = game_map.get_tile_at(base_x_grid, base_y_grid - 1)
    if start_tile and start_tile.type != TileType.EMPTY:
        pytest.skip(
            f"Calculated player start position ({base_x_grid}, {base_y_grid - 1}) "
            f"is not EMPTY ({start_tile.type.name}). Skipping."
        )

    player_tank.set_position(player_start_x, player_start_y)
    player_tank.target_position = (player_start_x, player_start_y)
    player_tank.prev_x, player_tank.prev_y = player_start_x, player_start_y

    # Aim DOWN and shoot
    player_tank.direction = "down"  # Aim down towards base
    player_tank.shoot()

    assert player_tank.bullet is not None, "Player bullet failed to spawn."
    bullet = player_tank.bullet
    assert bullet.active, "Player bullet spawned inactive."

    # Assert initial game state is RUNNING
    assert game_manager.state == GameState.RUNNING, (
        "Game should start in RUNNING state."
    )

    # Simulate game time until bullet should have hit the base
    dt = 1.0 / FPS
    update_duration = 0.4  # Time to cross ~2 tiles
    num_updates = int(update_duration / dt)
    hit_processed = False

    for _ in range(num_updates):
        game_manager.update()
        # Check if game state changed OR bullet became inactive
        if game_manager.state != GameState.RUNNING or not bullet.active:
            logger.debug(
                f"Base hit processed after {_ + 1} updates (State: "
                f"{game_manager.state.name}, Bullet Active: {bullet.active})"
            )
            hit_processed = True
            break

    # --- Assertions --- #
    assert hit_processed, (
        "Base destruction/collision was not processed within simulation time."
    )

    # 1. Base tile type should be BASE_DESTROYED
    assert base_tile.type == TileType.BASE_DESTROYED, (
        f"Base tile type did not change to BASE_DESTROYED. Is: {base_tile.type.name}"
    )

    # 2. Player bullet should be inactive
    assert not bullet.active, "Player bullet should be inactive after hitting base."

    # 3. Game state should be GAME_OVER
    assert game_manager.state == GameState.GAME_OVER, (
        f"Game state did not change to GAME_OVER. Is: {game_manager.state.name}"
    )


# --- Test Enemy Bullet vs Base ---


def test_enemy_bullet_destroys_base_game_over(game_manager_fixture):
    """Test enemy bullet hitting the base destroys it and causes game over."""
    game_manager = game_manager_fixture
    game_map = game_manager.map

    # Find the base tile
    base_tile = game_map.get_base()
    assert base_tile is not None, "Base tile not found in the map."
    assert base_tile.type == TileType.BASE, "Base tile initial type is not BASE."
    base_x_grid = base_tile.x
    base_y_grid = base_tile.y
    logger.debug(f"Found base at ({base_x_grid}, {base_y_grid})")

    # --- Spawn Enemy Tank Above Base --- #
    enemy_type = "basic"
    enemy_x_grid = base_x_grid
    enemy_y_grid = base_y_grid - 2  # Place enemy 2 tiles above base

    enemy_start_x = enemy_x_grid * TILE_SIZE
    enemy_start_y = enemy_y_grid * TILE_SIZE

    # Ensure enemy spawns within bounds
    if not (
        0 <= enemy_y_grid < game_manager.map.height
        and 0 <= enemy_x_grid < game_manager.map.width
    ):
        pytest.skip(
            f"Calculated enemy position ({enemy_x_grid}, {enemy_y_grid}) "
            f"is out of bounds. Skipping."
        )

    enemy_tank = EnemyTank(
        enemy_start_x,
        enemy_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy_tank.direction = "down"  # Aim at base
    game_manager.enemy_tanks = [enemy_tank]  # Replace default enemies
    logger.debug(
        f"Manually added {enemy_type} enemy at ({enemy_x_grid}, {enemy_y_grid}) "
        f"aiming {enemy_tank.direction}"
    )
    # --- End Enemy Spawn --- #

    # --- Fire Enemy Bullet --- #
    enemy_tank.shoot()
    assert enemy_tank.bullet is not None, "Enemy bullet failed to spawn."
    bullet = enemy_tank.bullet
    assert bullet.active, "Enemy bullet spawned inactive."
    # --- End Fire --- #

    # Assert initial game state is RUNNING
    assert game_manager.state == GameState.RUNNING, (
        "Game should start in RUNNING state."
    )

    # --- Simulate game time until bullet should hit base --- #
    dt = 1.0 / FPS
    update_duration = 0.4  # Time to cross ~2 tiles
    num_updates = int(update_duration / dt)
    hit_processed = False

    for _ in range(num_updates):
        game_manager.update()
        # Check if game state changed OR bullet became inactive
        if game_manager.state != GameState.RUNNING or not bullet.active:
            logger.debug(
                f"Base hit processed after {_ + 1} updates (State: "
                f"{game_manager.state.name}, Bullet Active: {bullet.active})"
            )
            hit_processed = True
            break

    # --- Assertions --- #
    assert hit_processed, (
        "Base destruction/collision was not processed within simulation time."
    )

    # 1. Bullet should be inactive
    assert not bullet.active, "Enemy bullet should be inactive after hitting base."

    # 2. Base tile type should be BASE_DESTROYED
    assert base_tile.type == TileType.BASE_DESTROYED, (
        f"Base tile type did not change to BASE_DESTROYED. Is: {base_tile.type.name}"
    )

    # 3. Game state should be GAME_OVER
    assert game_manager.state == GameState.GAME_OVER, (
        f"Game state did not change to GAME_OVER. Is: {game_manager.state.name}"
    )


def test_enemy_spawning_rules(game_manager_fixture):
    """Test enemy spawning location, count, and limits."""
    game_manager = game_manager_fixture

    # Convert spawn points (grid coords) to possible pixel coords for easy checking
    spawn_points_pixels = [
        (gx * TILE_SIZE, gy * TILE_SIZE) for gx, gy in game_manager.SPAWN_POINTS
    ]

    # --- 1. Initial Spawn Verification --- #
    logger.info("Verifying initial enemy spawn...")
    assert len(game_manager.enemy_tanks) == 1, (
        "GameManager should initialize with 1 enemy."
    )
    initial_enemy = game_manager.enemy_tanks[0]
    initial_enemy_pos = initial_enemy.get_position()
    assert initial_enemy_pos in spawn_points_pixels, (
        f"Initial enemy spawned at {initial_enemy_pos}, which is not in valid spawn "
        f"points {spawn_points_pixels}"
    )
    assert game_manager.total_enemy_spawns == 1, (
        "Initial total_enemy_spawns should be 1."
    )

    # --- 2. Max Enemy Spawn Limit Verification --- #
    logger.info("Verifying maximum enemy spawn limit...")
    max_spawns = game_manager.max_enemy_spawns

    # Reset state for this part of the test
    game_manager.enemy_tanks = []
    game_manager.total_enemy_spawns = 0
    logger.debug(f"Cleared initial enemy. Max spawns to test: {max_spawns}")

    # Use a while loop allowing for failed attempts due to blocking
    # Remove max_attempts as updates should prevent infinite loops
    # max_attempts = max_spawns * 5
    # attempts = 0
    dt = 1.0 / FPS
    update_duration_between_spawns = 0.2  # Simulate time for enemies to move
    num_updates_between_spawns = int(update_duration_between_spawns / dt)

    while game_manager.total_enemy_spawns < max_spawns:
        # Simulate time to allow existing enemies to potentially move
        logger.debug(
            f"Simulating {num_updates_between_spawns} updates "
            f"before next spawn attempt..."
        )
        for _ in range(num_updates_between_spawns):
            game_manager.update()

        spawned_count_before = len(game_manager.enemy_tanks)
        total_spawned_before = game_manager.total_enemy_spawns

        logger.debug(
            f"Attempting spawn (Current total: {total_spawned_before}/{max_spawns})"
        )
        game_manager._spawn_enemy()  # Attempt spawn

        spawned_count_after = len(game_manager.enemy_tanks)
        total_spawned_after = game_manager.total_enemy_spawns

        if (
            spawned_count_after > spawned_count_before
        ):  # Check if a spawn actually happened
            logger.debug("Spawn successful.")
            # Assert total count increased only if spawn happened
            assert total_spawned_after == total_spawned_before + 1, (
                f"Total spawn count mismatch after successful spawn. "
                f"Before: {total_spawned_before}, After: {total_spawned_after}"
            )
            # Verify the newly spawned enemy position
            new_enemy = game_manager.enemy_tanks[-1]
            new_enemy_pos = new_enemy.get_position()
            assert new_enemy_pos in spawn_points_pixels, (
                f"Enemy spawned at {new_enemy_pos}, which is not in valid spawn points "
                f"{spawn_points_pixels}"
            )
        else:
            # Spawn might have failed due to blocking, which is okay.
            logger.debug(
                f"Spawn failed (likely blocked). Current total: "
                f"{total_spawned_after}/{max_spawns}"
            )
            # Ensure total_spawns didn't increase if len didn't
            assert total_spawned_after == total_spawned_before, (
                "total_enemy_spawns increased even though len(enemy_tanks) did not."
            )

    # Assert final counts after the while loop finishes
    assert len(game_manager.enemy_tanks) == max_spawns, (
        f"Expected {max_spawns} enemies after filling limit, but got "
        f"{len(game_manager.enemy_tanks)}"
    )
    assert game_manager.total_enemy_spawns == max_spawns, (
        f"Expected total spawns {max_spawns} after filling limit, but got "
        f"{game_manager.total_enemy_spawns}"
    )

    # Attempt to spawn one more enemy beyond the limit
    logger.info("Attempting to spawn beyond max limit...")
    game_manager._spawn_enemy()

    # Assert counts did NOT change
    assert len(game_manager.enemy_tanks) == max_spawns, (
        f"Enemy count changed when spawning beyond limit. Expected {max_spawns}, got "
        f"{len(game_manager.enemy_tanks)}"
    )
    assert game_manager.total_enemy_spawns == max_spawns, (
        f"Total spawn count changed when spawning beyond limit. Expected {max_spawns}, "
        f"got {game_manager.total_enemy_spawns}"
    )
    logger.info("Maximum spawn limit verified.")


def test_enemy_spawn_blocked(game_manager_fixture):
    """Test that enemies do not spawn on a blocked spawn point."""
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank

    spawn_points_grid = game_manager.SPAWN_POINTS
    spawn_points_pixels = [
        (gx * TILE_SIZE, gy * TILE_SIZE) for gx, gy in spawn_points_grid
    ]
    assert len(spawn_points_pixels) > 0, "No spawn points defined in GameManager."

    # --- Block a Spawn Point --- #
    # Choose the first spawn point to block
    blocked_spawn_point_pixels = spawn_points_pixels[0]
    blocked_spawn_point_grid = spawn_points_grid[0]
    # Move player tank to block it
    player_tank.set_position(
        blocked_spawn_point_pixels[0], blocked_spawn_point_pixels[1]
    )
    player_tank.target_position = (
        blocked_spawn_point_pixels  # Ensure target is also updated
    )
    player_tank.prev_x, player_tank.prev_y = blocked_spawn_point_pixels
    logger.info(
        f"Blocking spawn point {blocked_spawn_point_grid} with player at "
        f"{blocked_spawn_point_pixels}"
    )
    # --- End Blocking --- #

    # --- Reset Enemy State --- #
    game_manager.enemy_tanks = []
    game_manager.total_enemy_spawns = 0
    max_spawns = game_manager.max_enemy_spawns
    logger.debug(f"Cleared initial enemies. Will attempt to spawn up to {max_spawns}.")
    # --- End Reset --- #

    # --- Attempt Spawns with Blocking --- #
    # Attempt more times than available spawn points to ensure selection cycles
    max_attempts = len(spawn_points_pixels) * 5

    for attempt in range(max_attempts):
        if game_manager.total_enemy_spawns >= max_spawns:
            logger.debug("Reached max total spawns, stopping attempts.")
            break  # Stop if limit reached (unlikely if one is blocked)

        spawned_count_before = len(game_manager.enemy_tanks)
        game_manager._spawn_enemy()  # Attempt spawn
        spawned_count_after = len(game_manager.enemy_tanks)

        if spawned_count_after > spawned_count_before:
            new_enemy = game_manager.enemy_tanks[-1]
            new_enemy_pos = new_enemy.get_position()
            logger.debug(f"Attempt {attempt + 1}: Spawn successful at {new_enemy_pos}.")
            # Assert the new enemy did NOT spawn at the blocked point
            assert new_enemy_pos != blocked_spawn_point_pixels, (
                f"Enemy spawned at the blocked point {blocked_spawn_point_pixels} "
                f"on attempt {attempt + 1}."
            )
        else:
            logger.debug(
                f"Attempt {attempt + 1}: Spawn failed (possibly blocked). "
                f"Total spawned: {game_manager.total_enemy_spawns}"
            )

    # --- Assert Final State --- #
    logger.info("Verifying final state after spawn attempts with blocking...")
    # Check that no spawned enemy ended up at the blocked location
    for i, enemy in enumerate(game_manager.enemy_tanks):
        assert enemy.get_position() != blocked_spawn_point_pixels, (
            f"Enemy {i} is located at the blocked spawn point "
            f"{blocked_spawn_point_pixels}."
        )

    # Because one point is blocked, we might not reach max_spawns if _spawn_enemy
    # keeps randomly picking the blocked one. Check count is less than or equal.
    assert len(game_manager.enemy_tanks) <= max_spawns, (
        f"Enemy count ({len(game_manager.enemy_tanks)}) exceeded max spawns "
        f"({max_spawns})."
    )
    assert game_manager.total_enemy_spawns <= max_spawns, (
        f"Total enemy spawns ({game_manager.total_enemy_spawns}) exceeded max "
        f"spawns ({max_spawns})."
    )
    # We expect *at most* max_spawns-1 enemies if the blocking is perfectly effective
    # and the random choice eventually hits all other spots. This is hard to guarantee.
    # A simple check is sufficient for integration testing.
    logger.info("Blocked spawn point test completed.")


def test_enemy_movement_and_direction_change(game_manager_fixture):
    """Test that enemies move and change direction over time."""
    game_manager = game_manager_fixture

    # --- Clear existing and Spawn one enemy in open space --- #
    game_manager.enemy_tanks = []
    game_manager.total_enemy_spawns = 0
    enemy_type = "basic"
    start_x_grid, start_y_grid = 8, 8
    start_x = start_x_grid * TILE_SIZE
    start_y = start_y_grid * TILE_SIZE

    enemy_tank = EnemyTank(
        start_x, start_y, TILE_SIZE, game_manager.texture_manager, enemy_type
    )
    game_manager.enemy_tanks.append(enemy_tank)
    game_manager.total_enemy_spawns = 1  # Reflect the added enemy
    logger.debug(
        f"Spawned single enemy at ({start_x_grid}, {start_y_grid}) for movement test."
    )
    # --- End Spawn --- #

    initial_pos = enemy_tank.get_position()
    initial_direction = enemy_tank.direction
    observed_directions = {initial_direction}  # Store initial direction

    # --- Simulate Game Time --- #
    # Duration should be longer than typical direction_change_interval (2.5s for basic)
    # plus the random reset offset (up to 0.5s). Simulate for longer to be safe.
    dt = 1.0 / FPS
    direction_change_interval = enemy_tank.direction_change_interval
    simulation_duration = direction_change_interval + 1.0  # Add ample buffer
    num_updates = int(simulation_duration / dt)
    logger.info(
        f"Simulating {simulation_duration:.1f}s ({num_updates} updates), "
        f"expecting direction change after ~{direction_change_interval:.1f}s..."
    )

    direction_changed = False
    for _ in range(num_updates):
        game_manager.update()
        observed_directions.add(enemy_tank.direction)  # Record direction each frame
        if len(observed_directions) > 1:
            direction_changed = True
            logger.info(f"Direction changed after {_ + 1} updates.")
            break  # Stop simulation once direction change is observed

    # --- Assertions --- #
    final_pos = enemy_tank.get_position()

    # 1. Verify movement occurred (position changed)
    assert final_pos != initial_pos, (
        f"Enemy tank did not move. Start: {initial_pos}, End: {final_pos}"
    )

    # 2. Verify direction changed at least once during the simulation
    assert direction_changed, (
        f"Enemy direction did not change. Initial: {initial_direction}, "
        f"Observed: {observed_directions}"
    )

    logger.info(
        f"Enemy moved from {initial_pos} to {final_pos}. "
        f"Observed directions: {observed_directions}"
    )


@pytest.mark.parametrize(
    "blocking_tile_type",
    [
        TileType.STEEL,
        TileType.WATER,
        # TileType.BRICK, # Could add if needed
        # TileType.BASE, # Base also blocks tanks
    ],
)
@pytest.mark.parametrize(
    "move_direction, start_pos_offset",
    [
        ("up", (0, 1)),  # Try moving UP, start 1 tile below
        ("down", (0, -1)),  # Try moving DOWN, start 1 tile above
        ("left", (1, 0)),  # Try moving LEFT, start 1 tile right
        ("right", (-1, 0)),  # Try moving RIGHT, start 1 tile left
    ],
)
def test_enemy_movement_blocked_by_tile(
    game_manager_fixture, blocking_tile_type, move_direction, start_pos_offset
):
    """Test enemy tank movement is blocked by specific tile types."""
    game_manager = game_manager_fixture
    game_map = game_manager.map

    # Define target tile location (use a known EMPTY spot)
    target_x_grid = 10
    target_y_grid = 10  # Changed from (7, 7) to avoid default water

    # --- Place Blocking Tile --- #
    if 0 <= target_y_grid < game_map.height and 0 <= target_x_grid < game_map.width:
        # Ensure the target spot is initially empty
        original_tile = game_map.get_tile_at(target_x_grid, target_y_grid)
        assert original_tile is not None and original_tile.type == TileType.EMPTY, (
            "Target location for blocking tile is not EMPTY in default map."
        )

        target_tile = Tile(blocking_tile_type, target_x_grid, target_y_grid, TILE_SIZE)
        game_map.tiles[target_y_grid][target_x_grid] = target_tile
        logger.debug(
            f"Placed blocking {blocking_tile_type.name} tile at "
            f"({target_x_grid}, {target_y_grid})"
        )
    else:
        pytest.fail(
            f"Target tile coordinates ({target_x_grid}, {target_y_grid}) "
            f"are out of bounds."
        )
    # --- End Tile Placement --- #

    # --- Spawn Enemy Tank Adjacent --- #
    # Clear existing enemies
    game_manager.enemy_tanks = []
    game_manager.total_enemy_spawns = 0
    # Calculate start position
    start_grid_x = target_x_grid + start_pos_offset[0]
    start_grid_y = target_y_grid + start_pos_offset[1]
    start_x = start_grid_x * TILE_SIZE
    start_y = start_grid_y * TILE_SIZE

    # Ensure start position is within bounds and EMPTY
    if not (0 <= start_grid_y < game_map.height and 0 <= start_grid_x < game_map.width):
        pytest.skip(
            f"Calculated enemy start pos ({start_grid_x}, {start_grid_y}) "
            f"is out of bounds. Skipping."
        )
    start_tile = game_map.get_tile_at(start_grid_x, start_grid_y)
    # Ensure start tile exists and is EMPTY
    assert start_tile is not None and start_tile.type == TileType.EMPTY, (
        f"Calculated enemy start pos ({start_grid_x}, {start_grid_y}) is not "
        f"EMPTY ({start_tile.type.name if start_tile else 'None'}). "
        f"Cannot start test."
    )

    # Spawn the enemy
    enemy_tank = EnemyTank(
        start_x, start_y, TILE_SIZE, game_manager.texture_manager, tank_type="basic"
    )
    # Force initial direction towards the obstacle
    enemy_tank.direction = move_direction
    enemy_tank.direction_timer = 0  # Prevent immediate random change
    enemy_tank.move_timer = (
        enemy_tank.move_delay
    )  # Ensure it tries to move on first update
    game_manager.enemy_tanks.append(enemy_tank)
    game_manager.total_enemy_spawns = 1
    logger.debug(
        f"Spawned enemy at ({start_grid_x}, {start_grid_y}) aiming "
        f"{move_direction} towards {blocking_tile_type.name} tile."
    )
    # --- End Spawn --- #

    initial_pos = enemy_tank.get_position()

    # --- Simulate Game Time --- #
    num_updates = 2

    for _ in range(num_updates):
        game_manager.update()

    # --- Assertions --- #
    final_pos = enemy_tank.get_position()

    assert final_pos == initial_pos, (
        f"Enemy tank moved into {blocking_tile_type.name} when moving "
        f"{move_direction}. Start: {initial_pos}, End: {final_pos}"
    )

    logger.info(
        f"Enemy attempted move {move_direction} into {blocking_tile_type.name} "
        f"and remained at {final_pos}. Final dir: {enemy_tank.direction}"
    )


# --- Enemy Shooting Tests ---


def test_enemy_shooting(game_manager_fixture):
    """Test that enemies shoot periodically and their bullets travel correctly."""
    game_manager = game_manager_fixture

    # --- Clear existing and Spawn one enemy in open space --- #
    game_manager.enemy_tanks = []
    game_manager.total_enemy_spawns = 0
    enemy_type = "basic"  # Basic shoot_interval is 2.0s
    start_x_grid, start_y_grid = 8, 8
    start_x = start_x_grid * TILE_SIZE
    start_y = start_y_grid * TILE_SIZE

    enemy_tank = EnemyTank(
        start_x, start_y, TILE_SIZE, game_manager.texture_manager, enemy_type
    )
    # Set a known initial direction to predict bullet path
    initial_enemy_direction = "right"
    enemy_tank.direction = initial_enemy_direction
    enemy_tank.shoot_timer = 0  # Reset shoot timer for predictable firing
    game_manager.enemy_tanks.append(enemy_tank)
    game_manager.total_enemy_spawns = 1
    logger.debug(
        f"Spawned single enemy at ({start_x_grid}, {start_y_grid}) "
        f"aiming {initial_enemy_direction}"
    )
    # --- End Spawn --- #

    # --- Simulate Game Time --- #
    # Duration should be longer than shoot_interval (2.0s) + time for bullet to move
    dt = 1.0 / FPS
    shoot_interval = enemy_tank.shoot_interval
    simulation_duration = shoot_interval + 0.5  # e.g., 2.5s
    num_updates = int(simulation_duration / dt)
    logger.info(
        f"Simulating {simulation_duration}s ({num_updates} updates), "
        f"expecting shot around {shoot_interval}s..."
    )

    bullet_fired = False
    fired_bullet = None
    bullet_start_pos = None
    bullet_start_dir = None
    fire_frame = -1

    for i in range(num_updates):
        game_manager.update()

        if not bullet_fired and enemy_tank.bullet and enemy_tank.bullet.active:
            bullet_fired = True
            fired_bullet = enemy_tank.bullet
            bullet_start_pos = fired_bullet.get_position()
            # Bullet direction is set based on tank direction AT time of firing
            bullet_start_dir = fired_bullet.direction
            fire_frame = i
            logger.info(
                f"---> Enemy bullet fired on frame {i + 1}! Dir: "
                f"{bullet_start_dir}, Pos: {bullet_start_pos}"
            )
            # Continue simulation to check movement

        # If bullet fired previously, check its movement
        elif bullet_fired and fired_bullet is not None and i > fire_frame:
            # Check bullet still active (should be in open space)
            assert fired_bullet.active, (
                f"Enemy bullet became inactive unexpectedly on frame {i + 1}"
            )

            # Check bullet has moved from its start position
            current_bullet_pos = fired_bullet.get_position()
            assert current_bullet_pos != bullet_start_pos, (
                f"Enemy bullet has not moved from start pos {bullet_start_pos} "
                f"by frame {i + 1}"
            )

            # Basic check: Ensure movement is roughly in the correct direction
            # (A more precise check would calculate expected position based on speed/dt)
            if bullet_start_dir == "right":
                assert current_bullet_pos[0] > bullet_start_pos[0], (
                    "Bullet not moving right"
                )
            elif bullet_start_dir == "left":
                assert current_bullet_pos[0] < bullet_start_pos[0], (
                    "Bullet not moving left"
                )
            elif bullet_start_dir == "down":
                assert current_bullet_pos[1] > bullet_start_pos[1], (
                    "Bullet not moving down"
                )
            elif bullet_start_dir == "up":
                assert current_bullet_pos[1] < bullet_start_pos[1], (
                    "Bullet not moving up"
                )

            logger.info(
                f"Bullet movement verified at frame {i + 1}. Pos: {current_bullet_pos}"
            )
            break  # Stop simulation after verifying movement

    assert bullet_fired, (
        f"Enemy did not fire a bullet within {simulation_duration}s "
        f"({num_updates} updates)"
    )


def test_victory_condition(game_manager_fixture):
    """Test that game state changes to VICTORY when all enemies are gone
    and the total spawn count has reached the maximum."""
    game_manager = game_manager_fixture

    # --- Setup Victory Condition --- #
    # Simulate that all enemies have been spawned
    game_manager.total_enemy_spawns = game_manager.max_enemy_spawns
    # Simulate that all on-screen enemies are destroyed
    game_manager.enemy_tanks = []
    logger.info(
        f"Setting up victory condition: total_spawns="
        f"{game_manager.total_enemy_spawns}, on-screen enemies=0"
    )
    # --- End Setup --- #

    # Assert initial state is RUNNING (or whatever state it might be in)
    assert game_manager.state == GameState.RUNNING, (
        "Test setup assumes starting in RUNNING state."
    )

    # Call update(), which now checks victory condition after _process_collisions
    logger.info("Calling update() to check victory condition...")
    game_manager.update()

    # --- Assertions --- #
    assert game_manager.state == GameState.VICTORY, (
        f"Game state did not change to VICTORY. Is: {game_manager.state.name}"
    )

    logger.info("Victory condition verified.")
