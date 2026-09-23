from unittest.mock import patch, MagicMock

import pygame
import pytest

from src.managers.sound_manager import SoundManager
from src.utils.constants import SOUND_FADEOUT_MS


@pytest.fixture
def mock_pygame():
    """Patch pygame in the sound module: every Sound and found channel is one mock."""
    with patch("src.managers.sound_manager.pygame") as mock_pg:
        mock_pg.error = pygame.error
        mock_pg.mixer.Sound.return_value = MagicMock(spec=pygame.mixer.Sound)
        mock_pg.mixer.find_channel.return_value = MagicMock(spec=pygame.mixer.Channel)
        yield mock_pg


@pytest.fixture
def mock_sound(mock_pygame):
    """The mock Sound returned for every loaded sound file."""
    return mock_pygame.mixer.Sound.return_value


@pytest.fixture
def mock_channel(mock_pygame):
    """The mock Channel returned whenever a free channel is requested."""
    return mock_pygame.mixer.find_channel.return_value


@pytest.fixture
def sound_manager(mock_pygame):
    """A SoundManager whose mixer initialized and loaded every sound."""
    return SoundManager()


@pytest.fixture
def fail_to_load(mock_pygame, mock_sound):
    """Make one sound file fail to load with the given error; others load."""

    def _fail(sound_file, error):
        def load(path):
            if path.endswith(sound_file):
                raise error
            return mock_sound

        mock_pygame.mixer.Sound.side_effect = load

    return _fail


@pytest.fixture
def disabled_sound_manager(mock_pygame):
    """A SoundManager whose mixer failed to initialize."""
    mock_pygame.mixer.init.side_effect = pygame.error("no audio")
    return SoundManager()


class TestPlay:
    def test_play_plays_the_sound(self, sound_manager, mock_sound):
        sound_manager.play("shoot")
        mock_sound.play.assert_called_once_with()

    def test_play_unknown_name_plays_nothing(self, sound_manager, mock_sound):
        sound_manager.play("nonexistent")
        mock_sound.play.assert_not_called()

    def test_sound_that_fails_to_load_is_skipped(self, fail_to_load, mock_sound):
        fail_to_load("shoot.wav", FileNotFoundError("shoot.wav"))
        sound_manager = SoundManager()
        sound_manager.play("shoot")
        mock_sound.play.assert_not_called()
        sound_manager.play("explosion")
        mock_sound.play.assert_called_once_with()


class TestDisabledMixer:
    def test_no_sound_is_loaded(self, disabled_sound_manager, mock_pygame):
        mock_pygame.mixer.Sound.assert_not_called()

    def test_every_call_leaves_the_mixer_untouched(
        self, disabled_sound_manager, mock_pygame, mock_channel
    ):
        disabled_sound_manager.play("shoot")
        disabled_sound_manager.update_engine(True)
        disabled_sound_manager.update_powerup_blink(True)
        disabled_sound_manager.set_master_volume(0.5)
        disabled_sound_manager.update_engine(False)
        disabled_sound_manager.update_powerup_blink(False)
        disabled_sound_manager.stop_loops()
        mock_pygame.mixer.find_channel.assert_not_called()
        assert mock_channel.method_calls == []


