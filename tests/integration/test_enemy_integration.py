import pytest
from unittest.mock import patch
from src.utils.constants import (
    Direction,
    Difficulty,
    FPS,
    OwnerType,
    TILE_SIZE,
    SUB_TILE_SIZE,
    TankType,
)
from src.core.tile import Tile, TileType
from src.core.enemy_tank import EnemyTank
from tests.integration.conftest import first_player, flush_pending_spawns
import random


def test_enemy_spawning_rules(game_manager_fixture):
    """Test enemy spawning location, count, and limits."""
    game_manager = game_manager_fixture

    spawn_points_pixels = [
        (gx * SUB_TILE_SIZE, gy * SUB_TILE_SIZE)
        for gx, gy in game_manager.spawn_manager.spawn_points
    ]

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

    max_spawns = game_manager.spawn_manager.max_enemy_spawns

    # Rebuild the spawn queue directly: reset() performs an initial spawn which
    # we don't want here.
    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    game_manager.spawn_manager._spawn_queue = (
        game_manager.spawn_manager._build_spawn_queue(
            game_manager.map.enemy_composition
        )
    )
    game_manager.spawn_manager.max_enemy_spawns = len(
        game_manager.spawn_manager._spawn_queue
    )

    max_attempts = max_spawns * 3
    attempt = 0
    while game_manager.spawn_manager.total_enemy_spawns < max_spawns:
        attempt += 1
        if attempt > max_attempts:
            break

        total_spawned_before = game_manager.spawn_manager.total_enemy_spawns

        # Clear enemies so they don't block spawn points on the small test map.
        game_manager.spawn_manager.enemy_tanks = []

        spawn_success = game_manager.spawn_manager.spawn_enemy(
            game_manager.player_manager.get_active_players(), game_manager.map
        )

        total_spawned_after = game_manager.spawn_manager.total_enemy_spawns

        if spawn_success:
            assert total_spawned_after == total_spawned_before + 1, (
                f"Total spawn count mismatch after successful spawn. "
                f"Before: {total_spawned_before}, "
                f"After: {total_spawned_after}"
            )
            flush_pending_spawns(game_manager)
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
            assert total_spawned_after == total_spawned_before, (
                "total_enemy_spawns increased even though spawn failed."
            )

    assert len(game_manager.spawn_manager.enemy_tanks) <= max_spawns, (
        "Exceeded max on-screen enemies"
    )
    assert game_manager.spawn_manager.total_enemy_spawns == max_spawns, (
        f"Expected total spawns {max_spawns} after filling limit, but got "
        f"{game_manager.spawn_manager.total_enemy_spawns}"
    )

    spawn_success = game_manager.spawn_manager.spawn_enemy(
        first_player(game_manager), game_manager.map
    )

    assert not spawn_success, "Spawn succeeded unexpectedly beyond max limit."
    assert len(game_manager.spawn_manager.enemy_tanks) <= max_spawns, (
        f"Enemy count changed when spawning beyond limit. Expected <= {max_spawns}, "
        f"got {len(game_manager.spawn_manager.enemy_tanks)}"
    )
    assert game_manager.spawn_manager.total_enemy_spawns == max_spawns, (
        f"Total spawn count changed when spawning beyond limit. "
        f"Expected {max_spawns}, got {game_manager.spawn_manager.total_enemy_spawns}"
    )


