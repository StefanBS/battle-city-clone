from dataclasses import replace
from unittest.mock import patch

import pytest

from src.core.tile import TileType
from src.managers.dodge import Dodge, DodgeMove
from src.managers.world_view import WorldView
from src.utils.constants import (
    CPU_PARTNER_DODGE_MISS_CHANCE,
    CPU_PARTNER_DODGE_REACTION_TIME,
    FPS,
    Direction,
    OwnerType,
)
from tests.unit.managers.world_views import (
    BASE,
    BASE_WALL,
    MIDDLE,
    SHOT_FROM_THE_LEFT,
    base_tiles,
    cell,
    enemy_bullet,
    make_view,
    with_bullets,
    with_own,
)


@pytest.fixture
def dodge() -> Dodge:
    """A Dodge without imperfection: it notices every shot at once."""
    return Dodge(reaction_frames=0, miss_chance=0)


def react_frames(dodge: Dodge, view: WorldView, frames: int) -> list[DodgeMove | None]:
    """React to ``view`` for ``frames`` frames; what it did each frame."""
    return [dodge.react(view) for _ in range(frames)]


SIDESTEPS = (
    DodgeMove(Direction.UP.delta, False),
    DodgeMove(Direction.DOWN.delta, False),
)


class TestDodgeSidestep:
    def test_sidesteps_a_shot_fired_from_across_the_map_only_once_it_is_near(
        self, dodge
    ) -> None:
        own = make_view(own=(12, 12, Direction.UP))
        far = enemy_bullet(cell(0), MIDDLE, Direction.RIGHT, speed=100)
        assert dodge.react(with_bullets(own, far)) is None
        assert dodge.react(with_bullets(own, replace(far, x=cell(8)))) in SIDESTEPS

    @pytest.mark.parametrize(
        "bullet, tiles, human",
        [
            # Flying away from it.
            (enemy_bullet(cell(6), MIDDLE, Direction.LEFT), {}, (0, 24)),
            # Its lane passes just above the tank.
            (enemy_bullet(cell(6), cell(12) - 4, Direction.RIGHT), {}, (0, 24)),
            # A brick or steel wall stops it first.
            (
                enemy_bullet(cell(6), MIDDLE, Direction.RIGHT),
                {(9, 12): TileType.BRICK, (9, 13): TileType.BRICK},
                (0, 24),
            ),
            # The Human Player stands in between and takes it.
            (enemy_bullet(cell(4), MIDDLE, Direction.RIGHT), {}, (8, 12)),
            # The Human Player's own bullet.
            (
                replace(
                    enemy_bullet(cell(6), MIDDLE, Direction.RIGHT),
                    owner_type=OwnerType.PLAYER,
                ),
                {},
                (0, 24),
            ),
        ],
        ids=["flying-away", "lane-misses", "brick", "human", "player-bullet"],
    )
    def test_ignores_bullets_that_are_no_incoming_shot(
        self, dodge, bullet, tiles, human
    ) -> None:
        view = make_view(own=(12, 12, Direction.UP), tiles=tiles, human=human)
        assert dodge.react(with_bullets(view, bullet)) is None


class TestDodgeWhichWay:
    @pytest.mark.parametrize(
        "lane_top, way",
        [(cell(12) + 2, Direction.DOWN), (cell(14) - 6, Direction.UP)],
        ids=["near-its-top", "near-its-bottom"],
    )
    def test_steps_the_short_way_out_of_the_lane(self, dodge, lane_top, way) -> None:
        view = with_bullets(
            make_view(own=(12, 12, Direction.LEFT)),
            enemy_bullet(cell(6), lane_top, Direction.RIGHT),
        )
        assert dodge.react(view) == DodgeMove(way.delta, False)

    @pytest.mark.parametrize(
        "blocker",
        [
            {"tiles": {(12, 14): TileType.STEEL, (13, 14): TileType.STEEL}},
            {"enemies": [(12, 14)]},
        ],
        ids=["steel", "enemy"],
    )
    def test_steps_the_long_way_when_the_short_way_is_blocked(
        self, dodge, blocker
    ) -> None:
        view = with_bullets(
            make_view(own=(12, 12, Direction.LEFT), **blocker),
            enemy_bullet(cell(4), cell(12) + 2, Direction.RIGHT),
        )
        assert dodge.react(view) == DodgeMove(Direction.UP.delta, False)

    def test_does_not_step_into_another_incoming_shots_lane(self, dodge) -> None:
        view = with_bullets(
            make_view(own=(12, 12, Direction.LEFT)),
            enemy_bullet(cell(4), cell(12) + 2, Direction.RIGHT, bullet_id=0),
            # Passing just below it: stepping down walks into its lane.
            enemy_bullet(cell(6), cell(14) + 2, Direction.RIGHT, bullet_id=1),
        )
        assert dodge.react(view) == DodgeMove(Direction.UP.delta, False)

    def test_does_not_step_toward_a_shot_already_coming_at_it(self, dodge) -> None:
        view = with_bullets(
            make_view(own=(12, 12, Direction.LEFT)),
            enemy_bullet(cell(6), cell(12) + 2, Direction.RIGHT, bullet_id=0),
            # Coming up its column, due after the first: stepping down would
            # bring it sooner.
            enemy_bullet(MIDDLE, cell(22), Direction.UP, bullet_id=1),
        )
        assert dodge.react(view) == DodgeMove(Direction.UP.delta, False)

    def test_dodges_the_shot_that_arrives_first(self, dodge) -> None:
        view = with_bullets(
            make_view(own=(12, 12, Direction.LEFT)),
            enemy_bullet(cell(4), cell(12) + 2, Direction.RIGHT, bullet_id=0),
            enemy_bullet(cell(12) + 2, cell(8), Direction.DOWN, bullet_id=1),
        )
        assert dodge.react(view) == DodgeMove(Direction.RIGHT.delta, False)


