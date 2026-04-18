import pytest
from src.utils.constants import (
    Direction,
    ENEMY_POINTS,
    FPS,
    TILE_SIZE,
    SUB_TILE_SIZE,
)
from src.states.game_state import GameState
from src.core.tile import Tile, TileType
from tests.integration.conftest import (
    clear_enemies,
    fire_bullet_from,
    first_player,
    place_player_at,
    spawn_enemy_at,
)


def test_initial_game_state(game_manager_fixture):
    """Test the initial state of the GameManager after initialization."""
    game_manager = game_manager_fixture

    assert game_manager.state == GameState.RUNNING, (
        f"Expected initial state RUNNING, got {game_manager.state.name}"
    )

    expected_initial_lives = 3
    assert first_player(game_manager).lives == expected_initial_lives, (
        f"Expected initial player lives {expected_initial_lives}, "
        f"got {first_player(game_manager).lives}"
    )

    # Spawn animation may still be running, so count pending spawns too.
    total_enemies = len(game_manager.spawn_manager.enemy_tanks) + len(
        game_manager.spawn_manager._pending_spawns
    )
    assert total_enemies == 1, (
        f"Expected 1 initial enemy (active or pending), got {total_enemies}"
    )

    spawns = game_manager.spawn_manager.total_enemy_spawns
    assert spawns == 1, f"Expected initial total_enemy_spawns 1, got {spawns}"

    game_map = game_manager.map
    base_tile = game_map.get_base()
    assert base_tile is not None, "Base tile not found in initial map."
    assert base_tile.type == TileType.BASE, "Base tile type is not BASE."
    assert 0 <= base_tile.x < game_map.width, (
        f"Base tile x={base_tile.x} out of map bounds (width={game_map.width})"
    )
    assert 0 <= base_tile.y < game_map.height, (
        f"Base tile y={base_tile.y} out of map bounds (height={game_map.height})"
    )

    corner_tile = game_map.get_tile_at(0, 0)
    assert corner_tile is not None, "Tile at (0,0) not found."
    assert corner_tile.type == TileType.EMPTY, (
        f"Tile at (0,0) should be EMPTY, got {corner_tile.type.name}"
    )


def test_player_bullet_hits_base(game_manager_fixture):
    """Test that a player bullet hitting the base destroys it and causes game over."""
    game_manager = game_manager_fixture
    player_tank = first_player(game_manager)
    game_map = game_manager.map

    base_tile = game_map.get_base()
    assert base_tile is not None, "Base tile not found in the map."
    assert base_tile.type == TileType.BASE, "Base tile initial type is not BASE."
    base_x_grid = base_tile.x
    base_y_grid = base_tile.y

    # Position player 2 sub-tiles (= 1 tank height) above the base.
    player_start_x = base_x_grid * SUB_TILE_SIZE
    player_start_y = (base_y_grid - 2) * SUB_TILE_SIZE

    if not (0 <= (base_y_grid - 2) < game_map.height):
        pytest.skip(
            f"Calculated player start position y={base_y_grid - 2} is out of "
            f"bounds. Skipping."
        )
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

    player_tank.direction = Direction.DOWN
    bullet = player_tank.shoot()
    assert bullet is not None, "Player bullet failed to spawn."
    game_manager.player_manager._bullets.append(bullet)
    assert bullet.active, "Player bullet spawned inactive."

    assert game_manager.state == GameState.RUNNING, (
        "Game should start in RUNNING state."
    )

    dt = 1.0 / FPS
    update_duration = 0.4
    num_updates = int(update_duration / dt)
    hit_processed = False

    for _ in range(num_updates):
        game_manager.update()
        if game_manager.state != GameState.RUNNING or not bullet.active:
            hit_processed = True
            break

    assert hit_processed, (
        "Base destruction/collision was not processed within simulation time."
    )

    assert base_tile.type == TileType.BASE_DESTROYED, (
        f"Base tile type did not change to BASE_DESTROYED. Is: {base_tile.type.name}"
    )

    assert not bullet.active, "Player bullet should be inactive after hitting base."

    assert game_manager.state in (
        GameState.GAME_OVER,
        GameState.GAME_OVER_ANIMATION,
    ), (
        f"Game state did not change to GAME_OVER/GAME_OVER_ANIMATION. "
        f"Is: {game_manager.state.name}"
    )


