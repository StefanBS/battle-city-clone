import pytest
from loguru import logger
from unittest.mock import patch
from src.utils.constants import Direction, FPS, TILE_SIZE, SUB_TILE_SIZE
from src.core.tile import Tile, TileType
from src.core.enemy_tank import EnemyTank
import random


def _complete_pending_spawns(game_manager, max_ticks=60):
    """Tick effect updates until all pending spawn animations finish."""
    dt = 1.0 / FPS
    sm = game_manager.spawn_manager
    em = game_manager.effect_manager
    for _ in range(max_ticks):
        if not sm._pending_spawns:
            break
        # Only tick effects and check pending spawns — don't advance spawn timer
        em.update(dt)
        still_pending = []
        for pending in sm._pending_spawns:
            if not pending.effect.active:
                sm._materialize_enemy(pending.x, pending.y, pending.tank_type)
            else:
                still_pending.append(pending)
        sm._pending_spawns = still_pending

# Tests related to enemy behavior: spawning, movement, shooting


def test_enemy_spawning_rules(game_manager_fixture):
    """Test enemy spawning location, count, and limits."""
    game_manager = game_manager_fixture

    # Convert spawn points (sub-tile grid coords) to possible pixel coords
    spawn_points_pixels = [
        (gx * SUB_TILE_SIZE, gy * SUB_TILE_SIZE)
        for gx, gy in game_manager.spawn_manager.spawn_points
    ]

    # --- 1. Initial Spawn Verification --- #
    logger.info("Verifying initial enemy spawn...")
    # Run updates to let spawn animation finish and materialize the enemy
    for _ in range(60):
        game_manager.update()
        if game_manager.spawn_manager.enemy_tanks:
            break
    assert len(game_manager.spawn_manager.enemy_tanks) == 1, (
        "GameManager should have 1 enemy after spawn animation completes."
    )
    initial_enemy = game_manager.spawn_manager.enemy_tanks[0]
    initial_enemy_pos = initial_enemy.get_position()
    assert initial_enemy_pos in spawn_points_pixels, (
        f"Initial enemy spawned at {initial_enemy_pos}, which is not in valid spawn "
        f"points {spawn_points_pixels}"
    )
    assert game_manager.spawn_manager.total_enemy_spawns == 1, (
        "Initial total_enemy_spawns should be 1."
    )

    # --- 2. Max Enemy Spawn Limit Verification --- #
    logger.info("Verifying maximum enemy spawn limit...")
    max_spawns = game_manager.spawn_manager.max_enemy_spawns

    # Reset state for this part of the test
    # Rebuild spawn queue directly (reset() does an initial spawn which we don't want)
    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    game_manager.spawn_manager._spawn_queue = (
        game_manager.spawn_manager._build_spawn_queue(1)
    )
    game_manager.spawn_manager.max_enemy_spawns = len(
        game_manager.spawn_manager._spawn_queue
    )
    logger.debug(f"Cleared initial enemy. Max spawns to test: {max_spawns}")

    dt = 1.0 / FPS
    update_duration_between_spawns = 0.2  # Simulate time for enemies to move
    num_updates_between_spawns = int(update_duration_between_spawns / dt)

    max_attempts = max_spawns * 3  # Allow retries for blocked spawns
    attempt = 0
    while game_manager.spawn_manager.total_enemy_spawns < max_spawns:
        attempt += 1
        if attempt > max_attempts:
            break  # Prevent infinite loop

        total_spawned_before = game_manager.spawn_manager.total_enemy_spawns

        # Clear existing enemies to avoid blocking spawn points on small maps
        game_manager.spawn_manager.enemy_tanks = []

        logger.debug(
            f"Attempting spawn (Current total: {total_spawned_before}/{max_spawns})"
        )
        spawn_success = game_manager.spawn_manager.spawn_enemy(
            game_manager.player_tank, game_manager.map
        )

        total_spawned_after = game_manager.spawn_manager.total_enemy_spawns

        if spawn_success:
            logger.debug("Spawn successful.")
            assert total_spawned_after == total_spawned_before + 1, (
                f"Total spawn count mismatch after successful spawn. "
                f"Before: {total_spawned_before}, "
                f"After: {total_spawned_after}"
            )
            _complete_pending_spawns(game_manager)
            # Verify the newly spawned enemy position
            assert game_manager.spawn_manager.enemy_tanks, (
                "Enemy should have materialized after spawn animation"
            )
            new_enemy = game_manager.spawn_manager.enemy_tanks[-1]
            new_enemy_pos = new_enemy.get_position()
            assert new_enemy_pos in spawn_points_pixels, (
                f"Enemy spawned at {new_enemy_pos}, "
                f"which is not in valid spawn points "
                f"{spawn_points_pixels}"
            )
        else:
            logger.debug(
                f"Spawn failed (likely blocked). Current total: "
                f"{total_spawned_after}/{max_spawns}"
            )
            assert total_spawned_after == total_spawned_before, (
                "total_enemy_spawns increased even though spawn failed."
            )

    # Assert final counts after the while loop finishes
    assert len(game_manager.spawn_manager.enemy_tanks) <= max_spawns, (
        "Exceeded max on-screen enemies"
    )
    assert game_manager.spawn_manager.total_enemy_spawns == max_spawns, (
        f"Expected total spawns {max_spawns} after filling limit, but got "
        f"{game_manager.spawn_manager.total_enemy_spawns}"
    )

    # Attempt to spawn one more enemy beyond the limit
    logger.info("Attempting to spawn beyond max limit...")
    spawn_success = game_manager.spawn_manager.spawn_enemy(
        game_manager.player_tank, game_manager.map
    )

    # Assert counts did NOT change and spawn failed
    assert not spawn_success, "Spawn succeeded unexpectedly beyond max limit."
    assert len(game_manager.spawn_manager.enemy_tanks) <= max_spawns, (
        f"Enemy count changed when spawning beyond limit. Expected <= {max_spawns}, "
        f"got {len(game_manager.spawn_manager.enemy_tanks)}"
    )
    assert game_manager.spawn_manager.total_enemy_spawns == max_spawns, (
        f"Total spawn count changed when spawning beyond limit. "
        f"Expected {max_spawns}, got {game_manager.spawn_manager.total_enemy_spawns}"
    )
    logger.info("Maximum spawn limit verified.")


