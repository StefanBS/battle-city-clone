import pytest
from src.utils.constants import Direction, FPS, SUB_TILE_SIZE
from src.states.game_state import GameState
from src.core.tile import BrickVariant, Tile, TileDefaults, TileType
from tests.integration.conftest import (
    clear_tiles,
    fire_bullet_from,
    first_player,
    place_player_at,
    spawn_enemy_at,
)


@pytest.mark.parametrize(
    "tile_to_place, expected_bullet_active, expected_tile_type",
    [
        (TileType.BRICK, False, TileType.BRICK),
        (TileType.STEEL, False, TileType.STEEL),
        (TileType.WATER, True, TileType.WATER),
        (TileType.BUSH, True, TileType.BUSH),
    ],
)
def test_player_bullet_vs_tile(
    game_manager_fixture,
    tile_to_place,
    expected_bullet_active,
    expected_tile_type,
):
    """Test player bullet interaction with various tile types."""
    game_manager = game_manager_fixture
    player_tank = first_player(game_manager)
    game_map = game_manager.map

    target_x_grid = 14
    target_y_grid = 20

    if 0 <= target_y_grid < game_map.height and 0 <= target_x_grid < game_map.width:
        defaults = game_map._tile_collision_defaults.get(tile_to_place, TileDefaults())
        target_tile = Tile(
            tile_to_place,
            target_x_grid,
            target_y_grid,
            SUB_TILE_SIZE,
            blocks_tanks=defaults.blocks_tanks,
            blocks_bullets=defaults.blocks_bullets,
            is_destructible=defaults.is_destructible,
            is_overlay=defaults.is_overlay,
            is_slidable=defaults.is_slidable,
        )
        game_map.place_tile(target_x_grid, target_y_grid, target_tile)
    else:
        pytest.fail(
            f"Target tile coordinates ({target_x_grid}, {target_y_grid}) "
            f"are out of bounds."
        )

    # Clear 2 sub-tiles wide (bullet path) for 4 sub-tiles deep (target + player area),
    # skipping the target itself.
    clear_tiles(
        game_map,
        [
            (target_x_grid + dx, y)
            for y in range(target_y_grid, target_y_grid + 4)
            for dx in range(2)
            if not (dx == 0 and y == target_y_grid)
        ],
    )

    # Player below target (2 sub-tiles = 1 tank height).
    place_player_at(
        game_manager,
        target_x_grid * SUB_TILE_SIZE,
        (target_y_grid + 2) * SUB_TILE_SIZE,
        player=player_tank,
    )

    player_tank.direction = Direction.UP
    bullet = player_tank.shoot()
    assert bullet is not None, "Bullet failed to spawn."
    game_manager.player_manager._bullets.append(bullet)

    dt = 1.0 / FPS
    update_duration = 0.2
    num_updates = int(update_duration / dt)

    for _ in range(num_updates):
        game_manager.update()
        if not expected_bullet_active and not bullet.active:
            break

    assert bullet.active == expected_bullet_active, (
        f"Bullet active state mismatch for {tile_to_place.name}. "
        f"Expected: {expected_bullet_active}, Got: {bullet.active}"
    )

    final_tile = game_map.get_tile_at(target_x_grid, target_y_grid)
    assert final_tile is not None, "Target tile somehow disappeared."
    assert final_tile.type == expected_tile_type, (
        f"Tile type mismatch for {tile_to_place.name}. "
        f"Expected: {expected_tile_type.name}, Got: {final_tile.type.name}"
    )
    if tile_to_place == TileType.BRICK:
        damaged = (
            final_tile.type == TileType.EMPTY
            or final_tile.brick_variant != BrickVariant.FULL
        )
        assert damaged, "Brick should be damaged or destroyed after being hit."


