import pytest
from loguru import logger
from src.utils.constants import FPS, TILE_SIZE
from src.core.tile import Tile, TileType
from src.core.enemy_tank import EnemyTank

# Tests related to enemy behavior: spawning, movement, shooting

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
        spawn_success = game_manager._spawn_enemy()  # Attempt spawn

        spawned_count_after = len(game_manager.enemy_tanks)
        total_spawned_after = game_manager.total_enemy_spawns

        if spawn_success:
            logger.debug("Spawn successful.")
            assert spawned_count_after == spawned_count_before + 1
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
            assert spawned_count_after == spawned_count_before
            # Ensure total_spawns didn't increase if len didn't
            assert total_spawned_after == total_spawned_before, (
                "total_enemy_spawns increased even though len(enemy_tanks) did not."
            )

    # Assert final counts after the while loop finishes
    assert len(game_manager.enemy_tanks) <= max_spawns, (
        "Exceeded max on-screen enemies"
    )
    assert game_manager.total_enemy_spawns == max_spawns, (
        f"Expected total spawns {max_spawns} after filling limit, but got "
        f"{game_manager.total_enemy_spawns}"
    )

    # Attempt to spawn one more enemy beyond the limit
    logger.info("Attempting to spawn beyond max limit...")
    spawn_success = game_manager._spawn_enemy()

    # Assert counts did NOT change and spawn failed
    assert not spawn_success, "Spawn succeeded unexpectedly beyond max limit."
    assert len(game_manager.enemy_tanks) <= max_spawns, (
        f"Enemy count changed when spawning beyond limit. Expected <= {max_spawns}, got "
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
        spawn_success = game_manager._spawn_enemy()  # Attempt spawn
        spawned_count_after = len(game_manager.enemy_tanks)

        if spawn_success:
            assert spawned_count_after == spawned_count_before + 1
            new_enemy = game_manager.enemy_tanks[-1]
            new_enemy_pos = new_enemy.get_position()
            logger.debug(f"Attempt {attempt + 1}: Spawn successful at {new_enemy_pos}.")
            # Assert the new enemy did NOT spawn at the blocked point
            assert new_enemy_pos != blocked_spawn_point_pixels, (
                f"Enemy spawned at the blocked point {blocked_spawn_point_pixels} "
                f"on attempt {attempt + 1}."
            )
        else:
            assert spawned_count_after == spawned_count_before
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

    # Because one point is blocked, we might not reach max_spawns
    assert len(game_manager.enemy_tanks) <= max_spawns, (
        f"Enemy count ({len(game_manager.enemy_tanks)}) exceeded max spawns "
        f"({max_spawns})."
    )
    assert game_manager.total_enemy_spawns <= max_spawns, (
        f"Total enemy spawns ({game_manager.total_enemy_spawns}) exceeded max "
        f"spawns ({max_spawns})."
    )
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