def test_enemy_spawn_blocked(game_manager_fixture):
    """Test that enemies do not spawn on a blocked spawn point."""
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank

    spawn_points_grid = game_manager.spawn_manager.spawn_points
    spawn_points_pixels = [
        (gx * SUB_TILE_SIZE, gy * SUB_TILE_SIZE) for gx, gy in spawn_points_grid
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
    player_tank.prev_x, player_tank.prev_y = blocked_spawn_point_pixels
    logger.info(
        f"Blocking spawn point {blocked_spawn_point_grid} with player at "
        f"{blocked_spawn_point_pixels}"
    )
    # --- End Blocking --- #

    # --- Reset Enemy State --- #
    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager._pending_spawns = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    max_spawns = game_manager.spawn_manager.max_enemy_spawns
    logger.debug(f"Cleared initial enemies. Will attempt to spawn up to {max_spawns}.")
    # --- End Reset --- #

    # --- Attempt Spawns with Blocking --- #
    # Attempt more times than available spawn points to ensure selection cycles
    max_attempts = len(spawn_points_pixels) * 5

    for attempt in range(max_attempts):
        if game_manager.spawn_manager.total_enemy_spawns >= max_spawns:
            logger.debug("Reached max total spawns, stopping attempts.")
            break  # Stop if limit reached (unlikely if one is blocked)

        spawned_count_before = len(game_manager.spawn_manager.enemy_tanks)
        spawn_success = game_manager.spawn_manager.spawn_enemy(
            game_manager.player_tank, game_manager.map
        )  # Attempt spawn
        spawned_count_after = len(game_manager.spawn_manager.enemy_tanks)

        if spawn_success:
            _complete_pending_spawns(game_manager)
            spawned_count_after = len(game_manager.spawn_manager.enemy_tanks)
            assert spawned_count_after == spawned_count_before + 1
            new_enemy = game_manager.spawn_manager.enemy_tanks[-1]
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
                f"Total spawned: {game_manager.spawn_manager.total_enemy_spawns}"
            )

    # --- Assert Final State --- #
    logger.info("Verifying final state after spawn attempts with blocking...")
    # Check that no spawned enemy ended up at the blocked location
    for i, enemy in enumerate(game_manager.spawn_manager.enemy_tanks):
        assert enemy.get_position() != blocked_spawn_point_pixels, (
            f"Enemy {i} is located at the blocked spawn point "
            f"{blocked_spawn_point_pixels}."
        )

    # Because one point is blocked, we might not reach max_spawns
    assert len(game_manager.spawn_manager.enemy_tanks) <= max_spawns, (
        f"Enemy count ({len(game_manager.spawn_manager.enemy_tanks)}) exceeded max spawns "
        f"({max_spawns})."
    )
    assert game_manager.spawn_manager.total_enemy_spawns <= max_spawns, (
        f"Total enemy spawns ({game_manager.spawn_manager.total_enemy_spawns}) exceeded max "
        f"spawns ({max_spawns})."
    )
    logger.info("Blocked spawn point test completed.")


