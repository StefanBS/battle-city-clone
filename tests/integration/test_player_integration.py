import pytest
import pygame
from loguru import logger
from src.managers.game_manager import GameManager
from src.utils.constants import (
    Direction,
    FPS,
    OwnerType,
    SUB_TILE_SIZE,
    BULLET_WIDTH,
    BULLET_HEIGHT,
)
from src.core.tile import Tile, TileType
from tests.integration.conftest import first_player, send_event, tick_for


@pytest.mark.parametrize(
    "key, axis, direction_sign, expected_direction",
    [
        (pygame.K_UP, 1, -1, Direction.UP),
        (pygame.K_DOWN, 1, 1, Direction.DOWN),
        (pygame.K_LEFT, 0, -1, Direction.LEFT),
        (pygame.K_RIGHT, 0, 1, Direction.RIGHT),
    ],
)
def test_player_movement(key, axis, direction_sign, expected_direction):
    """Test player tank movement and direction in all four directions."""
    game_manager = GameManager()
    game_manager._reset_game()
    player_tank = first_player(game_manager)
    game_map = game_manager.map

    start_grid_x, start_grid_y = 16, 16
    new_x = start_grid_x * SUB_TILE_SIZE
    new_y = start_grid_y * SUB_TILE_SIZE

    # Tank is 2x2 sub-tiles, so clear a wider area to allow movement in any direction.
    for dy in range(-2, 4):
        for dx in range(-2, 4):
            nx, ny = start_grid_x + dx, start_grid_y + dy
            if 0 <= nx < game_map.width and 0 <= ny < game_map.height:
                tile = game_map.get_tile_at(nx, ny)
                if tile and tile.type != TileType.EMPTY:
                    game_map.place_tile(
                        nx, ny, Tile(TileType.EMPTY, nx, ny, SUB_TILE_SIZE)
                    )

    player_tank.set_position(new_x, new_y)
    player_tank.prev_x, player_tank.prev_y = new_x, new_y

    initial_pos = player_tank.get_position()

    send_event(game_manager, pygame.event.Event(pygame.KEYDOWN, key=key))
    tick_for(game_manager, 0.2)
    send_event(game_manager, pygame.event.Event(pygame.KEYUP, key=key))

    final_pos = player_tank.get_position()

    assert final_pos != initial_pos

    if direction_sign == -1:
        assert final_pos[axis] < initial_pos[axis]
    else:
        assert final_pos[axis] > initial_pos[axis]

    assert player_tank.direction == expected_direction