class TestDodgeShootDown:
    def test_shoots_down_a_shot_it_faces_and_holds_its_ground(self, dodge) -> None:
        view = with_bullets(
            make_view(own=(12, 12, Direction.LEFT)),
            enemy_bullet(cell(6), MIDDLE, Direction.RIGHT),
        )
        assert dodge.react(view) == DodgeMove((0, 0), True)

    def test_leaves_a_shot_it_shot_down_to_its_own_bullet(self, dodge) -> None:
        view = make_view(own=(12, 12, Direction.LEFT))
        assert dodge.react(with_bullets(view, SHOT_FROM_THE_LEFT)) == DodgeMove(
            (0, 0), True
        )
        # Its bullet is in flight now: at its Bullet Cap, it still doesn't
        # sidestep a shot its bullet is about to meet.
        at_cap = with_own(view, can_fire=False)
        nearer = replace(SHOT_FROM_THE_LEFT, x=cell(6) + 3)
        assert dodge.react(with_bullets(at_cap, nearer)) is None

    def test_sidesteps_when_at_its_bullet_cap(self, dodge) -> None:
        view = with_bullets(
            with_own(make_view(own=(12, 12, Direction.LEFT)), can_fire=False),
            enemy_bullet(cell(6), MIDDLE, Direction.RIGHT),
        )
        assert dodge.react(view) in SIDESTEPS

    def test_sidesteps_a_shot_that_would_only_clip_its_edge(self, dodge) -> None:
        # Its own bullet would fly past: the lanes don't meet.
        view = with_bullets(
            make_view(own=(12, 12, Direction.LEFT)),
            enemy_bullet(cell(6), cell(12) + 2, Direction.RIGHT),
        )
        assert dodge.react(view) == DodgeMove(Direction.DOWN.delta, False)

    def test_shoots_down_a_shot_coming_from_the_base(self, dodge) -> None:
        # Its Line of Fire runs into the Base Wall, but its bullet meets the
        # Enemy's first.
        view = with_bullets(
            make_view(
                own=(12, 8, Direction.DOWN),
                tiles=base_tiles(),
                base_cells=BASE,
                base_wall_cells=BASE_WALL,
            ),
            enemy_bullet(cell(12) + 14, cell(13), Direction.UP),
        )
        assert dodge.react(view) == DodgeMove((0, 0), True)


# Steel just above and below the CPU Partner at (12, 12): no room to sidestep.
HEMMED_IN = {(x, y): TileType.STEEL for x in (12, 13) for y in (11, 14)}


class TestDodgeLastResort:
    def test_turns_and_fires_when_too_late_to_step_aside(self, dodge) -> None:
        view = with_bullets(
            make_view(own=(12, 12, Direction.UP)),
            enemy_bullet(cell(12) - 12, MIDDLE, Direction.RIGHT),
        )
        assert dodge.react(view) == DodgeMove(Direction.LEFT.delta, True)

    def test_leaves_it_to_the_goal_when_nothing_would_help(self, dodge) -> None:
        # Hemmed in, and the shot would only clip its edge: firing back would
        # miss.
        view = with_bullets(
            make_view(own=(12, 12, Direction.UP), tiles=HEMMED_IN),
            enemy_bullet(cell(6), cell(12) + 2, Direction.RIGHT),
        )
        assert dodge.react(view) is None


def guarding_base_view(wall: TileType | None, can_fire: bool = True) -> WorldView:
    """The CPU Partner above the mid-field Base, a shot coming down on it."""
    view = make_view(
        own=(12, 8, Direction.LEFT),
        tiles=base_tiles(wall),
        base_cells=BASE,
        base_wall_cells=BASE_WALL,
    )
    return with_bullets(
        with_own(view, can_fire=can_fire),
        enemy_bullet(cell(12) + 14, cell(2), Direction.DOWN),
    )


