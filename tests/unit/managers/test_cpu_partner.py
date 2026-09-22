from dataclasses import replace

import pytest

from src.core.tile import TileType
from src.managers.cpu_partner import CpuPartnerInput
from src.managers.world_view import EnemyView, PlayerView, WorldView
from src.utils.constants import (
    CPU_PARTNER_STUCK_TIME,
    FPS,
    SUB_TILE_SIZE,
    TANK_ALIGN_THRESHOLD,
    Direction,
)

GRID = 26
CPU_ID = 2

Cell = tuple[int, int]


def cell(n: int) -> float:
    """Pixel coordinate of sub-tile ``n``."""
    return float(n * SUB_TILE_SIZE)


def make_view(
    own: tuple[int, int, Direction] | None = (12, 12, Direction.UP),
    enemies: list[tuple[int, int]] | None = None,
    human: tuple[int, int] = (0, 24),
    tiles: dict[Cell, TileType] | None = None,
    base_cells: frozenset[Cell] = frozenset(),
    base_wall_cells: frozenset[Cell] = frozenset(),
    half_brick_cells: frozenset[Cell] = frozenset(),
) -> WorldView:
    """Build a World View with the CPU Partner at sub-tile ``own``.

    The field is open except for ``tiles``; the Human Player sits at ``human``.
    """
    tiles = tiles or {}
    players: list[PlayerView] = [
        PlayerView(
            player_id=1, x=cell(human[0]), y=cell(human[1]), direction=Direction.UP
        )
    ]
    if own is not None:
        gx, gy, facing = own
        players.append(
            PlayerView(player_id=CPU_ID, x=cell(gx), y=cell(gy), direction=facing)
        )
    return WorldView(
        tile_size=SUB_TILE_SIZE,
        tiles=tuple(
            tuple(tiles.get((x, y), TileType.EMPTY) for x in range(GRID))
            for y in range(GRID)
        ),
        base_cells=base_cells,
        base_wall_cells=base_wall_cells,
        half_brick_cells=half_brick_cells,
        enemies=tuple(
            EnemyView(enemy_id=i, x=cell(gx), y=cell(gy), direction=Direction.DOWN)
            for i, (gx, gy) in enumerate(enemies or [])
        ),
        players=tuple(players),
        own_player_id=CPU_ID,
    )


@pytest.fixture
def cpu() -> CpuPartnerInput:
    return CpuPartnerInput()


class TestCpuPartnerHunt:
    def test_heads_for_nearest_of_several_enemies(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 0), (18, 12)]))
        assert cpu.get_movement_direction() == Direction.RIGHT.delta

    def test_keeps_target_when_another_enemy_comes_closer(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)]))
        # Enemy 1 appears right next to it; it keeps hunting enemy 0.
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2), (16, 12)]))
        assert cpu.consume_shoot() is True
        assert cpu.get_movement_direction() == (0, 0)

    def test_retargets_nearest_when_target_dies(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2), (20, 12)]))
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 2), (20, 12)])
        cpu.observe(replace(view, enemies=view.enemies[1:]))
        assert cpu.get_movement_direction() == Direction.RIGHT.delta

    def test_stands_still_without_enemies(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[]))
        assert cpu.get_movement_direction() == (0, 0)
        assert cpu.consume_shoot() is False

    def test_idle_when_own_tank_is_dead(self, cpu) -> None:
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)])
        dead = replace(view.players[1], alive=False)
        cpu.observe(replace(view, players=(view.players[0], dead)))
        assert cpu.get_movement_direction() == (0, 0)
        assert cpu.consume_shoot() is False


