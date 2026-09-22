from dataclasses import replace

import pytest

from src.core.tile import TileType
from src.managers.cpu_partner import CpuPartnerInput, ambush_positions
from src.managers.world_view import EnemyView, PlayerView, PowerUpView, WorldView
from src.utils.constants import (
    CPU_PARTNER_ALIGN_TOLERANCE,
    CPU_PARTNER_AMBUSH_DISTANCE,
    CPU_PARTNER_GOAL_STICKINESS,
    CPU_PARTNER_POWER_UP_RANGE,
    CPU_PARTNER_STUCK_TIME,
    FPS,
    SUB_TILE_SIZE,
    TANK_ALIGN_THRESHOLD,
    Direction,
    PowerUpType,
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
    human: tuple[float, float] = (0, 24),
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

    @pytest.mark.parametrize(
        "offset, fires",
        [
            (CPU_PARTNER_ALIGN_TOLERANCE, True),
            (CPU_PARTNER_ALIGN_TOLERANCE + 1, False),
        ],
    )
    def test_fires_only_within_half_a_sub_tile_of_alignment(
        self, cpu, offset, fires
    ) -> None:
        view = make_view(own=(12, 12, Direction.RIGHT), enemies=[(20, 12)])
        enemy = replace(view.enemies[0], y=cell(12) + offset)
        cpu.observe(replace(view, enemies=(enemy,)))
        assert cpu.consume_shoot() is fires

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


# The Enemy at (20, 2) sits far above and to the right of the CPU Partner at
# (12, 12): on open ground, the nearest Firing Position is straight below it
# at (20, 12).
FAR_ENEMY = (20, 2)
# Steel right under FAR_ENEMY spoils every Firing Position below it in its
# column, leaving only those in its row (and the one right above it).
STEEL_UNDER_FAR_ENEMY = {(x, y): TileType.STEEL for x in (20, 21) for y in (6, 7)}

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
                enemies=[FAR_ENEMY],
                tiles=wall_row((10, 11), TileType.BRICK, gaps=(10, 11))
                | STEEL_UNDER_FAR_ENEMY,
            )
        )
        assert cpu.get_movement_direction() == Direction.LEFT.delta
        assert cpu.consume_shoot() is False

    def test_shoots_through_a_brick_wall_when_the_detour_is_long(self, cpu) -> None:
        cpu.observe(
            make_view(
                own=(12, 12, Direction.UP),
                enemies=[FAR_ENEMY],
                tiles=BRICK_WALL_OVER_CORRIDOR | STEEL_UNDER_FAR_ENEMY,
            )
        )
        assert cpu.get_movement_direction() == Direction.UP.delta
        assert cpu.consume_shoot() is True

    def test_turns_to_face_a_brick_before_shooting_it(self, cpu) -> None:
        cpu.observe(
            make_view(
                own=(12, 12, Direction.LEFT),
                enemies=[FAR_ENEMY],
                tiles=BRICK_WALL_OVER_CORRIDOR | STEEL_UNDER_FAR_ENEMY,
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
    blocker: tuple[int, int] | None = (10, 12),
    human: tuple[float, float] = (0, 24),
    tiles: dict[Cell, TileType] = TWO_GAP_WALL,
) -> WorldView:
    """The CPU Partner at (12, 12) hunting the Enemy at (12, 2) past a wall.

    A frozen Enemy is parked at ``blocker`` (just left of the CPU Partner by
    default; none if ``None``) and the Human Player at ``human``.
    """
    return replace(
        make_view(
            own=(12, 12, Direction.LEFT),
            enemies=[(12, 2)] + ([blocker] if blocker else []),
            human=human,
            tiles=tiles,
        ),
        enemies_frozen=True,
    )


def observe_stuck(
    cpu: CpuPartnerInput, frames: int, view: WorldView | None = None
) -> None:
    """Feed ``frames`` frames of the CPU Partner not moving from its spot."""
    for _ in range(frames):
        cpu.observe(view or blocked_view())


STUCK_FRAMES = int(CPU_PARTNER_STUCK_TIME * FPS)


@pytest.fixture
def hunting(cpu) -> CpuPartnerInput:
    """A CPU Partner already heading for the left gap to hunt the Enemy."""
    cpu.observe(blocked_view(blocker=None))
    assert cpu.get_movement_direction() == Direction.LEFT.delta
    return cpu


class TestCpuPartnerBlocked:
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
        hunting.observe(blocked_view(blocker=(10, 16)))
        assert hunting.get_movement_direction() == Direction.LEFT.delta

    def test_does_not_route_around_an_enemy_that_is_not_in_its_way(
        self, hunting
    ) -> None:
        # Held in place (by anything) while a frozen Enemy sits in the far
        # gap: that Enemy isn't what is stopping it, so the route stays.
        far_in_the_gap = (9, 10)
        observe_stuck(hunting, STUCK_FRAMES + 1, blocked_view(blocker=far_in_the_gap))
        assert hunting.get_movement_direction() == Direction.LEFT.delta


# The Human Player parked just left of the CPU Partner, on its way to the
# left gap.
HUMAN_IN_THE_WAY = blocked_view(blocker=None, human=(10, 12))


class TestCpuPartnerGivesWayToHuman:
    def test_takes_another_route_when_blocked_by_the_human(self, hunting) -> None:
        observe_stuck(hunting, STUCK_FRAMES + 1, HUMAN_IN_THE_WAY)
        assert hunting.get_movement_direction() == Direction.RIGHT.delta

    def test_keeps_the_detour_while_the_human_shuffles_in_place(self, hunting) -> None:
        observe_stuck(hunting, STUCK_FRAMES + 1, HUMAN_IN_THE_WAY)
        one_px_over = 10 + 1 / SUB_TILE_SIZE
        hunting.observe(blocked_view(blocker=None, human=(one_px_over, 12)))
        assert hunting.get_movement_direction() == Direction.RIGHT.delta

    def test_waits_when_the_human_blocks_the_only_way(self, cpu) -> None:
        one_gap = wall_row((10, 11), TileType.STEEL, gaps=(9, 10))
        cpu.observe(blocked_view(blocker=None, tiles=one_gap))
        assert cpu.get_movement_direction() == Direction.LEFT.delta
        in_the_way = blocked_view(blocker=None, human=(10, 12), tiles=one_gap)
        observe_stuck(cpu, STUCK_FRAMES + 1, in_the_way)
        assert cpu.get_movement_direction() == (0, 0)
        cpu.observe(in_the_way)
        assert cpu.get_movement_direction() == (0, 0)
        cpu.observe(blocked_view(blocker=None, human=(0, 24), tiles=one_gap))
        assert cpu.get_movement_direction() == Direction.LEFT.delta

    def test_blocked_by_an_enemy_does_not_route_around_the_human_beside_it(
        self, hunting
    ) -> None:
        # The Enemy on its left stops it; the Human Player merely stands on
        # its right, on the way to the other gap. Only the Enemy is routed
        # around, so it heads right past the Human Player.
        observe_stuck(hunting, STUCK_FRAMES + 1, blocked_view(human=(14, 12)))
        assert hunting.get_movement_direction() == Direction.RIGHT.delta


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


# A wall across rows 8-9 between the CPU Partner and FAR_ENEMY, open only at
# the far left.
def wall_under_far_enemy(tile: TileType) -> dict[Cell, TileType]:
    return wall_row((8, 9), tile, gaps=(0, 1))


class TestCpuPartnerFiringPosition:
    @pytest.mark.parametrize("wall", [TileType.WATER, TileType.BRICK])
    def test_heads_for_the_cheapest_firing_position(self, cpu, wall) -> None:
        # Rather than drive round through the far-left gap, it lines up under
        # the Enemy to shoot across water or through brick.
        cpu.observe(
            make_view(
                own=(12, 12, Direction.UP),
                enemies=[FAR_ENEMY],
                tiles=wall_under_far_enemy(wall),
            )
        )
        assert cpu.get_movement_direction() == Direction.RIGHT.delta
        assert cpu.consume_shoot() is False

    def test_rejects_a_firing_position_behind_steel(self, cpu) -> None:
        # With no Firing Position below the Enemy, it goes up to its row.
        cpu.observe(
            make_view(
                own=(12, 12, Direction.UP),
                enemies=[FAR_ENEMY],
                tiles=STEEL_UNDER_FAR_ENEMY,
            )
        )
        assert cpu.get_movement_direction() == Direction.UP.delta

    def test_picks_a_new_firing_position_when_the_target_moves(self, cpu) -> None:
        water = wall_under_far_enemy(TileType.WATER)
        cpu.observe(
            make_view(own=(20, 12, Direction.UP), enemies=[FAR_ENEMY], tiles=water)
        )
        assert cpu.consume_shoot() is True
        cpu.observe(
            make_view(own=(20, 12, Direction.UP), enemies=[(24, 2)], tiles=water)
        )
        assert cpu.consume_shoot() is False
        assert cpu.get_movement_direction() == Direction.RIGHT.delta


# The CPU Partner in the top-left corner, facing down at DECOY, the Enemy it
# would Hunt. A second Enemy stands where the test puts it.
DECOY = (2, 8)


def threat_view(
    enemy: tuple[int, int],
    wall: TileType | None = TileType.BRICK,
    extra_tiles: dict[Cell, TileType] | None = None,
) -> WorldView:
    """The mid-field Base, the CPU Partner lined up on DECOY, and ``enemy``."""
    return make_view(
        own=(2, 2, Direction.DOWN),
        enemies=[DECOY, enemy],
        tiles=base_tiles(wall) | (extra_tiles or {}),
        base_cells=BASE,
        base_wall_cells=BASE_WALL,
    )


def leaves_decoy(cpu: CpuPartnerInput) -> bool:
    """Whether it left DECOY alone this frame (so went after the other Enemy)."""
    return not cpu.consume_shoot() and cpu.get_movement_direction() != (0, 0)


class TestCpuPartnerBaseThreat:
    @pytest.mark.parametrize(
        "enemy, is_threat",
        [
            ((8, 12), True),  # ~6 sub-tiles from the Base
            ((3, 10), False),  # ~11 sub-tiles away, off the Base's row and column
        ],
    )
    def test_defends_against_an_enemy_close_to_the_base(
        self, cpu, enemy, is_threat
    ) -> None:
        cpu.observe(threat_view(enemy))
        assert leaves_decoy(cpu) is is_threat

    # (12, 2) is far from the Base but in its column: only the Base Wall, or
    # whatever else the test adds, stands between them.
    @pytest.mark.parametrize(
        "wall, extra_tiles, is_threat",
        [
            (TileType.BRICK, {}, True),
            (None, {}, True),
            (TileType.BRICK, {(x, 8): TileType.WATER for x in (12, 13)}, True),
            (TileType.STEEL, {}, False),
        ],
    )
    def test_defends_against_an_enemy_with_a_line_of_fire_to_the_base(
        self, cpu, wall, extra_tiles, is_threat
    ) -> None:
        cpu.observe(threat_view((12, 2), wall=wall, extra_tiles=extra_tiles))
        assert leaves_decoy(cpu) is is_threat

    def test_an_enemy_just_off_the_base_column_is_no_threat(self, cpu) -> None:
        # Its bullet would fly past the Base's left edge.
        cpu.observe(threat_view((10, 2), wall=None))
        assert leaves_decoy(cpu) is False

    def test_defends_against_the_threat_nearest_the_base(self, cpu) -> None:
        # Two threats: (0, 16) in the Base's row, reached by heading left,
        # and (8, 12), nearer the Base and reached by heading right.
        view = threat_view((0, 16))
        near = EnemyView(enemy_id=9, x=cell(8), y=cell(12), direction=Direction.DOWN)
        cpu.observe(replace(view, enemies=(*view.enemies, near)))
        assert cpu.get_movement_direction() == Direction.RIGHT.delta


STICKY_FRAMES = int(CPU_PARTNER_GOAL_STICKINESS * FPS)
NEAR_BASE = (8, 12)


# DECOY for it to Hunt, with and without an Enemy near the Base.
WITH_THREAT = threat_view(NEAR_BASE)
NO_THREAT = replace(WITH_THREAT, enemies=WITH_THREAT.enemies[:1])


class TestCpuPartnerGoalStickiness:
    def test_keeps_hunting_until_the_threat_has_lasted(self, cpu) -> None:
        cpu.observe(NO_THREAT)
        for _ in range(STICKY_FRAMES - 1):
            cpu.observe(WITH_THREAT)
            assert leaves_decoy(cpu) is False
        cpu.observe(WITH_THREAT)
        assert leaves_decoy(cpu) is True

    def test_ignores_a_threat_that_flickers(self, cpu) -> None:
        cpu.observe(NO_THREAT)
        for _ in range(3):
            for _ in range(STICKY_FRAMES - 1):
                cpu.observe(WITH_THREAT)
                assert leaves_decoy(cpu) is False
            cpu.observe(NO_THREAT)

    def test_keeps_defending_for_a_while_once_the_threat_passes(self, cpu) -> None:
        cpu.observe(WITH_THREAT)
        # The Enemy drives away from the Base, off its row and column.
        away = threat_view((20, 2))
        for _ in range(STICKY_FRAMES - 1):
            cpu.observe(away)
            assert leaves_decoy(cpu) is True
        cpu.observe(away)
        assert leaves_decoy(cpu) is False

    def test_hunts_at_once_when_the_threat_dies(self, cpu) -> None:
        cpu.observe(WITH_THREAT)
        cpu.observe(NO_THREAT)
        assert leaves_decoy(cpu) is False


# A ring of steel around (7, 11), near the Base: nothing inside can be
# reached by bullet or tank.
STEEL_RING = {
    (x, y): TileType.STEEL
    for x in range(6, 10)
    for y in range(10, 14)
    if x in (6, 9) or y in (10, 13)
}


class TestCpuPartnerUnreachableThreat:
    def test_hunts_instead_when_the_threat_is_sealed_off(self, cpu) -> None:
        view = threat_view((7, 11), extra_tiles=STEEL_RING)
        for _ in range(3):
            cpu.observe(view)
        assert cpu.consume_shoot() is True

    def test_defends_once_the_threat_moves_where_it_can_be_reached(self, cpu) -> None:
        for _ in range(3):
            cpu.observe(threat_view((7, 11), extra_tiles=STEEL_RING))
        # The same Enemy, now outside the ring and still near the Base.
        out = threat_view((11, 11), extra_tiles=STEEL_RING)
        for _ in range(STICKY_FRAMES):
            cpu.observe(out)
        assert leaves_decoy(cpu) is True


def with_power_up(
    view: WorldView, at: Cell, power_up_type: PowerUpType = PowerUpType.STAR
) -> WorldView:
    """``view`` with a Power-Up of ``power_up_type`` added at sub-tile ``at``."""
    power_up = PowerUpView(x=cell(at[0]), y=cell(at[1]), power_up_type=power_up_type)
    return replace(view, power_ups=(*view.power_ups, power_up))


# The CPU Partner at (12, 12), lined up on an Enemy straight above it that
# it would otherwise shoot.
LINED_UP = make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)])
# The Power-Up column where the CPU Partner, driving right along row 12,
# first touches it after exactly CPU_PARTNER_POWER_UP_RANGE steps.
EDGE_OF_RANGE = 12 + CPU_PARTNER_POWER_UP_RANGE + 1


