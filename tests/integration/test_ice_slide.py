"""Integration tests for ice tile slide physics.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pygame
import pytest
from src.core.tile import TileType
from src.managers.player_input import KEY_TO_DIRECTION
from src.utils.constants import (
    Direction,
    ICE_SLIDE_DISTANCE,
    SUB_TILE_SIZE,
)
from tests.integration.conftest import (
    first_player,
    place_player_at,
    spawn_enemy_with_ai,
    tick,
)

_DIRECTION_TO_KEY = {direction: key for key, direction in KEY_TO_DIRECTION.items()}


def _place_ice_patch(game, grid_x, grid_y, width=4, height=4):
    """Place a patch of ice tiles at the given sub-tile grid position."""
    for dy in range(height):
        for dx in range(width):
            tile = game.map.get_tile_at(grid_x + dx, grid_y + dy)
            if tile is not None:
                game.map.set_tile_type(tile, TileType.ICE)


def _set_input(game, direction):
    """Simulate holding exactly one direction key (or none)."""
    player_manager = game.player_manager
    for key in _DIRECTION_TO_KEY.values():
        player_manager.handle_event(pygame.event.Event(pygame.KEYUP, key=key))
    if direction is not None:
        player_manager.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=_DIRECTION_TO_KEY[direction])
        )


def _clear_input(game):
    """Release all direction keys."""
    _set_input(game, None)


def _steel_wall_right_of(game, tank):
    """Put a steel column one sub-tile to the right of ``tank``."""
    wall_x = int(tank.x // SUB_TILE_SIZE) + 3
    wall_y = int(tank.y // SUB_TILE_SIZE)
    for dy in range(2):
        game.map.set_tile_type(
            game.map.get_tile_at(wall_x, wall_y + dy), TileType.STEEL
        )


@pytest.fixture
def game(game_manager_fixture):
    gm = game_manager_fixture
    gm.spawn_manager.enemy_tanks.clear()
    gm.spawn_manager._pending_spawns.clear()
    gm.spawn_manager._spawn_queue.clear()
    return gm


class TestPlayerIceSlide:
    """Integration tests for player ice sliding."""

    @pytest.fixture
    def ice_game(self, game):
        """Game with player on a large ice patch."""
        _place_ice_patch(game, 4, 4, width=8, height=8)
        place_player_at(game, 6 * SUB_TILE_SIZE, 6 * SUB_TILE_SIZE)
        first_player(game).direction = Direction.UP
        return game

    def test_slide_on_key_release(self, ice_game):
        """Player slides when releasing keys on ice."""
        game = ice_game

        _set_input(game, Direction.UP)
        tick(game, 5)
        assert first_player(game).direction == Direction.UP

        _clear_input(game)
        tick(game)
        assert first_player(game).is_sliding is True
        assert first_player(game)._slide_direction == Direction.UP

        pos_before = first_player(game).y
        tick(game)
        assert first_player(game).y < pos_before, "Tank should slide UP (decreasing y)"

    def test_slide_on_perpendicular_direction_change(self, ice_game):
        """Player slides in old direction when changing to perpendicular."""
        game = ice_game

        _set_input(game, Direction.UP)
        tick(game, 5)

        _set_input(game, Direction.LEFT)
        tick(game)
        assert first_player(game).is_sliding is True, (
            "Tank should start sliding on perpendicular direction change"
        )
        assert first_player(game)._slide_direction == Direction.UP, (
            "Slide should be in the OLD direction (UP)"
        )

        pos_before_y = first_player(game).y
        tick(game)
        assert first_player(game).y < pos_before_y, (
            "Tank should continue moving UP during slide"
        )

    def test_slide_distance_approximately_one_tile(self, ice_game):
        """Slide covers approximately ICE_SLIDE_DISTANCE pixels."""
        game = ice_game

        first_player(game).direction = Direction.RIGHT
        _set_input(game, Direction.RIGHT)
        tick(game, 5)

        _clear_input(game)
        tick(game)
        pos_before = first_player(game).x

        for _ in range(120):
            tick(game)
            if not first_player(game).is_sliding:
                break

        distance = first_player(game).x - pos_before
        assert abs(distance - ICE_SLIDE_DISTANCE) < 2.0, (
            f"Slide distance {distance:.1f} should be ~{ICE_SLIDE_DISTANCE}"
        )

    def test_no_slide_when_not_on_ice(self, game):
        """Player does NOT slide on normal tiles."""
        _set_input(game, Direction.RIGHT)
        tick(game, 5)
        _clear_input(game)
        tick(game)

        assert first_player(game).is_sliding is False

    def test_slide_cancelled_by_wall(self, ice_game):
        """Slide stops when tank hits a wall/obstacle."""
        game = ice_game

        px = first_player(game).x
        py = first_player(game).y
        wall_grid_x = int(px // SUB_TILE_SIZE) + 2
        wall_grid_y = int(py // SUB_TILE_SIZE)
        for dy in range(2):
            tile = game.map.get_tile_at(wall_grid_x, wall_grid_y + dy)
            if tile is not None:
                game.map.set_tile_type(tile, TileType.BRICK)

        first_player(game).direction = Direction.RIGHT
        _set_input(game, Direction.RIGHT)
        tick(game, 3)
        _clear_input(game)

        for _ in range(60):
            tick(game)
            if not first_player(game).is_sliding:
                break

        assert first_player(game).is_sliding is False, (
            "Slide should have been cancelled"
        )

    def test_slide_on_opposite_direction(self, ice_game):
        """Player slides when pressing opposite direction on ice."""
        game = ice_game

        _set_input(game, Direction.UP)
        tick(game, 5)

        _set_input(game, Direction.DOWN)
        tick(game)
        assert first_player(game).is_sliding is True, (
            "Tank should slide when pressing opposite direction"
        )

        pos_before = first_player(game).y
        tick(game)
        assert first_player(game).y < pos_before, "Tank should continue sliding UP"

    def test_turn_after_hitting_a_wall_does_not_slide(self, ice_game):
        """A tank that has just run into something turns without sliding."""
        game = ice_game
        player = first_player(game)
        player.direction = Direction.RIGHT
        _steel_wall_right_of(game, player)
        _set_input(game, Direction.RIGHT)
        tick(game, 30)

        _set_input(game, Direction.UP)
        y_before = player.y
        tick(game)

        assert player.is_sliding is False
        assert player.direction == Direction.UP
        assert player.y < y_before


class TestEnemyIceSlide:
    """Enemies follow the same Slide rule as Players."""

    @pytest.fixture
    def enemy_on_ice(self, game):
        _place_ice_patch(game, 4, 4, width=8, height=8)
        return spawn_enemy_with_ai(
            game, 6, 6, direction=Direction.RIGHT, fires=False, turns=False
        )

    def test_turn_on_arrival_frame_slides(self, game, enemy_on_ice):
        """The ice flag comes from where the Enemy stands, not last frame."""
        enemy, ai = enemy_on_ice
        # It drove onto this ice: this is its first frame here.
        enemy._moving_this_frame = True
        # A turn falls due this frame, and only DOWN is open.
        ai.direction_timer = ai.direction_change_interval
        ai._blocked_directions = {Direction.UP, Direction.RIGHT}

        tick(game)

        assert enemy.is_sliding is True
        assert enemy._slide_direction == Direction.RIGHT

    def test_turns_once_the_slide_ends(self, game, enemy_on_ice):
        enemy, ai = enemy_on_ice
        enemy._moving_this_frame = True
        ai.direction_timer = ai.direction_change_interval
        ai._blocked_directions = {Direction.UP, Direction.RIGHT}
        x_before = enemy.x

        for _ in range(120):
            tick(game)
            if not enemy.is_sliding:
                break

        assert abs(enemy.x - x_before - ICE_SLIDE_DISTANCE) < 2.0
        tick(game)
        assert enemy.direction == Direction.DOWN

    def test_turn_after_hitting_a_wall_does_not_slide(self, game, enemy_on_ice):
        """A tank that has just run into something turns without sliding."""
        enemy, _ = enemy_on_ice
        _steel_wall_right_of(game, enemy)

        slid = False
        for _ in range(60):
            tick(game)
            slid = slid or enemy.is_sliding
            if enemy.direction != Direction.RIGHT:
                break

        assert slid is False
        assert enemy.direction in (Direction.UP, Direction.DOWN)