class TestCpuPartnerFiring:
    def test_fires_and_holds_position_when_lined_up_and_facing(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)]))
        assert cpu.consume_shoot() is True
        assert cpu.get_movement_direction() == (0, 0)

    def test_fires_within_half_a_tile_of_alignment(self, cpu) -> None:
        # One sub-tile (half a tank) off the column still counts as lined up.
        cpu.observe(make_view(own=(12, 12, Direction.RIGHT), enemies=[(20, 13)]))
        assert cpu.consume_shoot() is True

    def test_turns_to_face_enemy_before_firing(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.LEFT), enemies=[(12, 2)]))
        assert cpu.consume_shoot() is False
        assert cpu.get_movement_direction() == Direction.UP.delta

    def test_shoot_request_is_consumed_once(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)]))
        cpu.consume_shoot()
        assert cpu.consume_shoot() is False

    def test_clear_pending_shoot_drops_request(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)]))
        cpu.clear_pending_shoot()
        assert cpu.consume_shoot() is False


# A Base in mid-field so targets can stand on either side of it: Base cells
# (12..13, 16..17) inside a ring of Base Wall cells (11..14, 15..18).
BASE = frozenset((x, y) for x in (12, 13) for y in (16, 17))
BASE_WALL = frozenset(
    (x, y) for x in range(11, 15) for y in range(15, 19) if (x, y) not in BASE
)


def base_tiles(wall: TileType | None = TileType.BRICK) -> dict[Cell, TileType]:
    """Tiles for the mid-field Base, with its wall made of ``wall`` (or gone)."""
    tiles = {cell: TileType.BASE for cell in BASE}
    if wall is not None:
        tiles |= {cell: wall for cell in BASE_WALL}
    return tiles


def base_view(
    own: tuple[int, int, Direction],
    enemy: tuple[int, int],
    wall: TileType | None = TileType.BRICK,
    extra_tiles: dict[Cell, TileType] | None = None,
    half_brick_cells: frozenset[Cell] = frozenset(),
) -> WorldView:
    """World View with the mid-field Base, one Enemy and optional extra tiles."""
    return make_view(
        own=own,
        enemies=[enemy],
        tiles=base_tiles(wall) | (extra_tiles or {}),
        base_cells=BASE,
        base_wall_cells=BASE_WALL,
        half_brick_cells=half_brick_cells,
    )


class TestCpuPartnerHoldFireNearBase:
    @pytest.mark.parametrize(
        "wall",
        [
            None,  # wall shot away: the Base itself is the first tile hit
            TileType.BRICK,
            TileType.STEEL,  # after a shovel
        ],
    )
    def test_holds_fire_when_base_or_base_wall_is_first_tile_hit(
        self, cpu, wall
    ) -> None:
        cpu.observe(base_view((12, 4, Direction.DOWN), (12, 22), wall=wall))
        assert cpu.consume_shoot() is False

    def test_holds_fire_on_base_wall_behind_a_close_target(self, cpu) -> None:
        # A miss would carry on into the Base Wall.
        cpu.observe(base_view((12, 4, Direction.DOWN), (12, 10)))
        assert cpu.consume_shoot() is False

    @pytest.mark.parametrize(
        ("own", "enemy"),
        [
            ((0, 16, Direction.RIGHT), (24, 16)),  # row through the Base
            ((13, 0, Direction.DOWN), (13, 24)),  # lane straddles columns 13-14
        ],
    )
    def test_holds_fire_along_any_lane_into_the_base(self, cpu, own, enemy) -> None:
        cpu.observe(base_view(own, enemy))
        assert cpu.consume_shoot() is False

    def test_holds_fire_when_only_a_half_brick_precedes_base_wall(self, cpu) -> None:
        # The bullet may slip past the missing half into the Base Wall.
        cpu.observe(
            base_view(
                (12, 4, Direction.DOWN),
                (12, 22),
                extra_tiles={(12, 10): TileType.BRICK},
                half_brick_cells=frozenset({(12, 10)}),
            )
        )
        assert cpu.consume_shoot() is False

    def test_fires_when_lane_passes_beside_the_base_wall(self, cpu) -> None:
        # Lane covers columns 15-16, just right of the wall's column 14.
        cpu.observe(base_view((15, 4, Direction.DOWN), (15, 22)))
        assert cpu.consume_shoot() is True

    def test_fires_when_other_brick_is_hit_before_base_wall(self, cpu) -> None:
        cpu.observe(
            base_view(
                (12, 4, Direction.DOWN),
                (12, 22),
                extra_tiles={(12, 10): TileType.BRICK},
            )
        )
        assert cpu.consume_shoot() is True