@pytest.mark.parametrize(
    "blocking_tile_type",
    [
        TileType.STEEL,
        TileType.WATER,
    ],
)
@pytest.mark.parametrize(
    "move_direction, key, start_pos_offset",
    [
        (Direction.UP, pygame.K_UP, (0, 1)),
        (Direction.DOWN, pygame.K_DOWN, (0, -1)),
        (Direction.LEFT, pygame.K_LEFT, (1, 0)),
        (Direction.RIGHT, pygame.K_RIGHT, (-1, 0)),
    ],
)
def test_player_movement_blocked_by_tile(
    game_manager_fixture, blocking_tile_type, move_direction, key, start_pos_offset
):
    """Test player tank movement is blocked by specific tile types."""
    game_manager = game_manager_fixture
    player_tank = first_player(game_manager)
    game_map = game_manager.map

    # Target location (14,14) is clear of default map obstacles.
    target_x_grid = 14
    target_y_grid = 14

    if (
        0 <= target_y_grid + 1 < game_map.height
        and 0 <= target_x_grid + 1 < game_map.width
    ):
        for dy in range(2):
            for dx in range(2):
                sx, sy = target_x_grid + dx, target_y_grid + dy
                tile = Tile(
                    blocking_tile_type,
                    sx,
                    sy,
                    SUB_TILE_SIZE,
                    blocks_tanks=True,
                    blocks_bullets=True,
                )
                game_map.place_tile(sx, sy, tile)
        logger.debug(
            f"Placed {blocking_tile_type.name} 2x2 block at "
            f"({target_x_grid}, {target_y_grid})"
        )
    else:
        pytest.fail(
            f"Target tile coordinates ({target_x_grid}, {target_y_grid}) "
            f"are out of bounds."
        )

    # start_pos_offset is in tile-size units (2 sub-tiles each), so the tank
    # sits flush against the 2x2 block.
    start_grid_x = target_x_grid + start_pos_offset[0] * 2
    start_grid_y = target_y_grid + start_pos_offset[1] * 2
    start_x = start_grid_x * SUB_TILE_SIZE
    start_y = start_grid_y * SUB_TILE_SIZE

    if not (0 <= start_grid_y < game_map.height and 0 <= start_grid_x < game_map.width):
        pytest.skip(
            f"Calculated start position ({start_grid_x}, {start_grid_y}) is out of "
            f"bounds for target ({target_x_grid}, {target_y_grid}). Skipping."
        )

    for dy in range(2):
        for dx in range(2):
            sx, sy = start_grid_x + dx, start_grid_y + dy
            if 0 <= sx < game_map.width and 0 <= sy < game_map.height:
                game_map.place_tile(
                    sx,
                    sy,
                    Tile(TileType.EMPTY, sx, sy, SUB_TILE_SIZE),
                )
    logger.debug(f"Set player starting area ({start_grid_x}, {start_grid_y}) to EMPTY.")

    player_tank.set_position(start_x, start_y)
    player_tank.prev_x, player_tank.prev_y = start_x, start_y
    initial_player_rect = pygame.Rect(
        round(start_x), round(start_y), player_tank.width, player_tank.height
    )

    send_event(game_manager, pygame.event.Event(pygame.KEYDOWN, key=key))
    tick_for(game_manager, 0.2)
    send_event(game_manager, pygame.event.Event(pygame.KEYUP, key=key))

    final_player_rect = player_tank.rect
    colliding_tile_rect = pygame.Rect(
        target_x_grid * SUB_TILE_SIZE,
        target_y_grid * SUB_TILE_SIZE,
        SUB_TILE_SIZE * 2,
        SUB_TILE_SIZE * 2,
    )

    # Float positions can drift; compare rounded rects for exact flush alignment.
    expected_message_base = (
        f"Tank not properly snapped to {blocking_tile_type.name} "
        f"when moving {move_direction}. Player Rect: {final_player_rect}, "
        f"Tile Rect: {colliding_tile_rect}."
    )

    if move_direction == Direction.RIGHT:
        assert final_player_rect.right == colliding_tile_rect.left, (
            f"{expected_message_base} Expected player.right == tile.left."
        )
        assert final_player_rect.top == initial_player_rect.top, (
            f"{expected_message_base} Player y-position changed unexpectedly. "
            f"Expected top {initial_player_rect.top}, got {final_player_rect.top}."
        )
    elif move_direction == Direction.LEFT:
        assert final_player_rect.left == colliding_tile_rect.right, (
            f"{expected_message_base} Expected player.left == tile.right."
        )
        assert final_player_rect.top == initial_player_rect.top, (
            f"{expected_message_base} Player y-position changed unexpectedly. "
            f"Expected top {initial_player_rect.top}, got {final_player_rect.top}."
        )
    elif move_direction == Direction.DOWN:
        assert final_player_rect.bottom == colliding_tile_rect.top, (
            f"{expected_message_base} Expected player.bottom == tile.top."
        )
        assert final_player_rect.left == initial_player_rect.left, (
            f"{expected_message_base} Player x-position changed unexpectedly. "
            f"Expected left {initial_player_rect.left}, got {final_player_rect.left}."
        )
    elif move_direction == Direction.UP:
        assert final_player_rect.top == colliding_tile_rect.bottom, (
            f"{expected_message_base} Expected player.top == tile.bottom."
        )
        assert final_player_rect.left == initial_player_rect.left, (
            f"{expected_message_base} Player x-position changed unexpectedly. "
            f"Expected left {initial_player_rect.left}, got {final_player_rect.left}."
        )
    else:
        pytest.fail(f"Unknown move_direction: {move_direction}")

    assert player_tank.direction == move_direction, (
        f"Tank direction incorrect when blocked by {blocking_tile_type.name}. "
        f"Expected {move_direction}, got {player_tank.direction}"
    )


