import pytest

from src.managers.refused_shots import RefusedShots


def refuse_for(refused_shots: RefusedShots, enemy_id: int, frames: int) -> list[bool]:
    """Whether it gives up in each of ``frames`` frames refusing to shoot."""
    return [refused_shots.should_give_up(enemy_id) for _ in range(frames)]


class TestRefusedShots:
    @pytest.fixture
    def refused_shots(self) -> RefusedShots:
        return RefusedShots(frames=3)

    def test_gives_up_after_refusing_for_long_enough(self, refused_shots) -> None:
        assert refuse_for(refused_shots, 1, 3) == [False, False, True]

    def test_counts_afresh_after_giving_up(self, refused_shots) -> None:
        refuse_for(refused_shots, 1, 3)
        assert refuse_for(refused_shots, 1, 3) == [False, False, True]

    def test_a_frame_without_refusing_starts_the_count_afresh(
        self, refused_shots
    ) -> None:
        refuse_for(refused_shots, 1, 2)
        assert refused_shots.should_give_up(None) is False
        assert refuse_for(refused_shots, 1, 3) == [False, False, True]

    def test_a_new_target_starts_the_count_afresh(self, refused_shots) -> None:
        refuse_for(refused_shots, 1, 2)
        assert refuse_for(refused_shots, 2, 3) == [False, False, True]
