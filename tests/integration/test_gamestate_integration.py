import pytest
from unittest.mock import MagicMock
from loguru import logger
from src.managers.game_manager import GameManager
from src.utils.constants import Direction, FPS, TILE_SIZE, SUB_TILE_SIZE
from src.states.game_state import GameState
from src.core.bullet import Bullet
from src.core.tile import Tile, TileType
from src.core.enemy_tank import EnemyTank

# Tests related to game state transitions and initial state verification


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

    # 3. Verify initial number of enemies (may be pending spawn animation)
    total_enemies = (
        len(game_manager.spawn_manager.enemy_tanks)
        + len(game_manager.spawn_manager._pending_spawns)
    )
    assert total_enemies == 1, (
        f"Expected 1 initial enemy (active or pending), got {total_enemies}"
    )

    # 4. Verify initial total spawn count
    assert game_manager.spawn_manager.total_enemy_spawns == 1, (
        f"Expected initial total_enemy_spawns 1, got {game_manager.spawn_manager.total_enemy_spawns}"
    )

    # 5. Verify map layout (basic check - e.g., base exists and corner tile)
    game_map = game_manager.map
    base_tile = game_map.get_base()
    assert base_tile is not None, "Base tile not found in initial map."
    assert base_tile.type == TileType.BASE, "Base tile type is not BASE."
    # Base should be within map bounds
    assert 0 <= base_tile.x < game_map.width, (
        f"Base tile x={base_tile.x} out of map bounds (width={game_map.width})"
    )
    assert 0 <= base_tile.y < game_map.height, (
        f"Base tile y={base_tile.y} out of map bounds (height={game_map.height})"
    )

    # Check a corner tile type (EMPTY in level_01.tmx)
    corner_tile = game_map.get_tile_at(0, 0)
    assert corner_tile is not None, "Tile at (0,0) not found."
    assert corner_tile.type == TileType.EMPTY, (
        f"Tile at (0,0) should be EMPTY, got {corner_tile.type.name}"
    )

    logger.info("Initial game state verified.")


def test_player_game_over_on_zero_lives():
    """Test game state changes to GAME_OVER when player takes fatal damage."""
    # Use a fresh instance as we are mocking methods
    game_manager = GameManager()
    player_tank = game_manager.player_tank
    # collision_manager variable removed as it wasn't used

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
    # Need to mock the instance within game_manager
    game_manager.collision_manager.get_collision_events = MagicMock(
        return_value=[(mock_enemy_bullet, player_tank)]
    )
    # --- End Mocks --- #

    # Execute the collision processing logic via the new handler
    events = game_manager.collision_manager.get_collision_events()
    game_manager.collision_response_handler.process_collisions(events)

    # --- Assertions --- #
    # 1. Verify take_damage was called
    player_tank.take_damage.assert_called_once()

    # 2. Verify game state changed to GAME_OVER
    assert game_manager.state == GameState.GAME_OVER, (
        "Game state did not change to GAME_OVER after player's final death was "
        "processed."
    )


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

    # Position player above the base (2 sub-tiles = 1 tank height)
    player_start_x = base_x_grid * SUB_TILE_SIZE
    player_start_y = (base_y_grid - 2) * SUB_TILE_SIZE

    # Check if player start position is valid (not steel/water/etc.)
    if not (0 <= (base_y_grid - 2) < game_map.height):
        pytest.skip(
            f"Calculated player start position y={base_y_grid - 2} is out of "
            f"bounds. Skipping."
        )
    # Clear the 2x2 sub-tile area where the player will be placed
    for dy in range(2):
        for dx in range(2):
            sx, sy = base_x_grid + dx, base_y_grid - 2 + dy
            start_tile = game_map.get_tile_at(sx, sy)
            if start_tile and start_tile.type != TileType.EMPTY:
                game_map.place_tile(
                    sx,
                    sy,
                    Tile(TileType.EMPTY, sx, sy, SUB_TILE_SIZE),
                )

    player_tank.set_position(player_start_x, player_start_y)
    player_tank.prev_x, player_tank.prev_y = player_start_x, player_start_y

    # Aim DOWN and shoot
    player_tank.direction = Direction.DOWN  # Aim down towards base
    game_manager._try_shoot(player_tank)

    assert len(game_manager.bullets) == 1, "Player bullet failed to spawn."
    bullet = next(b for b in game_manager.bullets if b.owner is player_tank)
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
    enemy_y_grid = (
        base_y_grid - 4
    )  # Place enemy 4 sub-tiles (2 tank heights) above base

    enemy_start_x = enemy_x_grid * SUB_TILE_SIZE
    enemy_start_y = enemy_y_grid * SUB_TILE_SIZE

    # Ensure enemy spawns within bounds
    if not (
        0 <= enemy_y_grid < game_manager.map.height
        and 0 <= enemy_x_grid < game_manager.map.width
    ):
        pytest.skip(
            f"Calculated enemy position ({enemy_x_grid}, {enemy_y_grid}) "
            f"is out of bounds. Skipping."
        )

    # Clear sub-tiles between enemy and base so bullet can reach the base
    for y in range(enemy_y_grid, base_y_grid):
        for dx in range(2):
            tile = game_map.get_tile_at(enemy_x_grid + dx, y)
            if tile and tile.type != TileType.EMPTY and tile.type != TileType.BASE:
                game_map.place_tile(
                    enemy_x_grid + dx,
                    y,
                    Tile(TileType.EMPTY, enemy_x_grid + dx, y, SUB_TILE_SIZE),
                )

    map_w_px = game_manager.map.width * SUB_TILE_SIZE
    map_h_px = game_manager.map.height * SUB_TILE_SIZE
    enemy_tank = EnemyTank(
        enemy_start_x,
        enemy_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
        map_width_px=map_w_px,
        map_height_px=map_h_px,
    )
    enemy_tank.direction = Direction.DOWN  # Aim at base
    game_manager.spawn_manager.enemy_tanks = [enemy_tank]  # Replace default enemies
    logger.debug(
        f"Manually added {enemy_type} enemy at ({enemy_x_grid}, {enemy_y_grid}) "
        f"aiming {enemy_tank.direction}"
    )
    # --- End Enemy Spawn --- #

    # --- Fire Enemy Bullet --- #
    game_manager._try_shoot(enemy_tank)
    enemy_bullets = [b for b in game_manager.bullets if b.owner is enemy_tank]
    assert len(enemy_bullets) == 1, "Enemy bullet failed to spawn."
    bullet = enemy_bullets[0]
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


def test_victory_condition(game_manager_fixture):
    """Test that game state changes to VICTORY when all enemies are gone
    and the total spawn count has reached the maximum."""
    game_manager = game_manager_fixture

    # --- Setup Victory Condition --- #
    # Simulate that all enemies have been spawned
    game_manager.spawn_manager.total_enemy_spawns = (
        game_manager.spawn_manager.max_enemy_spawns
    )
    # Simulate that all on-screen enemies are destroyed
    game_manager.spawn_manager.enemy_tanks = []
    game_manager.spawn_manager._pending_spawns = []
    logger.info(
        f"Setting up victory condition: total_spawns="
        f"{game_manager.spawn_manager.total_enemy_spawns}, on-screen enemies=0"
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