class TestCpuPartnerHoldFireNearHuman:
    def test_holds_fire_when_human_lies_before_target(self, cpu) -> None:
        # Even a Human Player only half in the lane would be hit.
        cpu.observe(
            make_view(own=(12, 20, Direction.UP), enemies=[(12, 2)], human=(13, 10))
        )
        assert cpu.consume_shoot() is False
        assert cpu.get_movement_direction() == (0, 0)

    @pytest.mark.parametrize(
        ("own", "enemy", "human"),
        [
            ((12, 20, Direction.UP), (12, 8), (12, 2)),  # beyond the target
            ((12, 20, Direction.UP), (12, 2), (14, 10)),  # beside the lane
            ((12, 12, Direction.UP), (12, 2), (12, 20)),  # behind the CPU Partner
        ],
    )
    def test_fires_when_human_is_out_of_harms_way(self, cpu, own, enemy, human) -> None:
        cpu.observe(make_view(own=own, enemies=[enemy], human=human))
        assert cpu.consume_shoot() is True

    def test_fires_when_brick_shields_human_before_target(self, cpu) -> None:
        cpu.observe(
            make_view(
                own=(12, 20, Direction.UP),
                enemies=[(12, 2)],
                human=(12, 10),
                tiles={(12, 14): TileType.BRICK},
            )
        )
        assert cpu.consume_shoot() is True

    def test_holds_fire_when_only_a_half_brick_shields_human(self, cpu) -> None:
        cpu.observe(
            make_view(
                own=(12, 20, Direction.UP),
                enemies=[(12, 2)],
                human=(12, 10),
                tiles={(12, 14): TileType.BRICK},
                half_brick_cells=frozenset({(12, 14)}),
            )
        )
        assert cpu.consume_shoot() is False

    def test_fires_through_dead_human(self, cpu) -> None:
        view = make_view(own=(12, 20, Direction.UP), enemies=[(12, 2)], human=(12, 10))
        dead_human = replace(view.players[0], alive=False)
        cpu.observe(replace(view, players=(dead_human, view.players[1])))
        assert cpu.consume_shoot() is True


# A steel corridor along columns 12-13 (walls at columns 11 and 14, rows 0-20)
# with the Enemy at (12, 4) and the CPU Partner below it at (12, 22), facing
# up. Openings are cut into the right wall; column 15 beyond it is open.
CORRIDOR_ENEMY = (12, 4)
CORRIDOR_CPU = (12, 22, Direction.UP)


def corridor_view(
    enemy_facing: Direction = Direction.DOWN,
    right_openings: tuple[int, ...] = (),
    extra_tiles: dict[Cell, TileType] | None = None,
    bullet_speed: float | None = None,
    enemy_speed: float | None = None,
    enemies_frozen: bool = False,
) -> WorldView:
    """World View of the Enemy in a corridor with the given right-wall gaps."""
    tiles = {(11, y): TileType.STEEL for y in range(21)}
    tiles |= {(14, y): TileType.STEEL for y in range(21) if y not in right_openings}
    view = make_view(
        own=CORRIDOR_CPU,
        enemies=[CORRIDOR_ENEMY],
        tiles=tiles | (extra_tiles or {}),
    )
    enemy = replace(view.enemies[0], direction=enemy_facing)
    if enemy_speed is not None:
        enemy = replace(enemy, speed=enemy_speed)
    own = view.players[1]
    if bullet_speed is not None:
        own = replace(own, bullet_speed=bullet_speed)
    return replace(
        view,
        enemies=(enemy,),
        players=(view.players[0], own),
        enemies_frozen=enemies_frozen,
    )


