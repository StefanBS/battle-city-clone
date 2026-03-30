from src.utils.level_data import STAGE_ENEMIES


def test_has_35_stages():
    """STAGE_ENEMIES should have exactly 35 entries."""
    assert len(STAGE_ENEMIES) == 35


def test_each_stage_sums_to_20():
    """Each stage tuple should sum to 20 enemies."""
    for i, stage in enumerate(STAGE_ENEMIES):
        assert sum(stage) == 20, f"Stage {i + 1} sums to {sum(stage)}, expected 20"


def test_no_negative_counts():
    """No stage should have negative enemy counts."""
    for i, stage in enumerate(STAGE_ENEMIES):
        for count in stage:
            assert count >= 0, f"Stage {i + 1} has negative count: {stage}"


def test_each_stage_has_four_types():
    """Each stage tuple should have exactly 4 elements."""
    for i, stage in enumerate(STAGE_ENEMIES):
        assert len(stage) == 4, f"Stage {i + 1} has {len(stage)} elements"