# Keep the original random.choice before patching
original_random_choice = random.choice


@patch("src.core.enemy_tank.random.choice")
@patch("src.core.enemy_tank.random.uniform", return_value=0.0)
def test_enemy_movement_and_direction_change(
    mock_uniform, mock_choice, game_manager_fixture
):
    """Test that enemies move and change direction over time."""
    game_manager = game_manager_fixture

    # --- Clear existing and Spawn one enemy in open space --- #
    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    enemy_type = "basic"
    start_x_grid, start_y_grid = 16, 16  # sub-tile grid coords
    start_x = start_x_grid * SUB_TILE_SIZE
    start_y = start_y_grid * SUB_TILE_SIZE

    # Clear sub-tiles around starting position so enemy can move in any direction
    game_map = game_manager.map
    for dy in range(-4, 6):
        for dx in range(-4, 6):
            nx, ny = start_x_grid + dx, start_y_grid + dy
            if 0 <= nx < game_map.width and 0 <= ny < game_map.height:
                tile = game_map.get_tile_at(nx, ny)
                if tile and tile.type != TileType.EMPTY:
                    game_map.place_tile(
                        nx, ny, Tile(TileType.EMPTY, nx, ny, SUB_TILE_SIZE)
                    )

    # Use the original random.choice via side_effect for the __init__ call
    mock_choice.side_effect = lambda x: original_random_choice(x)
    map_w_px = game_manager.map.width * SUB_TILE_SIZE
    map_h_px = game_manager.map.height * SUB_TILE_SIZE
    enemy_tank = EnemyTank(
        start_x,
        start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
        map_width_px=map_w_px,
        map_height_px=map_h_px,
    )
    initial_direction = enemy_tank.direction  # Capture initial direction

    # Set the mock_choice to return a different direction for the _change_direction call
    possible_directions = list(Direction)
    forced_new_direction = next(
        d for d in possible_directions if d != initial_direction
    )
    mock_choice.side_effect = None  # Clear the side_effect
    mock_choice.return_value = forced_new_direction
    logger.debug(
        f"Initial direction: {initial_direction}, "
        f"Mock forced direction: {forced_new_direction}"
    )

    # Prevent enemy from shooting so bullets don't hit the base
    # and cause GAME_OVER before the direction change timer fires
    enemy_tank.shoot = lambda: None

    game_manager.spawn_manager.enemy_tanks.append(enemy_tank)
    game_manager.spawn_manager.total_enemy_spawns = 1
    logger.debug(
        f"Spawned single enemy at ({start_x_grid}, {start_y_grid}) for movement test."
    )
    # --- End Spawn --- #

    initial_pos = enemy_tank.get_position()
    observed_directions = {initial_direction}

    # --- Simulate Game Time --- #
    dt = 1.0 / FPS
    direction_change_interval = enemy_tank.direction_change_interval
    simulation_duration = direction_change_interval + 0.1
    num_updates = int(simulation_duration / dt)
    logger.info(
        f"Simulating {simulation_duration:.1f}s ({num_updates} updates), "
        f"expecting direction change to {forced_new_direction} after "
        f"{direction_change_interval:.1f}s (mocked)..."
    )

    direction_changed = False
    actual_new_direction = None
    for i in range(num_updates):
        game_manager.update()
        current_direction = enemy_tank.direction
        observed_directions.add(current_direction)
        if current_direction != initial_direction and not direction_changed:
            logger.info(
                f"Direction changed from {initial_direction} to {current_direction} "
                f"after {i + 1} updates."
            )
            direction_changed = True
            actual_new_direction = current_direction
            break

    # --- Assertions --- #
    final_pos = enemy_tank.get_position()

    # 1. Verify movement occurred
    assert final_pos != initial_pos, (
        f"Enemy tank did not move. Start: {initial_pos}, End: {final_pos}"
    )

    # 2. Verify direction changed
    assert direction_changed, (
        f"Enemy direction did not change. Initial: {initial_direction}, "
        f"Observed: {observed_directions}"
    )

    # 3. Verify the direction changed to the one forced by the mock
    assert actual_new_direction == forced_new_direction, (
        f"Enemy changed direction, but not to the mocked value. "
        f"Expected: {forced_new_direction}, Got: {actual_new_direction}"
    )

    logger.info(
        f"Enemy moved from {initial_pos} to {final_pos}. "
        f"Direction changed to {actual_new_direction} as expected. "
        f"Observed directions: {observed_directions}"
    )


