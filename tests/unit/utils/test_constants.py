import pytest

from src.utils.constants import Direction


class TestDirection:
    def test_has_only_the_four_directions_as_members(self):
        assert list(Direction) == [
            Direction.UP,
            Direction.DOWN,
            Direction.LEFT,
            Direction.RIGHT,
        ]

    @pytest.mark.parametrize(
        "direction, value, delta, opposite",
        [
            (Direction.UP, "up", (0, -1), Direction.DOWN),
            (Direction.DOWN, "down", (0, 1), Direction.UP),
            (Direction.LEFT, "left", (-1, 0), Direction.RIGHT),
            (Direction.RIGHT, "right", (1, 0), Direction.LEFT),
        ],
    )
    def test_value_delta_and_opposite(self, direction, value, delta, opposite):
        assert direction == value
        assert Direction(value) is direction
        assert direction.delta == delta
        assert direction.opposite is opposite
