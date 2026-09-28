import pytest

from src.cpu_partner.cut_off import CutOff, RefusedShot
from src.world_view.world_view import WorldView
from src.utils.constants import Direction
from tests.unit.cpu_partner.world_views import make_view

FRAMES = 3


@pytest.fixture
def cut_off() -> CutOff:
    return CutOff(refused_shot_frames=FRAMES)


def refused_below(view: WorldView, enemy_id: int = 0) -> RefusedShot:
    """A Refused Shot held from below the Enemy, facing up at it."""
    own = view.own_player
    assert own is not None
    return RefusedShot(own, view.enemies[enemy_id], Direction.UP)


def refuse_for(
    cut_off: CutOff, view: WorldView, shot: RefusedShot | None, frames: int
) -> list[bool]:
    """Hold ``shot`` for ``frames`` frames; whether each left the Enemy Cut Off."""
    return [cut_off.refused(view, shot) for _ in range(frames)]


class TestCutOff:
    def test_gives_up_a_side_after_refusing_there_for_long_enough(
        self, cut_off
    ) -> None:
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 4)])
        enemy = view.enemies[0]
        refuse_for(cut_off, view, refused_below(view), FRAMES - 1)
        assert Direction.DOWN in cut_off.open_sides(enemy)

        cut_off.refused(view, refused_below(view))

        assert cut_off.open_sides(enemy) == [
            Direction.UP,
            Direction.LEFT,
            Direction.RIGHT,
        ]
        assert not cut_off.is_cut_off(enemy)

    def test_an_enemy_is_cut_off_once_every_side_is_given_up(self, cut_off) -> None:
        # In the corner, only its bottom and right sides have Firing Positions.
        view = make_view(own=(0, 12, Direction.UP), enemies=[(0, 0)])
        own, enemy = view.own_player, view.enemies[0]
        assert own is not None

        below = refuse_for(cut_off, view, RefusedShot(own, enemy, Direction.UP), FRAMES)
        right = refuse_for(
            cut_off, view, RefusedShot(own, enemy, Direction.LEFT), FRAMES
        )

        assert below == [False] * FRAMES
        assert right == [False] * (FRAMES - 1) + [True]
        assert cut_off.is_cut_off(enemy)

    def test_remembers_an_enemy_while_it_stays_where_it_stood(self, cut_off) -> None:
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 4), (20, 4)])
        refuse_for(cut_off, view, refused_below(view, 0), FRAMES)
        cut_off.cut_off(view, view.enemies[1])

        cut_off.forget_moved(view)

        assert Direction.DOWN not in cut_off.open_sides(view.enemies[0])
        assert cut_off.is_cut_off(view.enemies[1])

    @pytest.mark.parametrize(
        "enemies_after", [[(12, 6), (20, 6)], []], ids=["moved", "gone"]
    )
    def test_forgets_an_enemy_once_it_moves_or_leaves(
        self, cut_off, enemies_after
    ) -> None:
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 4), (20, 4)])
        refuse_for(cut_off, view, refused_below(view, 0), FRAMES)
        cut_off.cut_off(view, view.enemies[1])

        cut_off.forget_moved(
            make_view(own=(12, 12, Direction.UP), enemies=enemies_after)
        )

        assert cut_off.open_sides(view.enemies[0]) == list(Direction)
        assert not cut_off.is_cut_off(view.enemies[1])