def test_player_bullet_destroys_enemy_tank(game_manager_fixture, mocker):
    """Test player bullet hitting and destroying a basic enemy tank."""
    mocker.patch("src.core.enemy_tank.random.uniform", return_value=0.0)
    game_manager = game_manager_fixture
    player_tank = first_player(game_manager)

    enemy_x_grid = 14
    enemy_y_grid = 10

    # Clear enemy + player (2 sub-tiles each = 4 total) across 2 columns.
    clear_tiles(
        game_manager.map,
        [(enemy_x_grid + dx, enemy_y_grid + dy) for dy in range(4) for dx in range(2)],
    )

    enemy_tank = spawn_enemy_at(game_manager, enemy_x_grid, enemy_y_grid)
    # Prevent enemy shooting so its bullets don't interfere with the player bullet.
    enemy_tank.shoot = lambda: None
    initial_enemy_count = len(game_manager.spawn_manager.enemy_tanks)

    # Player below enemy (2 sub-tiles = 1 tank height).
    place_player_at(
        game_manager,
        enemy_x_grid * SUB_TILE_SIZE,
        (enemy_y_grid + 2) * SUB_TILE_SIZE,
        player=player_tank,
    )

    player_tank.direction = Direction.UP
    bullet = player_tank.shoot()
    assert bullet is not None, "Bullet failed to spawn."
    game_manager.player_manager._bullets.append(bullet)

    dt = 1.0 / FPS
    max_simulation_time = 0.5
    max_updates = int(max_simulation_time / dt)
    bullet_became_inactive_during_loop = False

    for _ in range(max_updates):
        game_manager.update()
        if not bullet.active:
            bullet_became_inactive_during_loop = True
            break
        if enemy_tank not in game_manager.spawn_manager.enemy_tanks:
            if not bullet.active:
                bullet_became_inactive_during_loop = True
            break

    if enemy_tank in game_manager.spawn_manager.enemy_tanks:
        assert bullet_became_inactive_during_loop, (
            "Bullet remained active but enemy was not destroyed."
        )

    assert enemy_tank not in game_manager.spawn_manager.enemy_tanks, (
        "Enemy tank was not removed after being hit."
    )
    assert len(game_manager.spawn_manager.enemy_tanks) == initial_enemy_count - 1, (
        "Enemy count did not decrease by one."
    )


