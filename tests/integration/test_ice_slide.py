"""Integration tests for ice tile slide physics.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pygame
import pytest
from src.core.tile import TileType
from src.battle.player_input import KEY_TO_DIRECTION
from src.utils.constants import (
    Direction,
    ICE_SLIDE_DISTANCE,
    SUB_TILE_SIZE,
)
from tests.integration.conftest import (
    clear_enemies,
    first_player,
    place_ice_patch,
    place_player_at,
    spawn_enemy_with_ai,
    tick,
)

_DIRECTION_TO_KEY = {direction: key for key, direction in KEY_TO_DIRECTION.items()}


def _set_input(battle, direction):
    """Simulate holding exactly one direction key (or none)."""
    for key in _DIRECTION_TO_KEY.values():
        battle.handle_event(pygame.event.Event(pygame.KEYUP, key=key))
    if direction is not None:
        battle.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=_DIRECTION_TO_KEY[direction])
        )


def _clear_input(battle):
    """Release all direction keys."""
    _set_input(battle, None)


def _steel_wall_right_of(battle, tank):
    """Put a steel column one sub-tile to the right of ``tank``."""
    wall_x = int(tank.x // SUB_TILE_SIZE) + 3
    wall_y = int(tank.y // SUB_TILE_SIZE)
    for dy in range(2):
        battle.map.set_tile_type(
            battle.map.get_tile_at(wall_x, wall_y + dy), TileType.STEEL
        )


@pytest.fixture(autouse=True)
def no_enemies(battle):
    """No Enemies on the Battle's battlefield."""
    clear_enemies(battle)