@pytest.mark.parametrize(
    "blocking_tile_type",
    [
        TileType.STEEL,
        TileType.WATER,
        TileType.BRICK,
        TileType.BASE,
    ],
)
@pytest.mark.parametrize(
    "move_direction, start_pos_offset",
    [
        (Direction.UP, (0, 1)),  # Try moving UP, start 1 tile below (2 sub-tiles)
        (Direction.DOWN, (0, -1)),  # Try moving DOWN, start 1 tile above (2 sub-tiles)
        (Direction.LEFT, (1, 0)),  # Try moving LEFT, start 1 tile right (2 sub-tiles)
        (Direction.RIGHT, (-1, 0)),  # Try moving RIGHT, start 1 tile left (2 sub-tiles)
    ],
)
def test_enemy_movement_blocked_by_tile(
    game_manager_fixture, blocking_tile_type, move_direction, start_pos_offset
):
    """Test enemy tank movement is blocked by specific tile types."""
    game_manager = game_manager_fixture
    game_map = game_manager.map

    # Define target tile location (sub-tile grid coords, use a known EMPTY spot)
    target_x_grid = 20
    target_y_grid = 20  # Changed from (7, 7) to avoid default water

    # --- Place Blocking Tile (2x2 sub-tile block = 1 full tile) --- #
    if (
        0 <= target_y_grid + 1 < game_map.height
        and 0 <= target_x_grid + 1 < game_map.width
    ):
        for dy in range(2):
            for dx in range(2):
                sx, sy = target_x_grid + dx, target_y_grid + dy
                original_tile = game_map.get_tile_at(sx, sy)
                assert (
                    original_tile is not None and original_tile.type == TileType.EMPTY
                ), (
                    f"Target location ({sx}, {sy}) for blocking tile is not EMPTY in default map."
                )
                tile = Tile(blocking_tile_type, sx, sy, SUB_TILE_SIZE)
                game_map.place_tile(sx, sy, tile)
        logger.debug(
            f"Placed blocking {blocking_tile_type.name} 2x2 block at "
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
    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    # Calculate start position: tank (32px) placed flush against 2x2 tile block (32px)
    # Offsets are in tank-size units (2 sub-tiles)
    start_grid_x = target_x_grid + start_pos_offset[0] * 2
    start_grid_y = target_y_grid + start_pos_offset[1] * 2
    start_x = start_grid_x * SUB_TILE_SIZE
    start_y = start_grid_y * SUB_TILE_SIZE

    # Ensure start position is within bounds and EMPTY
    if not (0 <= start_grid_y < game_map.height and 0 <= start_grid_x < game_map.width):
        pytest.skip(
            f"Calculated enemy start pos ({start_grid_x}, {start_grid_y}) "
            f"is out of bounds. Skipping."
        )
    # Clear the 2x2 sub-tile area for the enemy
    for dy in range(2):
        for dx in range(2):
            sx, sy = start_grid_x + dx, start_grid_y + dy
            if 0 <= sx < game_map.width and 0 <= sy < game_map.height:
                start_tile = game_map.get_tile_at(sx, sy)
                if start_tile is not None and start_tile.type != TileType.EMPTY:
                    game_map.place_tile(
                        sx,
                        sy,
                        Tile(TileType.EMPTY, sx, sy, SUB_TILE_SIZE),
                    )
    logger.debug(f"Cleared start area ({start_grid_x}, {start_grid_y}) to EMPTY.")

    # Spawn the enemy
    map_w_px = game_manager.map.width * SUB_TILE_SIZE
    map_h_px = game_manager.map.height * SUB_TILE_SIZE
    enemy_tank = EnemyTank(
        start_x,
        start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        tank_type="basic",
        map_width_px=map_w_px,
        map_height_px=map_h_px,
    )
    # Force initial direction towards the obstacle
    enemy_tank.direction = move_direction
    enemy_tank.direction_timer = 0  # Prevent immediate random change
    game_manager.spawn_manager.enemy_tanks.append(enemy_tank)
    game_manager.spawn_manager.total_enemy_spawns = 1
    logger.debug(
        f"Spawned enemy at ({start_grid_x}, {start_grid_y}) aiming "
        f"{move_direction} towards {blocking_tile_type.name} tile."
    )
    # --- End Spawn --- #

    initial_pos = enemy_tank.get_position()

    # --- Simulate Game Time --- #
    # One update: the tank attempts movement and gets snapped back by collision.
    # A second update would trigger _change_direction() away from the obstacle,
    # so we only check after a single update.
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
    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    enemy_type = "basic"  # Basic shoot_interval is 2.0s
    start_x_grid, start_y_grid = 16, 16  # sub-tile grid coords
    start_x = start_x_grid * SUB_TILE_SIZE
    start_y = start_y_grid * SUB_TILE_SIZE

    map_w_px = game_manager.map.width * SUB_TILE_SIZE
    map_h_px = game_manager.map.height * SUB_TILE_SIZE
    enemy_tank = EnemyTank(
        start_x,
        start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
        map_width_px=map_w_px,
        map_height_px=map_h_px,
    )
    # Set a known initial direction to predict bullet path
    initial_enemy_direction = Direction.RIGHT
    enemy_tank.direction = initial_enemy_direction
    enemy_tank.shoot_timer = 0  # Reset shoot timer for predictable firing
    game_manager.spawn_manager.enemy_tanks.append(enemy_tank)
    game_manager.spawn_manager.total_enemy_spawns = 1
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

        # Check if an enemy bullet appeared in game_manager.bullets
        enemy_bullets = [
            b for b in game_manager.bullets if b.owner_type == "enemy" and b.active
        ]
        if not bullet_fired and len(enemy_bullets) > 0:
            bullet_fired = True
            fired_bullet = enemy_bullets[0]
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
            if bullet_start_dir == Direction.RIGHT:
                assert current_bullet_pos[0] > bullet_start_pos[0], (
                    "Bullet not moving right"
                )
            elif bullet_start_dir == Direction.LEFT:
                assert current_bullet_pos[0] < bullet_start_pos[0], (
                    "Bullet not moving left"
                )
            elif bullet_start_dir == Direction.DOWN:
                assert current_bullet_pos[1] > bullet_start_pos[1], (
                    "Bullet not moving down"
                )
            elif bullet_start_dir == Direction.UP:
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