@pytest.mark.parametrize(
    "method, sound_file",
    [
        (SoundManager.update_engine, "engine.wav"),
        (SoundManager.update_powerup_blink, "powerup_spawn.wav"),
    ],
)
class TestLoopToggles:
    def test_true_loops_the_sound_on_a_channel(
        self, sound_manager, mock_sound, mock_channel, method, sound_file
    ):
        method(sound_manager, True)
        mock_channel.play.assert_called_once_with(mock_sound, loops=-1)

    def test_false_fades_out_the_channel(
        self, sound_manager, mock_channel, method, sound_file
    ):
        method(sound_manager, True)
        method(sound_manager, False)
        mock_channel.fadeout.assert_called_once_with(SOUND_FADEOUT_MS)

    def test_repeated_true_does_not_restart_the_loop(
        self, sound_manager, mock_pygame, mock_channel, method, sound_file
    ):
        method(sound_manager, True)
        method(sound_manager, True)
        mock_pygame.mixer.find_channel.assert_called_once_with()
        mock_channel.play.assert_called_once()

    def test_false_when_not_looping_fades_nothing(
        self, sound_manager, mock_channel, method, sound_file
    ):
        method(sound_manager, False)
        mock_channel.fadeout.assert_not_called()

    def test_unloaded_sound_requests_no_channel(
        self, fail_to_load, mock_pygame, method, sound_file
    ):
        fail_to_load(sound_file, pygame.error("bad file"))
        sound_manager = SoundManager()
        method(sound_manager, True)
        mock_pygame.mixer.find_channel.assert_not_called()

    def test_no_free_channel_retries_on_next_call(
        self, sound_manager, mock_pygame, mock_channel, method, sound_file
    ):
        mock_pygame.mixer.find_channel.return_value = None
        method(sound_manager, True)
        method(sound_manager, False)
        mock_pygame.mixer.find_channel.return_value = mock_channel
        method(sound_manager, True)
        assert mock_pygame.mixer.find_channel.call_count == 2
        mock_channel.play.assert_called_once()
        mock_channel.fadeout.assert_not_called()


class TestStopLoops:
    def test_fades_out_every_looping_channel(self, sound_manager, mock_pygame):
        engine_channel = MagicMock(spec=pygame.mixer.Channel)
        blink_channel = MagicMock(spec=pygame.mixer.Channel)
        mock_pygame.mixer.find_channel.side_effect = [engine_channel, blink_channel]
        sound_manager.update_engine(True)
        sound_manager.update_powerup_blink(True)
        sound_manager.stop_loops()
        engine_channel.fadeout.assert_called_once_with(SOUND_FADEOUT_MS)
        blink_channel.fadeout.assert_called_once_with(SOUND_FADEOUT_MS)

    def test_stopped_loops_are_not_faded_again(self, sound_manager, mock_channel):
        sound_manager.update_engine(True)
        sound_manager.stop_loops()
        sound_manager.update_engine(False)
        sound_manager.stop_loops()
        mock_channel.fadeout.assert_called_once_with(SOUND_FADEOUT_MS)

    def test_loop_can_restart_after_stop(self, sound_manager, mock_channel):
        sound_manager.update_engine(True)
        sound_manager.stop_loops()
        sound_manager.update_engine(True)
        assert mock_channel.play.call_count == 2


class TestMasterVolume:
    def test_start_up_volume_applies_to_sounds(self, mock_pygame, mock_sound):
        SoundManager(master_volume=0.6)
        mock_sound.set_volume.assert_called_with(0.6)

    def test_start_up_volume_applies_to_looping_channels(
        self, mock_pygame, mock_channel
    ):
        sound_manager = SoundManager(master_volume=0.7)
        sound_manager.update_engine(True)
        mock_channel.set_volume.assert_called_with(0.7)

    def test_set_master_volume_applies_to_sounds(self, sound_manager, mock_sound):
        sound_manager.set_master_volume(0.3)
        mock_sound.set_volume.assert_called_with(0.3)

    def test_set_master_volume_applies_to_looping_channels(
        self, sound_manager, mock_channel
    ):
        sound_manager.update_engine(True)
        sound_manager.set_master_volume(0.4)
        mock_channel.set_volume.assert_called_with(0.4)

    @pytest.mark.parametrize("volume, expected", [(1.5, 1.0), (-0.3, 0.0)])
    def test_set_master_volume_clamps(
        self, sound_manager, mock_sound, volume, expected
    ):
        sound_manager.set_master_volume(volume)
        mock_sound.set_volume.assert_called_with(expected)
