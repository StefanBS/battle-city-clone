from unittest.mock import patch, MagicMock

import pygame
import pytest

from src.managers.sound_manager import SoundManager


@pytest.fixture
def mock_pygame():
    """Patch pygame in the sound module: every Sound and found channel is one mock."""
    with patch("src.managers.sound_manager.pygame") as mock_pg:
        mock_pg.mixer.Sound.return_value = MagicMock(spec=pygame.mixer.Sound)
        mock_pg.mixer.find_channel.return_value = MagicMock(spec=pygame.mixer.Channel)
        yield mock_pg


@pytest.fixture
def mock_sound(mock_pygame):
    return mock_pygame.mixer.Sound.return_value


@pytest.fixture
def mock_channel(mock_pygame):
    return mock_pygame.mixer.find_channel.return_value


@pytest.fixture
def sm(mock_pygame):
    return SoundManager()


@pytest.fixture
def disabled_sm():
    """A SoundManager whose mixer failed to initialize."""
    with patch("src.managers.sound_manager.pygame") as mock_pg:
        mock_pg.error = type("error", (Exception,), {})
        mock_pg.mixer.init.side_effect = mock_pg.error("no audio")
        yield SoundManager()


class TestSoundManager:
    def test_init_enabled_with_valid_sounds(self, sm):
        assert sm._enabled is True

    def test_init_disabled_on_mixer_error(self, disabled_sm):
        assert disabled_sm._enabled is False

    def test_play_noop_when_disabled(self, disabled_sm):
        disabled_sm.play("shoot")  # should not raise

    def test_play_calls_sound_play(self, sm, mock_sound):
        sm.play("shoot")
        mock_sound.play.assert_called()

    def test_play_unknown_name_is_noop(self, sm):
        sm.play("nonexistent")  # should not raise


class TestLoopManagement:
    def test_start_loop_plays_on_channel(self, sm, mock_sound, mock_channel):
        sm._start_loop("shoot")  # use existing sound key for test
        mock_channel.play.assert_called_once_with(mock_sound, loops=-1)
        assert "shoot" in sm._looping_channels

    def test_start_loop_noop_when_already_looping(self, sm, mock_channel):
        sm._start_loop("shoot")
        mock_channel.play.reset_mock()
        sm._start_loop("shoot")
        mock_channel.play.assert_not_called()

    def test_start_loop_noop_when_disabled(self, disabled_sm):
        disabled_sm._start_loop("shoot")
        assert len(disabled_sm._looping_channels) == 0

    def test_start_loop_noop_when_no_channel_available(self, sm, mock_pygame):
        mock_pygame.mixer.find_channel.return_value = None
        sm._start_loop("shoot")
        assert "shoot" not in sm._looping_channels

    def test_start_loop_noop_for_unknown_sound(self, sm):
        sm._start_loop("nonexistent")
        assert len(sm._looping_channels) == 0

    def test_stop_loop_fades_out_channel(self, sm, mock_channel):
        sm._start_loop("shoot")
        sm._stop_loop("shoot")
        mock_channel.fadeout.assert_called_once_with(50)
        assert "shoot" not in sm._looping_channels

    def test_stop_loop_noop_when_not_looping(self, sm):
        sm._stop_loop("shoot")  # should not raise

    def test_stop_loops_stops_all_active_loops(self, sm, mock_pygame):
        channel_a = MagicMock(spec=pygame.mixer.Channel)
        channel_b = MagicMock(spec=pygame.mixer.Channel)
        mock_pygame.mixer.find_channel.side_effect = [channel_a, channel_b]
        sm._start_loop("shoot")
        sm._start_loop("explosion")
        sm.stop_loops()
        channel_a.fadeout.assert_called_once_with(50)
        channel_b.fadeout.assert_called_once_with(50)
        assert len(sm._looping_channels) == 0


@pytest.mark.parametrize(
    "method, sound_key",
    [
        (SoundManager.update_engine, "engine"),
        (SoundManager.update_powerup_blink, "powerup_spawn"),
    ],
)
class TestLoopToggles:
    def test_true_starts_loop(self, sm, method, sound_key):
        method(sm, True)
        assert sound_key in sm._looping_channels

    def test_false_stops_loop(self, sm, mock_channel, method, sound_key):
        method(sm, True)
        method(sm, False)
        assert sound_key not in sm._looping_channels
        mock_channel.fadeout.assert_called_once_with(50)

    def test_repeated_true_is_noop(self, sm, mock_channel, method, sound_key):
        method(sm, True)
        mock_channel.play.reset_mock()
        method(sm, True)
        mock_channel.play.assert_not_called()


class TestMasterVolume:
    def test_set_master_volume_applies_to_sounds(self, sm, mock_sound):
        sm.set_master_volume(0.3)
        mock_sound.set_volume.assert_called_with(0.3)

    def test_set_master_volume_applies_to_looping_channels(self, sm, mock_channel):
        sm._start_loop("engine")
        sm.set_master_volume(0.4)
        mock_channel.set_volume.assert_called_with(0.4)

    def test_init_with_master_volume(self, mock_pygame, mock_sound):
        sm = SoundManager(master_volume=0.6)
        assert sm._master_volume == 0.6
        mock_sound.set_volume.assert_called_with(0.6)

    def test_start_loop_applies_master_volume_to_channel(
        self, mock_pygame, mock_channel
    ):
        sm = SoundManager(master_volume=0.7)
        sm._start_loop("engine")
        mock_channel.set_volume.assert_called_with(0.7)

    @pytest.mark.parametrize("volume, expected", [(1.5, 1.0), (-0.3, 0.0)])
    def test_set_master_volume_clamps(self, sm, mock_sound, volume, expected):
        sm.set_master_volume(volume)
        mock_sound.set_volume.assert_called_with(expected)
