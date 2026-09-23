import pytest

from src.managers.refused_shots import RefusedShots


def refuse_for(refused: RefusedShots, enemy_id: int, frames: int) -> list[bool]:
    """Whether it gives up in each of ``frames`` frames refusing to shoot."""
    results = []
    for _ in range(frames):
        refused.start_frame()
        results.append(refused.refuse(enemy_id))
    return results


class TestRefusedShots:
    @pytest.fixture
    def refused(self) -> RefusedShots:
        return RefusedShots(frames=3)

    def test_gives_up_after_refusing_for_long_enough(self, refused) -> None:
        assert refuse_for(refused, 1, 3) == [False, False, True]

    def test_counts_afresh_after_giving_up(self, refused) -> None:
        refuse_for(refused, 1, 3)
        assert refuse_for(refused, 1, 3) == [False, False, True]

    def test_a_frame_without_refusing_starts_the_count_afresh(self, refused) -> None:
        refuse_for(refused, 1, 2)
        refused.start_frame()
        assert refuse_for(refused, 1, 3) == [False, False, True]

    def test_a_new_target_starts_the_count_afresh(self, refused) -> None:
        refuse_for(refused, 1, 2)
        assert refuse_for(refused, 2, 3) == [False, False, True]