def grabbing(cpu: CpuPartnerInput) -> bool:
    """Whether it went right for the Power-Up rather than shoot the Enemy."""
    return (
        not cpu.consume_shoot()
        and cpu.get_movement_direction() == Direction.RIGHT.delta
    )


class TestCpuPartnerGrabPowerUp:
    @pytest.mark.parametrize("power_up_type", list(PowerUpType))
    def test_grabs_a_nearby_power_up_of_any_type_before_hunting(
        self, cpu, power_up_type
    ) -> None:
        cpu.observe(with_power_up(LINED_UP, (16, 12), power_up_type))
        assert grabbing(cpu)

    @pytest.mark.parametrize(
        "column, grabs",
        [(EDGE_OF_RANGE, True), (EDGE_OF_RANGE + 1, False)],
    )
    def test_only_grabs_a_power_up_within_range(self, cpu, column, grabs) -> None:
        cpu.observe(with_power_up(LINED_UP, (column, 12)))
        assert grabbing(cpu) is grabs

    def test_brick_on_the_way_counts_toward_the_range(self, cpu) -> None:
        # In range by steps, but shooting through the brick makes it too far.
        brick = {(x, y): TileType.BRICK for x in (14, 15) for y in range(GRID)}
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)], tiles=brick)
        cpu.observe(with_power_up(view, (EDGE_OF_RANGE - 2, 12)))
        assert grabbing(cpu) is False

    def test_ignores_a_power_up_it_cannot_reach(self, cpu) -> None:
        ring = {
            (x, y): TileType.STEEL
            for x in range(15, 20)
            for y in range(10, 16)
            if x in (15, 19) or y in (10, 15)
        }
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)], tiles=ring)
        cpu.observe(with_power_up(view, (16, 12)))
        assert grabbing(cpu) is False

    def test_hunts_at_once_when_the_power_up_is_gone(self, cpu) -> None:
        cpu.observe(with_power_up(LINED_UP, (16, 12)))
        cpu.observe(LINED_UP)
        assert cpu.consume_shoot() is True


