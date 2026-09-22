from src.core.tile import TileType
from src.managers.pathfinding import NavGrid
from src.managers.world_view import WorldView
from src.utils.constants import SUB_TILE_SIZE
from tests.conftest import tile_fields


def grid_with(tiles: dict[tuple[int, int], TileType]) -> NavGrid:
    """NavGrid for a one-sub-tile tank on an 8x8 field of ``tiles``."""
    world = WorldView(
        tile_size=SUB_TILE_SIZE,
        **tile_fields(tiles, grid=8),
    )
    return NavGrid(world, size_cells=1)


class TestNavGridTileRules:
    def test_tile_that_blocks_tanks_and_cant_be_destroyed_is_impassable(
        self,
    ) -> None:
        assert grid_with({(3, 3): TileType.STEEL}).passable((3, 3)) is False

    def test_destroyed_base_is_passable(self) -> None:
        grid = grid_with({(3, 3): TileType.BASE_DESTROYED})
        assert grid.passable((3, 3)) is True
        assert grid.has_brick((3, 3)) is False

    def test_brick_is_passable_at_a_cost(self) -> None:
        grid = grid_with({(3, 3): TileType.BRICK})
        assert grid.passable((3, 3)) is True
        assert grid.has_brick((3, 3)) is True
        assert grid.step_cost((3, 3)) > grid.step_cost((4, 4))
