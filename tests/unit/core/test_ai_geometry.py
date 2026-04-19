import pytest

from src.core.ai_geometry import direction_moves_toward, is_aligned_with
from src.utils.constants import TILE_SIZE, Direction


class TestDirectionMovesToward:
    @pytest.mark.parametrize(
        "direction,target,expected",
        [
            (Direction.RIGHT, (100.0, 0.0), True),
            (Direction.RIGHT, (-100.0, 0.0), False),
            (Direction.LEFT, (-100.0, 0.0), True),
            (Direction.LEFT, (100.0, 0.0), False),
            (Direction.DOWN, (0.0, 100.0), True),
            (Direction.DOWN, (0.0, -100.0), False),
            (Direction.UP, (0.0, -100.0), True),
            (Direction.UP, (0.0, 100.0), False),
        ],
    )
    def test_cardinal_directions(self, direction, target, expected):
        assert direction_moves_toward((0.0, 0.0), direction, target) is expected

    def test_target_equals_position(self):
        pos = (50.0, 50.0)
        assert direction_moves_toward(pos, Direction.RIGHT, pos) is False
        assert direction_moves_toward(pos, Direction.UP, pos) is False


class TestIsAlignedWith:
    def test_facing_and_on_axis(self):
        result = is_aligned_with((0.0, 0.0), Direction.RIGHT, TILE_SIZE, (100.0, 0.0))
        assert result is True

    def test_facing_but_off_perpendicular_axis(self):
        off_y = 2 * TILE_SIZE
        result = is_aligned_with((0.0, 0.0), Direction.RIGHT, TILE_SIZE, (100.0, off_y))
        assert result is False

    def test_on_axis_but_facing_away(self):
        result = is_aligned_with((0.0, 0.0), Direction.RIGHT, TILE_SIZE, (-100.0, 0.0))
        assert result is False

    def test_vertical_alignment(self):
        pos = (0.0, 0.0)
        assert is_aligned_with(pos, Direction.DOWN, TILE_SIZE, (0.0, 100.0)) is True
        assert (
            is_aligned_with(pos, Direction.DOWN, TILE_SIZE, (TILE_SIZE, 100.0)) is True
        )
        assert (
            is_aligned_with(pos, Direction.DOWN, TILE_SIZE, (2 * TILE_SIZE, 100.0))
            is False
        )