class TestPlayerIceSlide:
    """Integration tests for player ice sliding."""

    @pytest.fixture
    def ice_game(self, battle):
        """A Battle with the player on a large ice patch."""
        place_ice_patch(battle, 4, 4, width=8, height=8)
        place_player_at(battle, 6 * SUB_TILE_SIZE, 6 * SUB_TILE_SIZE)
        first_player(battle).direction = Direction.UP
        return battle

    def test_slide_on_key_release(self, ice_game):
        """Player slides when releasing keys on ice."""
        battle = ice_game

        _set_input(battle, Direction.UP)
        tick(battle, 5)
        assert first_player(battle).direction == Direction.UP

        _clear_input(battle)
        tick(battle)
        assert first_player(battle).is_sliding is True
        assert first_player(battle)._slide_direction == Direction.UP

        pos_before = first_player(battle).y
        tick(battle)
        assert first_player(battle).y < pos_before, (
            "Tank should slide UP (decreasing y)"
        )

    def test_slide_on_perpendicular_direction_change(self, ice_game):
        """Player slides in old direction when changing to perpendicular."""
        battle = ice_game

        _set_input(battle, Direction.UP)
        tick(battle, 5)

        _set_input(battle, Direction.LEFT)
        tick(battle)
        assert first_player(battle).is_sliding is True, (
            "Tank should start sliding on perpendicular direction change"
        )
        assert first_player(battle)._slide_direction == Direction.UP, (
            "Slide should be in the OLD direction (UP)"
        )

        pos_before_y = first_player(battle).y
        tick(battle)
        assert first_player(battle).y < pos_before_y, (
            "Tank should continue moving UP during slide"
        )

    def test_slide_distance_approximately_one_tile(self, ice_game):
        """Slide covers approximately ICE_SLIDE_DISTANCE pixels."""
        battle = ice_game

        first_player(battle).direction = Direction.RIGHT
        _set_input(battle, Direction.RIGHT)
        tick(battle, 5)

        _clear_input(battle)
        tick(battle)
        pos_before = first_player(battle).x

        for _ in range(120):
            tick(battle)
            if not first_player(battle).is_sliding:
                break

        distance = first_player(battle).x - pos_before
        assert abs(distance - ICE_SLIDE_DISTANCE) < 2.0, (
            f"Slide distance {distance:.1f} should be ~{ICE_SLIDE_DISTANCE}"
        )

    def test_no_slide_when_not_on_ice(self, battle):
        """Player does NOT slide on normal tiles."""
        _set_input(battle, Direction.RIGHT)
        tick(battle, 5)
        _clear_input(battle)
        tick(battle)

        assert first_player(battle).is_sliding is False

    def test_slide_cancelled_by_wall(self, ice_game):
        """Slide stops when tank hits a wall/obstacle."""
        battle = ice_game

        px = first_player(battle).x
        py = first_player(battle).y
        wall_grid_x = int(px // SUB_TILE_SIZE) + 2
        wall_grid_y = int(py // SUB_TILE_SIZE)
        for dy in range(2):
            tile = battle.map.get_tile_at(wall_grid_x, wall_grid_y + dy)
            if tile is not None:
                battle.map.set_tile_type(tile, TileType.BRICK)

        first_player(battle).direction = Direction.RIGHT
        _set_input(battle, Direction.RIGHT)
        tick(battle, 3)
        _clear_input(battle)

        for _ in range(60):
            tick(battle)
            if not first_player(battle).is_sliding:
                break

        assert first_player(battle).is_sliding is False, (
            "Slide should have been cancelled"
        )

    def test_slide_on_opposite_direction(self, ice_game):
        """Player slides when pressing opposite direction on ice."""
        battle = ice_game

        _set_input(battle, Direction.UP)
        tick(battle, 5)

        _set_input(battle, Direction.DOWN)
        tick(battle)
        assert first_player(battle).is_sliding is True, (
            "Tank should slide when pressing opposite direction"
        )

        pos_before = first_player(battle).y
        tick(battle)
        assert first_player(battle).y < pos_before, "Tank should continue sliding UP"

    def test_turn_after_hitting_a_wall_does_not_slide(self, ice_game):
        """A tank that has just run into something turns without sliding."""
        battle = ice_game
        player = first_player(battle)
        player.direction = Direction.RIGHT
        _steel_wall_right_of(battle, player)
        _set_input(battle, Direction.RIGHT)
        tick(battle, 30)

        _set_input(battle, Direction.UP)
        y_before = player.y
        tick(battle)

        assert player.is_sliding is False
        assert player.direction == Direction.UP
        assert player.y < y_before


class TestEnemyIceSlide:
    """Enemies follow the same Slide rule as Players."""

    @pytest.fixture
    def enemy_on_ice(self, battle):
        place_ice_patch(battle, 4, 4, width=8, height=8)
        return spawn_enemy_with_ai(
            battle, 6, 6, direction=Direction.RIGHT, fires=False, turns=False
        )

    def test_turn_on_arrival_frame_slides(self, battle, enemy_on_ice):
        """The ice flag comes from where the Enemy stands, not last frame."""
        enemy, ai = enemy_on_ice
        # It drove onto this ice: this is its first frame here.
        enemy._moving_this_frame = True
        # A turn falls due this frame, and only DOWN is open.
        ai.direction_timer = ai.direction_change_interval
        ai._blocked_directions = {Direction.UP, Direction.RIGHT}

        tick(battle)

        assert enemy.is_sliding is True
        assert enemy._slide_direction == Direction.RIGHT

    def test_turns_once_the_slide_ends(self, battle, enemy_on_ice):
        enemy, ai = enemy_on_ice
        enemy._moving_this_frame = True
        ai.direction_timer = ai.direction_change_interval
        ai._blocked_directions = {Direction.UP, Direction.RIGHT}
        x_before = enemy.x

        for _ in range(120):
            tick(battle)
            if not enemy.is_sliding:
                break

        assert abs(enemy.x - x_before - ICE_SLIDE_DISTANCE) < 2.0
        tick(battle)
        assert enemy.direction == Direction.DOWN

    def test_turn_after_hitting_a_wall_does_not_slide(self, battle, enemy_on_ice):
        """A tank that has just run into something turns without sliding."""
        enemy, _ = enemy_on_ice
        _steel_wall_right_of(battle, enemy)

        slid = False
        for _ in range(60):
            tick(battle)
            slid = slid or enemy.is_sliding
            if enemy.direction != Direction.RIGHT:
                break

        assert slid is False
        assert enemy.direction in (Direction.UP, Direction.DOWN)
