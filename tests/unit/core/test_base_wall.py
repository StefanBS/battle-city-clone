"""Unit tests for BaseWall: the Shovel Fortifies the Base Wall, then reverts it."""

import pytest

from src.core.base_wall import BaseWall
from src.core.map import Map
from src.core.tile import BrickVariant, TileType
from src.utils.constants import (
    SHOVEL_DURATION,
    SHOVEL_FLASH_INTERVAL,
    SHOVEL_WARNING_DURATION,
    Direction,
)
from src.utils.paths import resource_path

# Exact in binary, so the Shovel's countdown has no rounding.
DT = 0.25
UNTIL_WARNING = SHOVEL_DURATION - SHOVEL_WARNING_DURATION


@pytest.fixture
def game_map(mock_texture_manager):
    return Map(resource_path("assets/maps/level_01.tmx"), mock_texture_manager)


@pytest.fixture
def base_wall(game_map):
    return BaseWall(game_map)


def _wall(game_map):
    return game_map.get_base_surrounding_tiles(include_empty=True)


def _types(game_map):
    return {tile.type for tile in _wall(game_map)}


def _run(base_wall, seconds):
    for _ in range(int(seconds / DT)):
        base_wall.update(DT)


class TestBaseWall:
    def test_a_shovel_fortifies_the_wall(self, game_map, base_wall):
        base_wall.fortify()
        assert _types(game_map) == {TileType.STEEL}

    def test_the_wall_stays_fortified_until_the_warning(self, game_map, base_wall):
        base_wall.fortify()
        _run(base_wall, UNTIL_WARNING - DT)
        assert _types(game_map) == {TileType.STEEL}

    def test_the_wall_reverts_to_brick_when_the_shovel_runs_out(
        self, game_map, base_wall
    ):
        base_wall.fortify()
        _run(base_wall, SHOVEL_DURATION)
        assert _types(game_map) == {TileType.BRICK}

    def test_the_wall_flashes_during_the_warning(self, game_map, base_wall):
        base_wall.fortify()
        _run(base_wall, UNTIL_WARNING)
        assert _types(game_map) == {TileType.BRICK}
        _run(base_wall, SHOVEL_FLASH_INTERVAL)
        assert _types(game_map) == {TileType.STEEL}

    def test_a_shovel_rebuilds_destroyed_bricks_first(self, game_map, base_wall):
        destroyed, damaged = _wall(game_map)[:2]
        game_map.set_tile_type(destroyed, TileType.EMPTY)
        game_map.damage_brick(damaged, Direction.UP, damaged.rect)
        assert damaged.brick_variant != BrickVariant.FULL

        base_wall.fortify()
        _run(base_wall, SHOVEL_DURATION)

        assert _types(game_map) == {TileType.BRICK}
        for tile in (destroyed, damaged):
            assert tile.brick_variant == BrickVariant.FULL
            assert tile.rect.size == (tile.size, tile.size)

    def test_steel_shot_away_stays_empty_when_the_wall_reverts(
        self, game_map, base_wall
    ):
        base_wall.fortify()
        shot_away = _wall(game_map)[0]
        game_map.set_tile_type(shot_away, TileType.EMPTY)

        _run(base_wall, SHOVEL_DURATION)

        assert shot_away.type == TileType.EMPTY
        assert _types(game_map) == {TileType.BRICK, TileType.EMPTY}

    def test_a_second_shovel_starts_it_over(self, game_map, base_wall):
        base_wall.fortify()
        _run(base_wall, UNTIL_WARNING - 1.0)

        base_wall.fortify()
        _run(base_wall, UNTIL_WARNING - DT)

        assert _types(game_map) == {TileType.STEEL}

    def test_a_second_shovel_does_not_rebuild(self, game_map, base_wall):
        base_wall.fortify()
        shot_away = _wall(game_map)[0]
        game_map.set_tile_type(shot_away, TileType.EMPTY)

        base_wall.fortify()

        assert shot_away.type == TileType.EMPTY

    def test_a_shovel_during_the_warning_turns_the_wall_back_to_steel(
        self, game_map, base_wall
    ):
        base_wall.fortify()
        _run(base_wall, UNTIL_WARNING)
        assert _types(game_map) == {TileType.BRICK}

        base_wall.fortify()

        assert _types(game_map) == {TileType.STEEL}
