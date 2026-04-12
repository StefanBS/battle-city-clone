"""Integration tests for ice tile slide physics.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.core.tile import TileType
from src.managers.player_input import CombinedInput
from src.utils.constants import (
    Direction,
    ICE_SLIDE_DISTANCE,
    SUB_TILE_SIZE,
)


def _place_ice_patch(game, grid_x, grid_y, width=4, height=4):
    """Place a patch of ice tiles at the given sub-tile grid position."""
    for dy in range(height):
        for dx in range(width):
            tile = game.map.get_tile_at(grid_x + dx, grid_y + dy)
            if tile is not None:
                game.map.set_tile_type(tile, TileType.ICE)


def _move_player_to(game, px, py):
    """Teleport the player tank to a pixel position."""
    game.player_tank.x = float(px)
    game.player_tank.y = float(py)
    game.player_tank.prev_x = float(px)
    game.player_tank.prev_y = float(py)
    game.player_tank.rect.topleft = (round(px), round(py))


def _set_input(game, direction):
    """Set player input to simulate holding a direction key."""
    player_input = game.player_manager._player_inputs[0]
    # 1P wraps keyboard + controller in a CombinedInput; the KeyboardInput
    # is always first (see PlayerManager._one_player_inputs).
    kb = (
        player_input._inputs[0]
        if isinstance(player_input, CombinedInput)
        else player_input
    )
    for d in kb._directions:
        kb._directions[d] = False
    if direction is not None:
        kb._directions[direction] = True


def _clear_input(game):
    """Release all direction keys."""
    _set_input(game, None)


def _tick(game, n=1):
    """Run n update frames."""
    for _ in range(n):
        game.update()


class TestPlayerIceSlide:
    """Integration tests for player ice sliding."""

    @pytest.fixture
    def game(self, game_manager_fixture):
        gm = game_manager_fixture
        # Remove enemies so they don't interfere
        gm.spawn_manager.enemy_tanks.clear()
        gm.spawn_manager._pending_spawns.clear()
        gm.spawn_manager._spawn_queue.clear()
        return gm

    @pytest.fixture
    def ice_game(self, game):
        """Game with player on a large ice patch."""
        # Place ice at sub-tile grid (4,4) to (11,11) — a 8x8 patch
        _place_ice_patch(game, 4, 4, width=8, height=8)
        # Move player to center of ice patch (pixel coords)
        _move_player_to(game, 6 * SUB_TILE_SIZE, 6 * SUB_TILE_SIZE)
        game.player_tank.direction = Direction.UP
        return game

    def test_slide_on_key_release(self, ice_game):
        """Player slides when releasing keys on ice."""
        game = ice_game

        # Move UP for a few frames
        _set_input(game, Direction.UP)
        _tick(game, 5)
        assert game.player_tank.direction == Direction.UP

        # Release keys — should start sliding UP
        _clear_input(game)
        _tick(game, 1)  # triggers slide
        assert game.player_tank.is_sliding is True
        assert game.player_tank._slide_direction == Direction.UP

        pos_before = game.player_tank.y
        _tick(game, 1)  # first frame of slide movement
        assert game.player_tank.y < pos_before, "Tank should slide UP (decreasing y)"

    def test_slide_on_perpendicular_direction_change(self, ice_game):
        """Player slides in old direction when changing to perpendicular."""
        game = ice_game

        # Move UP for a few frames
        _set_input(game, Direction.UP)
        _tick(game, 5)

        # Now press LEFT (perpendicular) — should slide UP first
        _set_input(game, Direction.LEFT)
        _tick(game, 1)  # triggers slide
        assert game.player_tank.is_sliding is True, (
            "Tank should start sliding on perpendicular direction change"
        )
        assert game.player_tank._slide_direction == Direction.UP, (
            "Slide should be in the OLD direction (UP)"
        )

        pos_before_y = game.player_tank.y
        _tick(game, 1)  # first frame of slide movement
        assert game.player_tank.y < pos_before_y, (
            "Tank should continue moving UP during slide"
        )

    def test_slide_distance_approximately_one_tile(self, ice_game):
        """Slide covers approximately ICE_SLIDE_DISTANCE pixels."""
        game = ice_game

        # Move RIGHT for a few frames
        game.player_tank.direction = Direction.RIGHT
        _set_input(game, Direction.RIGHT)
        _tick(game, 5)

        # Release — trigger slide, then capture position
        _clear_input(game)
        _tick(game, 1)  # triggers slide
        pos_before = game.player_tank.x

        # Let slide complete
        for _ in range(120):
            _tick(game, 1)
            if not game.player_tank.is_sliding:
                break

        distance = game.player_tank.x - pos_before
        assert abs(distance - ICE_SLIDE_DISTANCE) < 2.0, (
            f"Slide distance {distance:.1f} should be ~{ICE_SLIDE_DISTANCE}"
        )

    def test_no_slide_when_not_on_ice(self, game):
        """Player does NOT slide on normal tiles."""
        # Player is on normal tiles (default map position)
        _set_input(game, Direction.RIGHT)
        _tick(game, 5)
        _clear_input(game)
        _tick(game, 1)

        assert game.player_tank.is_sliding is False

    def test_slide_cancelled_by_wall(self, ice_game):
        """Slide stops when tank hits a wall/obstacle."""
        game = ice_game

        # Place a brick wall 1 tile to the right of player
        px = game.player_tank.x
        py = game.player_tank.y
        wall_grid_x = int(px // SUB_TILE_SIZE) + 2
        wall_grid_y = int(py // SUB_TILE_SIZE)
        for dy in range(2):
            tile = game.map.get_tile_at(wall_grid_x, wall_grid_y + dy)
            if tile is not None:
                game.map.set_tile_type(tile, TileType.BRICK)

        # Move RIGHT then release to slide into wall
        game.player_tank.direction = Direction.RIGHT
        _set_input(game, Direction.RIGHT)
        _tick(game, 3)
        _clear_input(game)

        # Tick until slide ends
        for _ in range(60):
            _tick(game, 1)
            if not game.player_tank.is_sliding:
                break

        assert game.player_tank.is_sliding is False, "Slide should have been cancelled"

    def test_slide_on_opposite_direction(self, ice_game):
        """Player slides when pressing opposite direction on ice."""
        game = ice_game

        # Move UP
        _set_input(game, Direction.UP)
        _tick(game, 5)

        # Press DOWN (opposite) — direction change triggers slide
        _set_input(game, Direction.DOWN)
        _tick(game, 1)  # triggers slide
        assert game.player_tank.is_sliding is True, (
            "Tank should slide when pressing opposite direction"
        )

        pos_before = game.player_tank.y
        _tick(game, 1)  # first frame of slide movement
        assert game.player_tank.y < pos_before, "Tank should continue sliding UP"