class TestCpuPartnerDefendOverridesGrab:
    @pytest.mark.parametrize(
        "view, heading",
        [(NO_THREAT, Direction.UP), (WITH_THREAT, Direction.RIGHT)],
    )
    def test_defends_rather_than_grab_a_power_up(self, cpu, view, heading) -> None:
        # A Power-Up right above it, one step away; the Base Threat, if any,
        # lies below and to the right.
        cpu.observe(with_power_up(view, (2, 0)))
        assert cpu.get_movement_direction() == heading.delta
        assert cpu.consume_shoot() is False


def with_spawns(view: WorldView, *spawns: Cell) -> WorldView:
    """``view`` with Enemy Spawn Points at the sub-tiles ``spawns``."""
    return replace(view, enemy_spawn_points=spawns)


class TestCpuPartnerAmbush:
    def test_heads_for_a_spawn_point_when_there_is_nothing_else_to_do(
        self, cpu
    ) -> None:
        # Its nearest Firing Position on the spawn point is (12, 12).
        cpu.observe(with_spawns(make_view(own=(20, 12, Direction.UP)), (12, 0)))
        assert cpu.get_movement_direction() == Direction.LEFT.delta
        assert cpu.consume_shoot() is False

    def test_hunts_rather_than_ambush(self, cpu) -> None:
        cpu.observe(with_spawns(LINED_UP, (24, 12)))
        assert cpu.consume_shoot() is True

    def test_covers_the_spawn_point_nearest_by_path(self, cpu) -> None:
        # (12, 2) is nearer as the crow flies, but steel walls it off; (24, 12)
        # is in its row already, so it only turns to face it.
        steel = {(x, y): TileType.STEEL for x in range(2, GRID) for y in (8, 9)}
        view = make_view(own=(12, 12, Direction.UP), tiles=steel)
        cpu.observe(with_spawns(view, (12, 2), (24, 12)))
        assert cpu.get_movement_direction() == Direction.RIGHT.delta

    def test_turns_to_face_the_spawn_point_once_in_position(self, cpu) -> None:
        view = with_spawns(make_view(own=(12, 12, Direction.LEFT)), (12, 0))
        cpu.observe(view)
        assert cpu.get_movement_direction() == Direction.UP.delta

    def test_waits_facing_the_spawn_point(self, cpu) -> None:
        cpu.observe(with_spawns(make_view(own=(12, 12, Direction.UP)), (12, 0)))
        assert cpu.get_movement_direction() == (0, 0)
        assert cpu.consume_shoot() is False

    def test_keeps_its_spawn_point_while_ambushing(self, cpu) -> None:
        spawns = ((12, 0), (0, 20))
        cpu.observe(with_spawns(make_view(own=(12, 12, Direction.UP)), *spawns))
        # (0, 20) is now nearer, but it still heads for (12, 20) to cover
        # (12, 0), rather than turn left to face (0, 20).
        cpu.observe(with_spawns(make_view(own=(4, 20, Direction.UP)), *spawns))
        assert cpu.get_movement_direction() == Direction.RIGHT.delta

    def test_picks_the_nearest_spawn_point_again_after_another_goal(self, cpu) -> None:
        spawns = ((12, 0), (0, 20))
        cpu.observe(with_spawns(make_view(own=(12, 12, Direction.UP)), *spawns))
        cpu.observe(
            with_spawns(
                make_view(own=(4, 20, Direction.UP), enemies=[(20, 2)]), *spawns
            )
        )
        cpu.observe(with_spawns(make_view(own=(4, 20, Direction.UP)), *spawns))
        assert cpu.get_movement_direction() == Direction.LEFT.delta

    def test_fires_at_once_on_an_enemy_arriving_at_its_spawn_point(self, cpu) -> None:
        cpu.observe(with_spawns(make_view(own=(12, 12, Direction.UP)), (12, 0)))
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 0)])
        cpu.observe(with_spawns(view, (12, 0)))
        assert cpu.consume_shoot() is True


class TestAmbushPositions:
    def test_are_in_the_spawn_points_row_or_column_at_a_distance(self) -> None:
        view = with_spawns(make_view(own=(20, 20, Direction.UP)), (12, 0))
        positions = ambush_positions(view, view.own_player, (12, 0))
        assert (12, CPU_PARTNER_AMBUSH_DISTANCE) in positions
        assert (12 + CPU_PARTNER_AMBUSH_DISTANCE, 0) in positions
        assert (12, CPU_PARTNER_AMBUSH_DISTANCE - 1) not in positions
        assert (12 - CPU_PARTNER_AMBUSH_DISTANCE + 1, 0) not in positions
        assert all(x == 12 or y == 0 for x, y in positions)

    def test_never_stand_on_an_enemy_spawn_point(self) -> None:
        view = with_spawns(make_view(own=(20, 20, Direction.UP)), (12, 0), (12, 8))
        positions = ambush_positions(view, view.own_player, (12, 0))
        # A tank at (12, 7) to (12, 9) would overlap the spawn point at (12, 8).
        assert {(12, 7), (12, 8), (12, 9)}.isdisjoint(positions)
        assert {(12, 6), (12, 10)} <= positions
