import math

import pytest

from src.core.tile import TileType
from src.managers.world_view import EnemyView, WorldView
from src.utils.constants import SUB_TILE_SIZE, TILE_SIZE, Direction
from tests.conftest import tile_fields

Cell = tuple[int, int]

# A Base in mid-field: Base cells (12..13, 16..17) inside a ring of Base Wall
# cells (11..14, 15..18).
BASE = frozenset((x, y) for x in (12, 13) for y in (16, 17))
BASE_WALL = frozenset(
    (x, y) for x in range(11, 15) for y in range(15, 19) if (x, y) not in BASE
)


def px(n: int) -> float:
    """Pixel coordinate of sub-tile ``n``."""
    return float(n * SUB_TILE_SIZE)


def tank(x: int, y: int, facing: Direction = Direction.UP, enemy_id: int = 0):
    """A tank with its top-left corner on sub-tile ``(x, y)``."""
    return EnemyView(enemy_id=enemy_id, x=px(x), y=px(y), direction=facing)


def make_world(
    tiles: dict[Cell, TileType] | None = None,
    enemies: list[EnemyView] | None = None,
    half_brick_cells: frozenset[Cell] = frozenset(),
    base_wall: TileType | None = None,
) -> WorldView:
    """A 26x26 World View of ``tiles``, with the mid-field Base if walled."""
    tiles = dict(tiles or {})
    base_cells: frozenset[Cell] = frozenset()
    base_wall_cells: frozenset[Cell] = frozenset()
    if base_wall is not None:
        tiles |= {cell: TileType.BASE for cell in BASE}
        tiles |= {cell: base_wall for cell in BASE_WALL}
        base_cells, base_wall_cells = BASE, BASE_WALL
    return WorldView(
        tile_size=SUB_TILE_SIZE,
        **tile_fields(tiles),
        base_cells=base_cells,
        base_wall_cells=base_wall_cells,
        half_brick_cells=half_brick_cells,
        enemies=tuple(enemies or ()),
    )


class TestTileRules:
    def test_blocks_tanks_follows_tile_rules(self) -> None:
        world = make_world({(3, 3): TileType.WATER})
        assert world.blocks_tanks((3, 3)) is True
        assert world.blocks_tanks((4, 4)) is False

    @pytest.mark.parametrize("cell", [(-1, 0), (0, -1), (26, 0), (0, 26)])
    def test_off_the_map_blocks_tanks(self, cell) -> None:
        assert make_world().blocks_tanks(cell) is True


class TestLineOfFire:
    # A tank at (12, 12) facing up fires from y = 208 along columns 12-13.
    SHOOTER = tank(12, 12)

    def test_open_field_stops_nowhere(self) -> None:
        line = make_world().line_of_fire(self.SHOOTER, Direction.UP)
        assert line.stopped_at == math.inf
        assert line.bullet_proof_at == math.inf
        assert line.endangers_base is False

    def test_stops_at_the_near_edge_of_the_first_solid_tile(self) -> None:
        line = make_world({(12, 5): TileType.BRICK}).line_of_fire(
            self.SHOOTER, Direction.UP
        )
        assert line.stopped_at == 208 - px(6)

    def test_half_brick_is_not_solid(self) -> None:
        world = make_world(
            {(12, 5): TileType.BRICK}, half_brick_cells=frozenset({(12, 5)})
        )
        assert world.line_of_fire(self.SHOOTER, Direction.UP).stopped_at == math.inf

    def test_reaches_through_brick(self) -> None:
        line = make_world({(12, 5): TileType.BRICK}).line_of_fire(
            self.SHOOTER, Direction.UP
        )
        assert line.reaches(tank(12, 2)) is True

    def test_nothing_gets_past_what_a_bullet_cant_destroy(self) -> None:
        line = make_world({(12, 5): TileType.STEEL}).line_of_fire(
            self.SHOOTER, Direction.UP
        )
        assert line.reaches(tank(12, 2)) is False
        assert line.reaches(tank(12, 7)) is True

    def test_distance_to_a_tank_ahead(self) -> None:
        line = make_world().line_of_fire(self.SHOOTER, Direction.UP)
        assert line.distance_to(tank(12, 2)) == 208 - px(4)

    @pytest.mark.parametrize(
        "other",
        [tank(12, 20), tank(15, 2), tank(9, 2)],
        ids=["behind", "right of the lane", "left of the lane"],
    )
    def test_distance_to_a_tank_out_of_the_line_is_none(self, other) -> None:
        line = make_world().line_of_fire(self.SHOOTER, Direction.UP)
        assert line.distance_to(other) is None

    def test_facing_decides_the_direction(self) -> None:
        line = make_world().line_of_fire(self.SHOOTER, Direction.RIGHT)
        assert line.horizontal is True
        assert line.step == 1
        assert line.distance_to(tank(20, 12)) == px(20) - 208
        assert line.distance_to(tank(12, 2)) is None

    def test_endangers_base_when_base_wall_is_hit_first(self) -> None:
        world = make_world(base_wall=TileType.BRICK)
        line = world.line_of_fire(tank(12, 4), Direction.DOWN)
        assert line.endangers_base is True

    def test_endangers_base_through_a_half_brick(self) -> None:
        world = make_world(
            {(12, 10): TileType.BRICK},
            half_brick_cells=frozenset({(12, 10)}),
            base_wall=TileType.BRICK,
        )
        assert world.line_of_fire(tank(12, 4), Direction.DOWN).endangers_base is True

    def test_solid_tile_before_base_wall_keeps_base_safe(self) -> None:
        world = make_world({(12, 10): TileType.BRICK}, base_wall=TileType.BRICK)
        line = world.line_of_fire(tank(12, 4), Direction.DOWN)
        assert line.endangers_base is False
        assert line.stopped_at == px(10) - px(5)

    def test_lane_beside_the_base_wall_is_safe(self) -> None:
        world = make_world(base_wall=TileType.BRICK)
        assert world.line_of_fire(tank(15, 4), Direction.DOWN).endangers_base is False

    def test_is_from_firing_position_needs_reach_and_a_safe_base(self) -> None:
        world = make_world(base_wall=TileType.BRICK)
        line = world.line_of_fire(tank(12, 4), Direction.DOWN)
        assert line.reaches(tank(12, 10)) is True
        assert line.is_from_firing_position(tank(12, 10)) is False