@pytest.mark.parametrize(
    "player_initial_lives, player_is_invincible, expected_game_state, "
    "expected_player_lives_after_hit",
    [
        (1, False, GameState.GAME_OVER_ANIMATION, 0),
        (3, False, GameState.RUNNING, 2),
        (3, True, GameState.RUNNING, 3),
    ],
)
def test_enemy_bullet_hits_player_tank(
    game_manager_fixture,
    player_initial_lives,
    player_is_invincible,
    expected_game_state,
    expected_player_lives_after_hit,
    mocker,
):
    """Test enemy bullet hitting the player tank under different conditions."""
    mocker.patch("src.core.enemy_tank.random.uniform", return_value=0.0)
    game_manager = game_manager_fixture
    player_tank = first_player(game_manager)
    initial_spawn_pos = player_tank.initial_position

    player_tank.lives = player_initial_lives
    player_tank.is_invincible = player_is_invincible
    player_tank.invincibility_timer = 0

    player_x_grid = int(player_tank.x // SUB_TILE_SIZE)
    player_y_grid = int(player_tank.y // SUB_TILE_SIZE)
    enemy_x_grid = player_x_grid
    # 4 sub-tiles (= 2 tank heights) above the player.
    enemy_y_grid = player_y_grid - 4

    if not (
        0 <= enemy_y_grid < game_manager.map.height
        and 0 <= enemy_x_grid < game_manager.map.width
    ):
        pytest.skip(
            f"Calculated enemy position ({enemy_x_grid}, {enemy_y_grid}) "
            f"is out of bounds. Skipping."
        )

    clear_tiles(
        game_manager.map,
        [
            (enemy_x_grid + dx, y)
            for y in range(enemy_y_grid, player_y_grid + 2)
            for dx in range(2)
        ],
    )

    enemy_tank = spawn_enemy_at(
        game_manager, enemy_x_grid, enemy_y_grid, direction=Direction.DOWN
    )

    enemy_bullet = fire_bullet_from(game_manager, enemy_tank)
    assert enemy_bullet.active, "Enemy bullet spawned inactive."

    dt = 1.0 / FPS
    max_simulation_time = 0.6
    max_updates = int(max_simulation_time / dt)
    interaction_processed = False

    original_player_lives = player_tank.lives

    for i in range(max_updates):
        game_manager.update()

        current_lives = player_tank.lives
        current_state = game_manager.state

        if not player_is_invincible:
            if not enemy_bullet.active:
                interaction_processed = True
                break
            if current_lives < original_player_lives:
                interaction_processed = True
                break
            if current_state in (
                GameState.GAME_OVER,
                GameState.GAME_OVER_ANIMATION,
            ) and expected_game_state in (
                GameState.GAME_OVER,
                GameState.GAME_OVER_ANIMATION,
            ):
                interaction_processed = True
                break
        else:
            if i == max_updates - 1:
                interaction_processed = True
                break

        if current_state != GameState.RUNNING and current_state != expected_game_state:
            interaction_processed = True
            break
    else:
        interaction_processed = True

    if not player_is_invincible:
        assert interaction_processed, (
            f"Enemy bullet interaction with vulnerable player not detected. "
            f"Bullet active: {enemy_bullet.active}, Player lives: {player_tank.lives}, "
            f"Game state: {game_manager.state.name}"
        )
        if player_tank.lives < original_player_lives or game_manager.state in (
            GameState.GAME_OVER,
            GameState.GAME_OVER_ANIMATION,
        ):
            assert not enemy_bullet.active, (
                "Enemy bullet should be inactive after "
                "damaging player or causing game over."
            )

    assert game_manager.state == expected_game_state, (
        f"Expected game state {expected_game_state.name}, "
        f"but got {game_manager.state.name}"
    )

    assert player_tank.lives == expected_player_lives_after_hit, (
        f"Expected player lives {expected_player_lives_after_hit}, "
        f"but got {player_tank.lives}"
    )

    if (
        expected_player_lives_after_hit == player_initial_lives - 1
        and expected_game_state == GameState.RUNNING
    ):
        assert player_tank.get_position() == initial_spawn_pos, (
            "Player did not return to spawn position after losing a life."
        )
        assert player_tank.is_invincible, "Player is not invincible after respawning."
    elif player_is_invincible:
        assert player_tank.is_invincible, (
            "Player lost invincibility after being hit while invincible."
        )


def test_enemy_bullet_hits_other_enemy(game_manager_fixture, mocker):
    """Test that an enemy bullet has no effect on another enemy tank."""
    mocker.patch("src.core.enemy_tank.random.uniform", return_value=0.0)
    game_manager = game_manager_fixture

    # enemy1 shoots down at enemy2 (4 sub-tiles apart).
    enemy1_x_grid, enemy1_y_grid = 16, 16
    enemy2_x_grid, enemy2_y_grid = 16, 20

    clear_tiles(
        game_manager.map,
        [(16 + dx, y) for y in range(16, 22) for dx in range(2)],
    )

    enemy1 = spawn_enemy_at(
        game_manager, enemy1_x_grid, enemy1_y_grid, direction=Direction.DOWN
    )
    enemy2 = spawn_enemy_at(game_manager, enemy2_x_grid, enemy2_y_grid, replace=False)

    initial_enemy_count = len(game_manager.spawn_manager.enemy_tanks)
    initial_enemy2_health = enemy2.health

    bullet = fire_bullet_from(game_manager, enemy1)
    assert bullet.active, "Enemy1 bullet spawned inactive."

    dt = 1.0 / FPS
    update_duration = 0.4
    num_updates = int(update_duration / dt)

    initial_bullet_state = bullet.active

    for _ in range(num_updates):
        game_manager.update()
        if not bullet.active:
            break

    assert bullet.active == initial_bullet_state, "Bullet state changed unexpectedly."
    assert bullet.active, "Bullet should still be active after passing another enemy."

    assert enemy2.health == initial_enemy2_health, (
        f"Enemy2 health changed. Expected: {initial_enemy2_health}, "
        f"Got: {enemy2.health}"
    )

    assert enemy2 in game_manager.spawn_manager.enemy_tanks, (
        "Enemy2 was removed from the list."
    )

    assert len(game_manager.spawn_manager.enemy_tanks) == initial_enemy_count, (
        f"Enemy count changed. Expected: {initial_enemy_count}, "
        f"Got: {len(game_manager.spawn_manager.enemy_tanks)}"
    )


def test_player_tank_vs_enemy_tank_no_overlap(game_manager_fixture, mocker):
    """Test that a player tank driving into an enemy tank does not overlap."""
    mocker.patch("src.core.enemy_tank.random.uniform", return_value=0.0)
    game_manager = game_manager_fixture
    player_tank = first_player(game_manager)

    player_x_grid = int(player_tank.x // SUB_TILE_SIZE)
    player_y_grid = int(player_tank.y // SUB_TILE_SIZE)
    # 2 sub-tiles above = exactly adjacent (one tank-height gap).
    enemy_x_grid = player_x_grid
    enemy_y_grid = player_y_grid - 2

    clear_tiles(
        game_manager.map,
        [
            (enemy_x_grid + dx, y)
            for y in range(enemy_y_grid, player_y_grid + 2)
            for dx in range(2)
        ],
    )

    enemy_tank = spawn_enemy_at(game_manager, enemy_x_grid, enemy_y_grid)
    # Pin the enemy so only the player moves; we want to test the collision, not AI.
    enemy_tank.speed = 0
    enemy_tank.direction_change_interval = 999
    enemy_tank.shoot_interval = 999

    dt = 1.0 / FPS
    for _ in range(30):
        player_tank.update(dt)
        player_tank.move(0, -1, dt)
        enemy_tank.update(dt)

        game_manager.collision_manager.check_collisions(
            player_tanks=[player_tank],
            player_bullets=[],
            enemy_tanks=[enemy_tank],
            enemy_bullets=[],
            tank_blocking_tiles=[],
            bullet_blocking_tiles=[],
            player_base=None,
        )
        events = game_manager.collision_manager.get_collision_events()
        game_manager.collision_response_handler.process_collisions(events)

    assert not player_tank.rect.colliderect(enemy_tank.rect), (
        f"Player rect {player_tank.rect} overlaps enemy rect {enemy_tank.rect}"
    )
    assert player_tank.rect.top >= enemy_tank.rect.bottom, (
        f"Player top ({player_tank.rect.top}) should be "
        f">= enemy bottom ({enemy_tank.rect.bottom})"
    )


def test_enemy_bullets_collide(game_manager_fixture, mocker):
    """Test that two enemy bullets pass through each other."""
    mocker.patch("src.core.enemy_tank.random.uniform", return_value=0.0)
    game_manager = game_manager_fixture

    enemy1_x_grid, enemy1_y_grid = 2, 16
    enemy2_x_grid, enemy2_y_grid = 8, 16

    clear_tiles(
        game_manager.map,
        [(x, 16 + dy) for x in range(2, 10) for dy in range(2)],
    )

    enemy1 = spawn_enemy_at(
        game_manager, enemy1_x_grid, enemy1_y_grid, direction=Direction.RIGHT
    )
    enemy2 = spawn_enemy_at(
        game_manager,
        enemy2_x_grid,
        enemy2_y_grid,
        direction=Direction.LEFT,
        replace=False,
    )

    bullet1 = fire_bullet_from(game_manager, enemy1)
    bullet2 = fire_bullet_from(game_manager, enemy2)
    assert bullet1.active, "Enemy1 bullet spawned inactive."
    assert bullet2.active, "Enemy2 bullet spawned inactive."

    # Enemies are 6 sub-tiles apart; bullets need to cross before we check pass-through.
    dt = 1.0 / FPS
    update_duration = 0.4
    num_updates = int(update_duration / dt)

    for _ in range(num_updates):
        game_manager.update()
        if not (bullet1.active and bullet2.active):
            break

    assert bullet1.active, (
        "Enemy1 bullet should still be active after passing enemy2 bullet."
    )
    assert bullet2.active, (
        "Enemy2 bullet should still be active after passing enemy1 bullet."
    )
