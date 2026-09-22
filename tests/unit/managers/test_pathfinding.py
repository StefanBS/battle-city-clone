import pytest

from src.core.tile import TileType
from src.managers.pathfinding import NavGrid
from src.managers.world_view import WorldView
from src.utils.constants import SUB_TILE_SIZE
from tests.conftest import tile_fields


def grid_with(
    tiles: dict[tuple[int, int], TileType],
    base_wall_cells: frozenset[tuple[int, int]] = frozenset(),
) -> NavGrid:
    """NavGrid for a one-sub-tile tank on an 8x8 field of ``tiles``."""
    world = WorldView(
        tile_size=SUB_TILE_SIZE,
        **tile_fields(tiles, grid=8),
        base_wall_cells=base_wall_cells,
    )
    return NavGrid(world, size_cells=1)


class TestNavGridTileRules:
    @pytest.mark.parametrize("tile", [TileType.STEEL, TileType.WATER, TileType.BASE])
    def test_indestructible_tank_blocking_tiles_are_impassable(self, tile) -> None:
        assert grid_with({(3, 3): tile}).passable((3, 3)) is False

    @pytest.mark.parametrize(
        "tile",
        [TileType.EMPTY, TileType.BUSH, TileType.ICE, TileType.BASE_DESTROYED],
    )
    def test_tiles_that_block_nothing_are_passable(self, tile) -> None:
        grid = grid_with({(3, 3): tile})
        assert grid.passable((3, 3)) is True
        assert grid.has_brick((3, 3)) is False

    def test_brick_is_passable_at_a_cost(self) -> None:
        grid = grid_with({(3, 3): TileType.BRICK})
        assert grid.passable((3, 3)) is True
        assert grid.has_brick((3, 3)) is True
        assert grid.step_cost((3, 3)) > grid.step_cost((4, 4))

    def test_base_wall_brick_is_impassable(self) -> None:
        grid = grid_with({(3, 3): TileType.BRICK}, base_wall_cells=frozenset({(3, 3)}))
        assert grid.passable((3, 3)) is False

    def test_map_edges_are_impassable(self) -> None:
        grid = grid_with({})
        assert grid.passable((-1, 0)) is False
        assert grid.passable((8, 0)) is False