class TestCpuPartnerHoldFireNearCorridorExit:
    def test_fires_at_enemy_hemmed_in_with_no_exit(self, cpu) -> None:
        cpu.observe(corridor_view())
        assert cpu.consume_shoot() is True

    def test_holds_fire_when_enemy_nears_an_exit(self, cpu) -> None:
        # Exit two cells ahead of the Enemy as it drives down the corridor.
        cpu.observe(corridor_view(right_openings=(6, 7)))
        assert cpu.consume_shoot() is False
        assert cpu.get_movement_direction() == (0, 0)

    def test_fires_when_exit_lies_behind_the_enemy(self, cpu) -> None:
        cpu.observe(corridor_view(Direction.DOWN, right_openings=(0, 1)))
        assert cpu.consume_shoot() is True

    def test_holds_fire_when_enemy_drives_toward_an_exit_behind_it(self, cpu) -> None:
        cpu.observe(corridor_view(Direction.UP, right_openings=(0, 1)))
        assert cpu.consume_shoot() is False

    def test_holds_fire_when_enemy_faces_the_wall_near_an_exit(self, cpu) -> None:
        # Facing a wall it must turn anyway, so it may head either way.
        cpu.observe(corridor_view(Direction.LEFT, right_openings=(0, 1)))
        assert cpu.consume_shoot() is False

    def test_fires_when_gap_is_too_narrow_for_a_tank(self, cpu) -> None:
        cpu.observe(corridor_view(right_openings=(6,)))
        assert cpu.consume_shoot() is True

    def test_fires_when_obstacle_blocks_the_way_to_the_exit(self, cpu) -> None:
        cpu.observe(
            corridor_view(
                Direction.UP,
                right_openings=(0, 1),
                extra_tiles={(12, 3): TileType.BRICK, (13, 3): TileType.BRICK},
            )
        )
        assert cpu.consume_shoot() is True

    def test_fires_at_stationary_enemy_beside_an_exit(self, cpu) -> None:
        cpu.observe(corridor_view(right_openings=(4, 5), enemy_speed=0))
        assert cpu.consume_shoot() is True

    def test_fires_when_enemies_are_frozen(self, cpu) -> None:
        cpu.observe(corridor_view(right_openings=(6, 7), enemies_frozen=True))
        assert cpu.consume_shoot() is True

    def test_star_bullet_beats_the_enemy_to_a_near_exit(self, cpu) -> None:
        cpu.observe(corridor_view(right_openings=(7, 8)))
        assert cpu.consume_shoot() is False
        cpu.observe(corridor_view(right_openings=(7, 8), bullet_speed=360))
        assert cpu.consume_shoot() is True

    def test_fast_enemy_reaches_a_farther_exit(self, cpu) -> None:
        cpu.observe(corridor_view(right_openings=(9, 10)))
        assert cpu.consume_shoot() is True
        cpu.observe(corridor_view(right_openings=(9, 10), enemy_speed=160))
        assert cpu.consume_shoot() is False

    def test_fires_when_enemy_is_walled_on_one_side_only(self, cpu) -> None:
        view = corridor_view()
        open_right = tuple(
            tuple(TileType.EMPTY if x == 14 else t for x, t in enumerate(row))
            for row in view.tiles
        )
        cpu.observe(replace(view, tiles=open_right))
        assert cpu.consume_shoot() is True


def wall_row(
    rows: tuple[int, ...],
    tile: TileType,
    gaps: tuple[int, ...] = (),
    xs: range = range(GRID),
) -> dict[Cell, TileType]:
    """A horizontal wall of ``tile`` across ``rows``, open at columns ``gaps``."""
    return {(x, y): tile for y in rows for x in xs if x not in gaps}


# The CPU Partner at (12, 12) sits at the top of a steel corridor (walls at
# columns 11 and 14, rows 12-21) under a brick wall across rows 10-11 whose
# only gap is on the far left: going round means a long detour.
BRICK_WALL_OVER_CORRIDOR = wall_row((10, 11), TileType.BRICK, gaps=(0, 1)) | {
    (x, y): TileType.STEEL for x in (11, 14) for y in range(12, 22)
}