class TestDodgeGuardingTheBase:
    def test_shoots_down_a_shot_that_would_go_on_to_hit_the_base(self, dodge) -> None:
        move = dodge.react(guarding_base_view(wall=None))
        assert move == DodgeMove(Direction.UP.delta, True)

    def test_takes_the_hit_when_it_cannot_shoot_it_down(self, dodge) -> None:
        move = dodge.react(guarding_base_view(wall=None, can_fire=False))
        assert move == DodgeMove((0, 0), False)

    def test_steps_aside_when_only_the_base_wall_lies_behind(self, dodge) -> None:
        assert dodge.react(guarding_base_view(wall=TileType.BRICK)) in (
            DodgeMove(Direction.LEFT.delta, False),
            DodgeMove(Direction.RIGHT.delta, False),
        )


class TestDodgeWhen:
    @pytest.mark.parametrize("condition", ["shielded", "frozen"])
    def test_does_not_dodge_while(self, dodge, condition) -> None:
        view = make_view(own=(12, 12, Direction.UP))
        shot = with_bullets(with_own(view, **{condition: True}), SHOT_FROM_THE_LEFT)
        assert dodge.react(shot) is None

    def test_does_not_dodge_off_the_battlefield(self, dodge) -> None:
        assert (
            dodge.react(with_bullets(make_view(own=None), SHOT_FROM_THE_LEFT)) is None
        )


# The CPU Partner at (12, 12), a shot passing just below it.
SHOT_BELOW = with_bullets(
    make_view(own=(12, 12, Direction.LEFT)),
    enemy_bullet(cell(6), cell(14), Direction.RIGHT),
)


class TestDodgeIsStepSafe:
    def test_a_step_into_a_shots_lane_is_not_safe(self, dodge) -> None:
        assert dodge.is_step_safe(SHOT_BELOW, Direction.DOWN.delta) is False

    @pytest.mark.parametrize(
        "movement", [Direction.UP.delta, Direction.LEFT.delta, (0, 0)]
    )
    def test_a_step_that_brings_no_shot_sooner_is_safe(self, dodge, movement) -> None:
        assert dodge.is_step_safe(SHOT_BELOW, movement) is True

    def test_any_step_is_safe_while_shielded(self, dodge) -> None:
        shielded = with_own(SHOT_BELOW, shielded=True)
        assert dodge.is_step_safe(shielded, Direction.DOWN.delta) is True

    def test_guards_against_shots_it_has_not_noticed(self) -> None:
        # Still inside its reaction time, and bound to miss the shot anyway.
        dodge = Dodge(reaction_frames=10, miss_chance=1)
        assert dodge.is_step_safe(SHOT_BELOW, Direction.DOWN.delta) is False


DODGE_REACTION_FRAMES = round(CPU_PARTNER_DODGE_REACTION_TIME * FPS)


class TestDodgeImperfection:
    @pytest.fixture
    def dodge(self) -> Dodge:
        return Dodge(reaction_frames=DODGE_REACTION_FRAMES, miss_chance=0)

    def test_takes_a_moment_to_notice_an_incoming_shot(self, dodge) -> None:
        view = with_bullets(make_view(own=(12, 12, Direction.UP)), SHOT_FROM_THE_LEFT)
        moves = react_frames(dodge, view, DODGE_REACTION_FRAMES)
        assert moves == [None] * DODGE_REACTION_FRAMES
        assert dodge.react(view) is not None

    def test_keeps_dodging_a_shot_it_has_noticed(self, dodge) -> None:
        view = with_bullets(make_view(own=(12, 12, Direction.UP)), SHOT_FROM_THE_LEFT)
        react_frames(dodge, view, DODGE_REACTION_FRAMES + 1)
        # A frame out of its lane (it just stepped clear) doesn't reset that.
        dodge.react(
            with_bullets(make_view(own=(12, 9, Direction.UP)), SHOT_FROM_THE_LEFT)
        )
        assert dodge.react(view) is not None

    @patch(
        "src.managers.dodge.random.random",
        return_value=CPU_PARTNER_DODGE_MISS_CHANCE - 0.01,
    )
    def test_misses_a_shot_for_its_whole_flight(self, random_) -> None:
        dodge = Dodge(reaction_frames=0, miss_chance=CPU_PARTNER_DODGE_MISS_CHANCE)
        view = with_bullets(make_view(own=(12, 12, Direction.UP)), SHOT_FROM_THE_LEFT)
        assert react_frames(dodge, view, 10) == [None] * 10
        assert random_.call_count == 1
        # Another bullet gets its own roll.
        random_.return_value = CPU_PARTNER_DODGE_MISS_CHANCE + 0.01
        other = replace(SHOT_FROM_THE_LEFT, bullet_id=1)
        assert dodge.react(with_bullets(view, other)) is not None