def test_player_shooting():
    """Test player shooting mechanics."""
    game_manager = GameManager()
    game_manager._reset_game()
    player_tank = first_player(game_manager)

    assert len(game_manager.bullets) == 0, "No bullets should exist initially."

    player_tank.direction = Direction.RIGHT
    game_manager._try_shoot(player_tank)

    assert len(game_manager.bullets) == 1, "One bullet should exist after shooting."
    bullet = game_manager.bullets[0]
    assert bullet.active, "Bullet should be active after shooting."
    assert bullet.direction == Direction.RIGHT, "Bullet direction is incorrect."
    assert bullet.owner_type == OwnerType.PLAYER, "Bullet owner type is incorrect."
    assert bullet.owner is player_tank, "Bullet owner should be the player tank."

    expected_x = player_tank.x + player_tank.width // 2 - BULLET_WIDTH // 2
    expected_y = player_tank.y + player_tank.height // 2 - BULLET_HEIGHT // 2
    actual_pos = bullet.get_position()
    assert actual_pos == (expected_x, expected_y), (
        f"Bullet spawn position incorrect. Expected ({expected_x}, {expected_y}), "
        f"got {actual_pos}"
    )

    # One-bullet-per-tank limit: firing again while the first is active is a no-op.
    game_manager._try_shoot(player_tank)

    assert len(game_manager.bullets) == 1, (
        "Firing again should not create a new bullet while the first is active."
    )
    assert game_manager.bullets[0] is bullet, "Original bullet should still be present."
    assert bullet.active, "Original bullet should still be active."


@pytest.mark.parametrize(
    "direction_str, axis_index, direction_sign",
    [
        (Direction.UP, 1, -1),
        (Direction.DOWN, 1, 1),
        (Direction.LEFT, 0, -1),
        (Direction.RIGHT, 0, 1),
    ],
)
def test_player_bullet_movement(direction_str, axis_index, direction_sign):
    """Test that the player's bullet moves correctly after firing."""
    game_manager = GameManager()
    game_manager._reset_game()
    player_tank = first_player(game_manager)

    player_tank.direction = direction_str
    game_manager._try_shoot(player_tank)

    assert len(game_manager.bullets) == 1, "Bullet failed to spawn."
    bullet = next(b for b in game_manager.bullets if b.owner is player_tank)
    assert bullet.active, "Bullet spawned but is not active."
    assert bullet.direction == direction_str, "Bullet has wrong direction."

    initial_pos = bullet.get_position()

    tick_for(game_manager, 0.1)

    final_pos = bullet.get_position()

    assert final_pos != initial_pos, f"Bullet did not move from {initial_pos}"

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

    other_axis_index = 1 - axis_index
    assert final_pos[other_axis_index] == initial_pos[other_axis_index], (
        f"Bullet moved unexpectedly along axis {other_axis_index}. "
        f"Start: {initial_pos[other_axis_index]}, End: {final_pos[other_axis_index]}"
    )


def test_player_respawn():
    """Test player respawn mechanics after taking lethal damage with lives remaining."""
    game_manager = GameManager()
    game_manager._reset_game()
    player_tank = first_player(game_manager)

    initial_lives = player_tank.lives
    initial_health = player_tank.health
    initial_max_health = player_tank.max_health
    spawn_pos = player_tank.initial_position

    assert initial_lives > 1, "Test requires player to start with more than 1 life."

    # Disable spawn invincibility so damage lands.
    player_tank.is_invincible = False

    # Call take_damage directly (rather than through the game loop) to isolate
    # the respawn logic from collision/bullet plumbing.
    was_destroyed_permanently = player_tank.take_damage(amount=initial_health)

    assert not was_destroyed_permanently, "Tank was permanently destroyed unexpectedly."

    # GameManager would call respawn() in the live loop; call it directly here.
    player_tank.respawn()

    assert player_tank.lives == initial_lives - 1, (
        f"Player lives did not decrease. Expected {initial_lives - 1}, "
        f"got {player_tank.lives}"
    )

    # take_damage() resets health when lives > 0; respawn() itself does not.
    assert player_tank.health == initial_max_health, (
        f"Player health not reset after taking damage. Expected {initial_max_health}, "
        f"got {player_tank.health}"
    )

    current_pos = player_tank.get_position()
    assert current_pos == spawn_pos, (
        f"Player did not respawn at initial position. Expected {spawn_pos}, "
        f"got {current_pos}"
    )

    assert player_tank.is_invincible, "Player should be invincible after respawning."
    assert player_tank.invincibility_timer == 0, "Invincibility timer should be reset."

    invincibility_duration = player_tank.invincibility_duration
    dt = 1.0 / FPS
    num_updates_to_exceed_duration = int(invincibility_duration / dt) + 2

    for i in range(num_updates_to_exceed_duration):
        if not player_tank.is_invincible and i * dt < invincibility_duration:
            logger.warning(
                f"Invincibility wore off early at frame {i + 1} ({i * dt:.2f}s)"
            )
            break
        game_manager.update()

        if not player_tank.is_invincible:
            logger.info(
                f"Invincibility wore off as expected at frame {i + 1} ({i * dt:.2f}s)"
            )
            break

    assert not player_tank.is_invincible, "Player invincibility did not wear off."