class TestCpuPartnerPathfinding:
    def test_goes_around_steel_to_reach_enemy_behind_it(self, cpu) -> None:
        # Lined up with the Enemy right under a steel wall that blocks the Line
        # of Fire; the only way through is the gap on the far left.
        cpu.observe(
            make_view(
                own=(12, 12, Direction.UP),
                enemies=[(12, 2)],
                tiles=wall_row((10, 11), TileType.STEEL, gaps=(0, 1)),
            )
        )
        assert cpu.consume_shoot() is False
        assert cpu.get_movement_direction() == Direction.LEFT.delta

    def test_does_not_enter_a_one_sub_tile_gap(self, cpu) -> None:
        # A 1-sub-tile gap right ahead is too narrow for the 2x2 tank; the
        # tank-wide gap is further away on the right.
        cpu.observe(
            make_view(
                own=(12, 12, Direction.UP),
                enemies=[(12, 2)],
                tiles=wall_row((10, 11), TileType.STEEL, gaps=(12, 20, 21)),
            )
        )
        assert cpu.get_movement_direction() == Direction.RIGHT.delta

    def test_goes_around_a_brick_wall_when_the_detour_is_short(self, cpu) -> None:
        cpu.observe(
            make_view(
                own=(12, 12, Direction.UP),
                enemies=[(20, 2)],
                tiles=wall_row((10, 11), TileType.BRICK, gaps=(10, 11)),
            )
        )
        assert cpu.get_movement_direction() == Direction.LEFT.delta
        assert cpu.consume_shoot() is False

    def test_shoots_through_a_brick_wall_when_the_detour_is_long(self, cpu) -> None:
        cpu.observe(
            make_view(
                own=(12, 12, Direction.UP),
                enemies=[(20, 2)],
                tiles=BRICK_WALL_OVER_CORRIDOR,
            )
        )
        assert cpu.get_movement_direction() == Direction.UP.delta
        assert cpu.consume_shoot() is True

    def test_turns_to_face_a_brick_before_shooting_it(self, cpu) -> None:
        cpu.observe(
            make_view(
                own=(12, 12, Direction.LEFT),
                enemies=[(20, 2)],
                tiles=BRICK_WALL_OVER_CORRIDOR,
            )
        )
        assert cpu.get_movement_direction() == Direction.UP.delta
        assert cpu.consume_shoot() is False

    def test_never_paths_through_the_base_wall(self, cpu) -> None:
        # Down through the Base Wall would be as short as going round, but
        # shooting it is forbidden.
        cpu.observe(base_view((12, 13, Direction.DOWN), (16, 21)))
        assert cpu.get_movement_direction() == Direction.RIGHT.delta
        assert cpu.consume_shoot() is False

    def test_hunts_the_enemy_nearest_by_path_not_by_distance(self, cpu) -> None:
        # Enemy 0 is closer as the crow flies but sits behind steel, a long way
        # round; Enemy 1 in the same row is quicker to reach.
        cpu.observe(
            make_view(
                own=(12, 12, Direction.UP),
                enemies=[(12, 4), (22, 12)],
                tiles=wall_row((8, 9), TileType.STEEL, gaps=(0, 1)),
            )
        )
        assert cpu.get_movement_direction() == Direction.RIGHT.delta

    def test_backs_up_to_a_gap_it_slid_past(self, cpu) -> None:
        # Slid 6px past the tank-wide gap, too far for the steering nudge to
        # line it up, so it backs up before turning into the gap.
        view = make_view(
            own=(12, 12, Direction.RIGHT),
            enemies=[(20, 2)],
            tiles=wall_row((10, 11), TileType.STEEL, gaps=(12, 13)),
        )
        slid = replace(view.players[1], x=cell(12) + 6)
        cpu.observe(replace(view, players=(view.players[0], slid)))
        assert cpu.get_movement_direction() == Direction.LEFT.delta

    def test_turns_into_a_gap_the_nudge_can_line_it_up_with(self, cpu) -> None:
        view = make_view(
            own=(12, 12, Direction.RIGHT),
            enemies=[(20, 2)],
            tiles=wall_row((10, 11), TileType.STEEL, gaps=(12, 13)),
        )
        slid = replace(view.players[1], x=cell(12) + TANK_ALIGN_THRESHOLD)
        cpu.observe(replace(view, players=(view.players[0], slid)))
        assert cpu.get_movement_direction() == Direction.UP.delta


