import pytest

from src.managers.pathfinding import Cell
from src.managers.steering import Steering, TankKey

LEFT = (-1, 0)
RIGHT = (1, 0)
ENEMY: TankKey = ("enemy", 1)
TARGET: TankKey = ("enemy", 2)
HUMAN: TankKey = ("player", 1)


def ahead_of(direction: tuple[int, int]) -> set[Cell]:
    """The cells a step ``direction`` from (10, 10): stands in for its footprint."""
    dx, dy = direction
    return {(10 + dx, 10 + dy)}


def stuck(steering: Steering, frames: int, movement: tuple[int, int] = LEFT) -> None:
    """Try to move ``movement`` for ``frames`` frames without getting anywhere."""
    for _ in range(frames):
        steering.track((10.0, 10.0), movement)


class TestSteeringStuck:
    @pytest.fixture
    def steering(self) -> Steering:
        return Steering(stuck_frames=3)

    def test_routes_around_no_one_until_stuck_long_enough(self, steering) -> None:
        stuck(steering, 3)
        assert steering.detour({ENEMY: {(9, 10)}}, ahead_of, None) == {}

    @pytest.mark.parametrize("pushing, in_the_way", [(LEFT, ENEMY), (RIGHT, HUMAN)])
    def test_routes_around_the_tank_ahead_the_way_it_kept_pushing(
        self, steering, pushing, in_the_way
    ) -> None:
        stuck(steering, 4, pushing)
        tanks = {ENEMY: {(9, 10)}, HUMAN: {(11, 10)}}
        assert steering.detour(tanks, ahead_of, None) == {in_the_way: tanks[in_the_way]}

    def test_does_not_route_around_its_target(self, steering) -> None:
        stuck(steering, 4)
        assert steering.detour({TARGET: {(9, 10)}}, ahead_of, TARGET) == {}

    def test_moving_starts_the_count_afresh(self, steering) -> None:
        stuck(steering, 3)
        steering.track((9.0, 10.0), LEFT)
        stuck(steering, 3)
        assert steering.detour({ENEMY: {(9, 10)}}, ahead_of, None) == {}

    def test_standing_still_on_purpose_is_not_being_stuck(self, steering) -> None:
        stuck(steering, 3)
        steering.track((10.0, 10.0), (0, 0))
        stuck(steering, 2)
        assert steering.detour({ENEMY: {(9, 10)}}, ahead_of, None) == {}

    def test_counts_afresh_after_picking_a_detour(self, steering) -> None:
        stuck(steering, 4)
        steering.detour({}, ahead_of, None)
        stuck(steering, 1)
        assert steering.detour({ENEMY: {(9, 10)}}, ahead_of, None) == {}


@pytest.fixture
def detouring() -> Steering:
    """Steering routing around the Enemy standing on (9, 10)."""
    steering = Steering(stuck_frames=1)
    stuck(steering, 2)
    assert steering.detour({ENEMY: {(9, 10)}}, ahead_of, None) == {ENEMY: {(9, 10)}}
    steering.track((10.0, 10.0), (0, 0))
    return steering


class TestSteeringDetourExpiry:
    def test_keeps_the_detour_while_the_tank_still_covers_a_cell_it_blocked(
        self, detouring
    ) -> None:
        shuffled = {(9, 10), (8, 10)}
        assert detouring.detour({ENEMY: shuffled}, ahead_of, None) == {ENEMY: shuffled}

    def test_drops_the_detour_once_the_tank_moves_off(self, detouring) -> None:
        assert detouring.detour({ENEMY: {(9, 14)}}, ahead_of, None) == {}
        # Even if it comes back later.
        assert detouring.detour({ENEMY: {(9, 10)}}, ahead_of, None) == {}

    def test_drops_the_detour_once_the_tank_is_gone(self, detouring) -> None:
        assert detouring.detour({}, ahead_of, None) == {}
        assert detouring.detour({ENEMY: {(9, 10)}}, ahead_of, None) == {}