def test_enemy_spawn_blocked(game_manager_fixture):
    """Test that enemies do not spawn on a blocked spawn point."""
    game_manager = game_manager_fixture
    player_tank = first_player(game_manager)

    spawn_points_grid = game_manager.spawn_manager.spawn_points
    spawn_points_pixels = [
        (gx * SUB_TILE_SIZE, gy * SUB_TILE_SIZE) for gx, gy in spawn_points_grid
    ]
    assert len(spawn_points_pixels) > 0, "No spawn points defined in GameManager."

    blocked_spawn_point_pixels = spawn_points_pixels[0]
    # Park the player on the blocked spawn point to occupy it.
    player_tank.set_position(
        blocked_spawn_point_pixels[0], blocked_spawn_point_pixels[1]
    )
    player_tank.prev_x, player_tank.prev_y = blocked_spawn_point_pixels

    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager._pending_spawns = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    max_spawns = game_manager.spawn_manager.max_enemy_spawns

    # Attempt more times than there are spawn points so the selection cycles.
    max_attempts = len(spawn_points_pixels) * 5

    for _ in range(max_attempts):
        if game_manager.spawn_manager.total_enemy_spawns >= max_spawns:
            break

        spawned_count_before = len(game_manager.spawn_manager.enemy_tanks)
        spawn_success = game_manager.spawn_manager.spawn_enemy(
            game_manager.player_manager.get_active_players(), game_manager.map
        )
        spawned_count_after = len(game_manager.spawn_manager.enemy_tanks)

        if spawn_success:
            flush_pending_spawns(game_manager)
            spawned_count_after = len(game_manager.spawn_manager.enemy_tanks)
            assert spawned_count_after == spawned_count_before + 1
            new_enemy = game_manager.spawn_manager.enemy_tanks[-1]
            new_enemy_pos = new_enemy.get_position()
            assert new_enemy_pos != blocked_spawn_point_pixels, (
                f"Enemy spawned at the blocked point {blocked_spawn_point_pixels}."
            )
        else:
            assert spawned_count_after == spawned_count_before

    for i, enemy in enumerate(game_manager.spawn_manager.enemy_tanks):
        assert enemy.get_position() != blocked_spawn_point_pixels, (
            f"Enemy {i} is located at the blocked spawn point "
            f"{blocked_spawn_point_pixels}."
        )

    enemy_count = len(game_manager.spawn_manager.enemy_tanks)
    assert enemy_count <= max_spawns, (
        f"Enemy count ({enemy_count}) exceeded max spawns ({max_spawns})."
    )
    total_spawns = game_manager.spawn_manager.total_enemy_spawns
    assert total_spawns <= max_spawns, (
        f"Total enemy spawns ({total_spawns}) exceeded max spawns ({max_spawns})."
    )


original_random_choice = random.choice


@patch("src.core.enemy_tank.random.choice")
@patch("src.core.enemy_tank.random.uniform", return_value=0.0)
def test_enemy_movement_and_direction_change(
    mock_uniform, mock_choice, game_manager_fixture
):
    """Test that enemies move and change direction over time."""
    game_manager = game_manager_fixture

    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    enemy_type = TankType.BASIC
    start_x_grid, start_y_grid = 16, 16
    start_x = start_x_grid * SUB_TILE_SIZE
    start_y = start_y_grid * SUB_TILE_SIZE

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

    # Use the unmocked random.choice during __init__, then force the direction
    # change later.
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
        difficulty=Difficulty.EASY,
    )
    initial_direction = enemy_tank.direction

    possible_directions = list(Direction)
    forced_new_direction = next(
        d for d in possible_directions if d != initial_direction
    )
    mock_choice.side_effect = None
    mock_choice.return_value = forced_new_direction

    # Prevent enemy from shooting: otherwise a bullet can hit the base and trigger
    # GAME_OVER before the direction-change timer fires.
    enemy_tank.shoot = lambda: None

    game_manager.spawn_manager.enemy_tanks.append(enemy_tank)
    game_manager.spawn_manager.total_enemy_spawns = 1

    initial_pos = enemy_tank.get_position()
    observed_directions = {initial_direction}

    dt = 1.0 / FPS
    direction_change_interval = enemy_tank.direction_change_interval
    simulation_duration = direction_change_interval + 0.1
    num_updates = int(simulation_duration / dt)

    direction_changed = False
    actual_new_direction = None
    for _ in range(num_updates):
        game_manager.update()
        current_direction = enemy_tank.direction
        observed_directions.add(current_direction)
        if current_direction != initial_direction and not direction_changed:
            direction_changed = True
            actual_new_direction = current_direction
            break

    final_pos = enemy_tank.get_position()

    assert final_pos != initial_pos, (
        f"Enemy tank did not move. Start: {initial_pos}, End: {final_pos}"
    )

    assert direction_changed, (
        f"Enemy direction did not change. Initial: {initial_direction}, "
        f"Observed: {observed_directions}"
    )

    assert actual_new_direction == forced_new_direction, (
        f"Enemy changed direction, but not to the mocked value. "
        f"Expected: {forced_new_direction}, Got: {actual_new_direction}"
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
        (Direction.UP, (0, 1)),
        (Direction.DOWN, (0, -1)),
        (Direction.LEFT, (1, 0)),
        (Direction.RIGHT, (-1, 0)),
    ],
)
def test_enemy_movement_blocked_by_tile(
    game_manager_fixture, blocking_tile_type, move_direction, start_pos_offset
):
    """Test enemy tank movement is blocked by specific tile types."""
    game_manager = game_manager_fixture
    game_map = game_manager.map

    # (20, 20) is a known-empty spot on the test map (avoids default water).
    target_x_grid = 20
    target_y_grid = 20

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
                ), f"Target ({sx}, {sy}) is not EMPTY."
                tile = Tile(
                    blocking_tile_type,
                    sx,
                    sy,
                    SUB_TILE_SIZE,
                    blocks_tanks=True,
                    blocks_bullets=True,
                )
                game_map.place_tile(sx, sy, tile)
    else:
        pytest.fail(
            f"Target tile coordinates ({target_x_grid}, {target_y_grid}) "
            f"are out of bounds."
        )

    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    # start_pos_offset is in tank-size units (2 sub-tiles), so the tank sits flush
    # against the 2x2 blocking tile.
    start_grid_x = target_x_grid + start_pos_offset[0] * 2
    start_grid_y = target_y_grid + start_pos_offset[1] * 2
    start_x = start_grid_x * SUB_TILE_SIZE
    start_y = start_grid_y * SUB_TILE_SIZE

    if not (0 <= start_grid_y < game_map.height and 0 <= start_grid_x < game_map.width):
        pytest.skip(
            f"Calculated enemy start pos ({start_grid_x}, {start_grid_y}) "
            f"is out of bounds. Skipping."
        )
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

    map_w_px = game_manager.map.width * SUB_TILE_SIZE
    map_h_px = game_manager.map.height * SUB_TILE_SIZE
    enemy_tank = EnemyTank(
        start_x,
        start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        tank_type=TankType.BASIC,
        map_width_px=map_w_px,
        map_height_px=map_h_px,
    )
    enemy_tank.direction = move_direction
    enemy_tank.direction_timer = 0
    game_manager.spawn_manager.enemy_tanks.append(enemy_tank)
    game_manager.spawn_manager.total_enemy_spawns = 1

    initial_pos = enemy_tank.get_position()

    # Check after a single update: the first update attempts movement and gets
    # snapped back by the collision. A second update would trigger _change_direction()
    # away from the obstacle, which would contaminate this test.
    game_manager.update()

    final_pos = enemy_tank.get_position()

    assert final_pos == initial_pos, (
        f"Enemy tank moved into {blocking_tile_type.name} when moving "
        f"{move_direction}. Start: {initial_pos}, End: {final_pos}"
    )