class TestFiringPositions:
    def test_open_field_positions_line_up_on_every_side(self) -> None:
        positions = make_world().firing_positions(tank(12, 8), TILE_SIZE)
        assert {(12, 10), (12, 6), (14, 8), (10, 8), (12, 25), (0, 8)} <= positions
        assert all(x == 12 or y == 8 for x, y in positions)

    def test_leaves_out_cells_overlapping_the_target(self) -> None:
        positions = make_world().firing_positions(tank(12, 8), TILE_SIZE)
        assert not {(12, 9), (12, 7), (13, 8), (11, 8)} & positions

    def test_only_on_the_given_sides(self) -> None:
        positions = make_world().firing_positions(
            tank(12, 8), TILE_SIZE, sides=[Direction.LEFT]
        )
        assert positions
        assert all(y == 8 and x < 12 for x, y in positions)

    def test_brick_does_not_cut_the_line(self) -> None:
        world = make_world({(12, 14): TileType.BRICK, (13, 14): TileType.BRICK})
        positions = world.firing_positions(tank(12, 8), TILE_SIZE)
        assert (12, 20) in positions

    def test_steel_cuts_every_cell_beyond_it(self) -> None:
        world = make_world({(12, 14): TileType.STEEL})
        below = {
            y
            for x, y in world.firing_positions(tank(12, 8), TILE_SIZE)
            if x == 12 and y > 8
        }
        assert below == {10, 11, 12}

    def test_never_where_a_miss_could_hit_the_base(self) -> None:
        # Above the target, a miss carries on into the Base Wall.
        world = make_world(base_wall=TileType.BRICK)
        positions = world.firing_positions(tank(12, 8), TILE_SIZE)
        assert not any(x == 12 and y < 8 for x, y in positions)
        assert (14, 8) in positions

    def test_never_through_the_base(self) -> None:
        world = make_world(base_wall=TileType.BRICK)
        positions = world.firing_positions(tank(12, 22), TILE_SIZE)
        assert (12, 20) in positions
        assert not any(x == 12 and y < 18 for x, y in positions)


class TestBaseThreats:
    @pytest.mark.parametrize(
        "wall", [TileType.EMPTY, TileType.BRICK], ids=["shot away", "brick"]
    )
    def test_far_enemy_in_base_column_is_a_threat_whatever_it_faces(self, wall) -> None:
        enemy = tank(12, 2, facing=Direction.UP)
        world = make_world(enemies=[enemy], base_wall=wall)
        assert world.base_threats == (enemy,)

    def test_steel_base_wall_shields_far_enemy(self) -> None:
        world = make_world(enemies=[tank(12, 2)], base_wall=TileType.STEEL)
        assert world.base_threats == ()

    def test_enemy_close_to_the_base_is_a_threat_without_a_line(self) -> None:
        # Out of the Base's rows and columns, but within the threat radius.
        enemy = tank(17, 19)
        world = make_world(enemies=[enemy], base_wall=TileType.STEEL)
        assert world.base_threats == (enemy,)

    def test_far_enemy_off_the_base_lines_is_no_threat(self) -> None:
        world = make_world(enemies=[tank(2, 2)], base_wall=TileType.BRICK)
        assert world.base_threats == ()

    def test_nearest_the_base_first(self) -> None:
        far = tank(12, 0, enemy_id=0)
        near = tank(12, 6, enemy_id=1)
        world = make_world(enemies=[far, near], base_wall=TileType.BRICK)
        assert world.base_threats == (near, far)

    def test_no_base_no_threats(self) -> None:
        world = make_world(enemies=[tank(12, 2)])
        assert world.base_footprint is None
        assert world.base_threats == ()


class TestCellOf:
    def test_an_unaligned_tank_is_at_its_nearest_cell(self) -> None:
        world = make_world()
        enemy = EnemyView(enemy_id=0, x=px(3) + 4, y=px(5), direction=Direction.UP)
        assert world.cell_of(enemy) == (3, 5)
