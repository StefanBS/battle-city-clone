import pytest

from src.managers.footprint import (
    Footprint,
    blocks_spawn_point,
    cells_at,
    covered_cells,
    moved,
    size_in_cells,
    spawn_point_footprint,
    swept_cells,
    touching_cells,
)
from src.managers.world_view import EnemyView
from src.utils.constants import SUB_TILE_SIZE, TILE_SIZE, Direction

CELL = SUB_TILE_SIZE


def px(n: int) -> float:
    """Pixel coordinate of sub-tile ``n``."""
    return float(n * CELL)


def square(x: float, y: float, size: int = TILE_SIZE) -> Footprint:
    return Footprint(x, y, size)


class TestCoveredCells:
    def test_an_aligned_tank_covers_its_own_cells(self) -> None:
        assert covered_cells(square(px(3), px(5)), CELL) == {
            (3, 5),
            (4, 5),
            (3, 6),
            (4, 6),
        }

    def test_an_unaligned_tank_covers_every_cell_it_overlaps(self) -> None:
        tank = square(px(3) + 4, px(5))
        assert covered_cells(tank, CELL) == {(x, y) for x in (3, 4, 5) for y in (5, 6)}


class TestSizeInCells:
    def test_a_tank_spans_two_cells(self) -> None:
        assert size_in_cells(TILE_SIZE, CELL) == 2

    @pytest.mark.parametrize(("size", "cells"), [(CELL, 1), (CELL + 1, 2)])
    def test_a_part_cell_counts_as_a_whole_one(self, size: int, cells: int) -> None:
        assert size_in_cells(size, CELL) == cells


class TestCellsAt:
    def test_a_tank_at_a_cell_covers_it_and_the_cells_right_and_below(self) -> None:
        assert cells_at((3, 5), 2) == {(3, 5), (4, 5), (3, 6), (4, 6)}

    def test_a_one_cell_tank_covers_only_its_cell(self) -> None:
        assert cells_at((3, 5), 1) == {(3, 5)}


class TestTouchingCells:
    def test_cells_from_which_a_tank_overlaps_a_power_up(self) -> None:
        power_up = square(px(6), px(6))
        assert touching_cells(power_up, 2, CELL) == {
            (x, y) for x in (5, 6, 7) for y in (5, 6, 7)
        }

    def test_a_one_cell_tank_touches_only_from_the_covered_cells(self) -> None:
        power_up = square(px(6), px(6))
        assert touching_cells(power_up, 1, CELL) == covered_cells(power_up, CELL)


class TestMoved:
    def test_moves_by_distance_toward_the_delta(self) -> None:
        start = square(px(3), px(5))
        assert moved(start, Direction.LEFT.delta, 4) == square(px(3) - 4, px(5))
        assert moved(start, Direction.DOWN.delta, CELL) == square(px(3), px(6))

    def test_keeps_everything_else_a_tank_carries(self) -> None:
        enemy = EnemyView(enemy_id=7, x=px(3), y=px(5), direction=Direction.UP)
        after = moved(enemy, Direction.RIGHT.delta, CELL)
        assert after == EnemyView(enemy_id=7, x=px(4), y=px(5), direction=Direction.UP)


class TestSweptCells:
    def test_covers_every_cell_passed_through_on_the_way(self) -> None:
        start = square(px(3), px(5))
        assert swept_cells(start, Direction.RIGHT.delta, 2 * CELL, CELL) == {
            (x, y) for x in range(3, 7) for y in (5, 6)
        }

    def test_a_part_cell_move_reaches_into_the_next_cell(self) -> None:
        start = square(px(3), px(5))
        assert swept_cells(start, Direction.UP.delta, 4, CELL) == {
            (x, y) for x in (3, 4) for y in (4, 5, 6)
        }


class TestEnemySpawnPoint:
    def test_an_enemy_spawns_on_a_tank_sized_square(self) -> None:
        assert spawn_point_footprint((8, 0), CELL) == square(px(8), px(0))

    def test_a_tank_on_it_blocks_it(self) -> None:
        assert blocks_spawn_point(square(px(8), px(0)), (8, 0), CELL)

    def test_a_tank_covering_part_of_it_blocks_it(self) -> None:
        assert blocks_spawn_point(square(px(9) + 4, px(1) + 4), (8, 0), CELL)

    @pytest.mark.parametrize("beside", [(px(10), px(0)), (px(8), px(2))])
    def test_a_tank_flush_against_it_does_not_block_it(
        self, beside: tuple[float, float]
    ) -> None:
        assert not blocks_spawn_point(square(*beside), (8, 0), CELL)