def test_enemy_shooting(game_manager_fixture):
    """Test that enemies shoot periodically and their bullets travel correctly."""
    game_manager = game_manager_fixture

    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager.total_enemy_spawns = 0
    enemy_type = TankType.BASIC
    start_x_grid, start_y_grid = 16, 16
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
    initial_enemy_direction = Direction.RIGHT
    enemy_tank.direction = initial_enemy_direction
    enemy_tank.shoot_timer = 0
    game_manager.spawn_manager.enemy_tanks.append(enemy_tank)
    game_manager.spawn_manager.total_enemy_spawns = 1

    # Run longer than shoot_interval so we're guaranteed to see a shot.
    dt = 1.0 / FPS
    shoot_interval = enemy_tank.shoot_interval
    simulation_duration = shoot_interval + 0.5
    num_updates = int(simulation_duration / dt)

    bullet_fired = False
    fired_bullet = None
    bullet_start_pos = None
    bullet_start_dir = None
    fire_frame = -1

    for i in range(num_updates):
        game_manager.update()

        enemy_bullets = [
            b
            for b in game_manager.bullets
            if b.owner_type == OwnerType.ENEMY and b.active
        ]
        if not bullet_fired and len(enemy_bullets) > 0:
            bullet_fired = True
            fired_bullet = enemy_bullets[0]
            bullet_start_pos = fired_bullet.get_position()
            bullet_start_dir = fired_bullet.direction
            fire_frame = i

        elif bullet_fired and fired_bullet is not None and i > fire_frame:
            assert fired_bullet.active, (
                f"Enemy bullet became inactive unexpectedly on frame {i + 1}"
            )

            current_bullet_pos = fired_bullet.get_position()
            assert current_bullet_pos != bullet_start_pos, (
                f"Enemy bullet has not moved from start pos {bullet_start_pos} "
                f"by frame {i + 1}"
            )

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
            break

    assert bullet_fired, (
        f"Enemy did not fire a bullet within {simulation_duration}s "
        f"({num_updates} updates)"
    )