# The CPU Partner at (12, 12) under a steel wall across rows 10-11, hunting
# the Enemy at (12, 2) above it. The nearer gap is on the left (columns
# 9-10), a slightly longer route through the right gap (columns 16-17).
TWO_GAP_WALL = wall_row((10, 11), TileType.STEEL, gaps=(9, 10, 16, 17))


def blocked_view(
    blocker_moved: bool = False, blocker: tuple[int, int] = (10, 12)
) -> WorldView:
    """The two-gap scene with a frozen Enemy parked just left of the CPU."""
    if blocker_moved:
        blocker = (10, 16)
    return replace(
        make_view(
            own=(12, 12, Direction.LEFT),
            enemies=[(12, 2), blocker],
            tiles=TWO_GAP_WALL,
        ),
        enemies_frozen=True,
    )


def observe_stuck(
    cpu: CpuPartnerInput, frames: int, blocker: tuple[int, int] = (10, 12)
) -> None:
    """Feed ``frames`` frames of the CPU Partner not moving from its spot."""
    for _ in range(frames):
        cpu.observe(blocked_view(blocker=blocker))


STUCK_FRAMES = int(CPU_PARTNER_STUCK_TIME * FPS)


class TestCpuPartnerBlocked:
    @pytest.fixture
    def hunting(self, cpu) -> CpuPartnerInput:
        """A CPU Partner already hunting the Enemy at (12, 2)."""
        cpu.observe(
            make_view(
                own=(12, 12, Direction.LEFT), enemies=[(12, 2)], tiles=TWO_GAP_WALL
            )
        )
        assert cpu.get_movement_direction() == Direction.LEFT.delta
        return cpu

    def test_keeps_its_route_while_briefly_blocked(self, hunting) -> None:
        observe_stuck(hunting, STUCK_FRAMES - 1)
        assert hunting.get_movement_direction() == Direction.LEFT.delta

    def test_replans_around_an_enemy_blocking_its_route(self, hunting) -> None:
        observe_stuck(hunting, STUCK_FRAMES + 1)
        assert hunting.get_movement_direction() == Direction.RIGHT.delta
        # It sticks with the detour rather than turning back into the blocker.
        hunting.observe(blocked_view())
        assert hunting.get_movement_direction() == Direction.RIGHT.delta

    def test_takes_the_short_route_again_once_the_blocker_moves(self, hunting) -> None:
        observe_stuck(hunting, STUCK_FRAMES + 1)
        hunting.observe(blocked_view(blocker_moved=True))
        assert hunting.get_movement_direction() == Direction.LEFT.delta

    def test_does_not_route_around_an_enemy_that_is_not_in_its_way(
        self, hunting
    ) -> None:
        # Held in place (by anything) while a frozen Enemy sits in the far
        # gap: that Enemy isn't what is stopping it, so the route stays.
        far_in_the_gap = (9, 10)
        observe_stuck(hunting, STUCK_FRAMES + 1, blocker=far_in_the_gap)
        assert hunting.get_movement_direction() == Direction.LEFT.delta


class TestCpuPartnerUnreachableTarget:
    def test_switches_to_a_reachable_enemy_when_its_target_is_cut_off(
        self, cpu
    ) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(20, 2), (2, 20)]))
        # The target it picked gets sealed in by steel.
        sealed = {
            (x, y): TileType.STEEL
            for x in range(16, GRID)
            for y in range(0, 8)
            if not (x >= 18 and y <= 5 and x <= 23)
        }
        view = make_view(
            own=(12, 12, Direction.UP), enemies=[(20, 2), (2, 20)], tiles=sealed
        )
        cpu.observe(view)
        cpu.observe(view)
        assert cpu.get_movement_direction() in {
            Direction.LEFT.delta,
            Direction.DOWN.delta,
        }