def test_enemy_bullet_destroys_base_game_over(game_manager_fixture):
    """Test enemy bullet hitting the base destroys it and causes game over."""
    game_manager = game_manager_fixture
    game_map = game_manager.map

    base_tile = game_map.get_base()
    assert base_tile is not None, "Base tile not found in the map."
    assert base_tile.type == TileType.BASE, "Base tile initial type is not BASE."
    base_x_grid = base_tile.x
    base_y_grid = base_tile.y

    enemy_x_grid = base_x_grid
    # Place enemy well above the base perimeter bricks so the bullet path is clear.
    enemy_y_grid = base_y_grid - 6

    if not (
        0 <= enemy_y_grid < game_manager.map.height
        and 0 <= enemy_x_grid < game_manager.map.width
    ):
        pytest.skip(
            f"Calculated enemy position ({enemy_x_grid}, {enemy_y_grid}) "
            f"is out of bounds. Skipping."
        )

    # Clear 4 columns between enemy and base to cover the full tank width.
    for y in range(enemy_y_grid, base_y_grid):
        for dx in range(4):
            tile = game_map.get_tile_at(enemy_x_grid + dx, y)
            if tile and tile.type != TileType.EMPTY and tile.type != TileType.BASE:
                game_map.place_tile(
                    enemy_x_grid + dx,
                    y,
                    Tile(TileType.EMPTY, enemy_x_grid + dx, y, SUB_TILE_SIZE),
                )

    enemy_tank = spawn_enemy_at(
        game_manager, enemy_x_grid, enemy_y_grid, direction=Direction.DOWN
    )
    # Move player out of the bullet path.
    place_player_at(game_manager, 0, 0)

    bullet = fire_bullet_from(game_manager, enemy_tank)
    assert bullet.active, "Enemy bullet spawned inactive."

    assert game_manager.state == GameState.RUNNING, (
        "Game should start in RUNNING state."
    )

    dt = 1.0 / FPS
    update_duration = 1.0
    num_updates = int(update_duration / dt)
    hit_processed = False

    for _ in range(num_updates):
        game_manager.update()
        if game_manager.state != GameState.RUNNING or not bullet.active:
            hit_processed = True
            break

    assert hit_processed, (
        "Base destruction/collision was not processed within simulation time."
    )

    assert not bullet.active, "Enemy bullet should be inactive after hitting base."

    assert base_tile.type == TileType.BASE_DESTROYED, (
        f"Base tile type did not change to BASE_DESTROYED. Is: {base_tile.type.name}"
    )

    assert game_manager.state in (
        GameState.GAME_OVER,
        GameState.GAME_OVER_ANIMATION,
    ), (
        f"Game state did not change to GAME_OVER/GAME_OVER_ANIMATION. "
        f"Is: {game_manager.state.name}"
    )


def test_victory_condition(game_manager_fixture):
    """Test that game state changes to VICTORY when all enemies are gone
    and the total spawn count has reached the maximum."""
    game_manager = game_manager_fixture

    clear_enemies(game_manager, reset_total=False)
    game_manager.spawn_manager.total_enemy_spawns = (
        game_manager.spawn_manager.max_enemy_spawns
    )

    assert game_manager.state == GameState.RUNNING, (
        "Test setup assumes starting in RUNNING state."
    )

    game_manager.update()

    assert game_manager.state == GameState.VICTORY, (
        f"Game state did not change to VICTORY. Is: {game_manager.state.name}"
    )


def test_score_accumulates_on_enemy_kill(game_manager_fixture):
    """Test that score increases when the player destroys an enemy."""
    gm = game_manager_fixture
    assert gm.player_manager.score == 0

    for _ in range(60):
        gm.update()
        if gm.spawn_manager.enemy_tanks:
            break

    enemy = gm.spawn_manager.enemy_tanks[0]
    tank_type = enemy.tank_type
    expected_points = ENEMY_POINTS.get(tank_type, 0)

    player = first_player(gm)
    place_player_at(gm, float(enemy.x), float(enemy.y + TILE_SIZE + 10), player=player)
    player.direction = Direction.UP

    bullet = player.shoot()
    assert bullet is not None
    gm.player_manager._bullets.append(bullet)

    gm.spawn_manager.enemy_tanks = [enemy]
    gm.spawn_manager._pending_spawns = []

    # Enemy AI chooses random directions; freeze it so it can't dodge the bullet.
    enemy.health = 1
    enemy.speed = 0

    for _ in range(60):
        gm.update()
        if enemy not in gm.spawn_manager.enemy_tanks:
            break

    assert gm.player_manager.score == expected_points, (
        f"Expected score {expected_points} after killing {tank_type} enemy, "
        f"got {gm.player_manager.score}"
    )
