from src.utils.animation import is_blink_visible


class TestIsBlinkVisible:
    def test_first_half_is_visible(self):
        assert is_blink_visible(0.0, 1.0)
        assert is_blink_visible(0.5, 1.0)

    def test_second_half_is_hidden(self):
        assert not is_blink_visible(1.0, 1.0)
        assert not is_blink_visible(1.5, 1.0)

    def test_cycle_wraps(self):
        # second cycle, first half
        assert is_blink_visible(2.0, 1.0)
        assert is_blink_visible(2.5, 1.0)
        # second cycle, second half
        assert not is_blink_visible(3.5, 1.0)

    def test_interval_boundary_is_hidden(self):
        # exactly at interval → start of hidden phase
        assert not is_blink_visible(1.0, 1.0)
