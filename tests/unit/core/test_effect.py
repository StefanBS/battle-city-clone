import pytest
import pygame
from unittest.mock import MagicMock
from src.core.effect import Effect


class TestEffect:
    @pytest.fixture
    def frames(self):
        """Create 3 mock frames of different sizes."""
        return [
            pygame.Surface((32, 32)),
            pygame.Surface((32, 32)),
            pygame.Surface((64, 64)),
        ]

    def test_initial_state(self, frames):
        effect = Effect(100.0, 200.0, frames, frame_duration=0.1)
        assert effect.active is True
        assert effect.current_frame == 0
        assert effect.x == 100.0
        assert effect.y == 200.0

    def test_frame_advances_after_duration(self, frames):
        effect = Effect(0, 0, frames, frame_duration=0.1)
        effect.update(0.1)
        assert effect.current_frame == 1
        assert effect.active is True

    def test_stays_on_frame_before_duration(self, frames):
        effect = Effect(0, 0, frames, frame_duration=0.1)
        effect.update(0.05)
        assert effect.current_frame == 0

    def test_deactivates_after_last_frame(self, frames):
        effect = Effect(0, 0, frames, frame_duration=0.1)
        effect.update(0.1)  # frame 1
        effect.update(0.1)  # frame 2
        effect.update(0.1)  # past last frame
        assert effect.active is False

    def test_multiple_frames_in_one_update(self, frames):
        effect = Effect(0, 0, frames, frame_duration=0.1)
        effect.update(0.25)  # should advance 2 frames (0.25 / 0.1 = 2.5)
        assert effect.current_frame == 2
        assert effect.active is True

    @pytest.mark.parametrize(
        "dt, frame_index, expected_pos",
        [
            (0.0, 0, (100 - 32 // 2, 100 - 32 // 2)),
            (0.2, 2, (100 - 64 // 2, 100 - 64 // 2)),
        ],
    )
    def test_draw_centers_frame_on_position(
        self, frames, dt, frame_index, expected_pos
    ):
        surface = MagicMock(spec=pygame.Surface)
        effect = Effect(100.0, 100.0, frames, frame_duration=0.1)
        effect.update(dt)

        effect.draw(surface)

        surface.blit.assert_called_once_with(frames[frame_index], expected_pos)

    def test_draw_does_nothing_when_inactive(self, frames):
        surface = MagicMock(spec=pygame.Surface)
        effect = Effect(100.0, 100.0, frames, frame_duration=0.1)
        effect.active = False

        effect.draw(surface)

        surface.blit.assert_not_called()

    def test_single_frame_effect(self):
        frames = [pygame.Surface((32, 32))]
        effect = Effect(0, 0, frames, frame_duration=0.1)
        assert effect.active is True
        effect.update(0.1)
        assert effect.active is False
