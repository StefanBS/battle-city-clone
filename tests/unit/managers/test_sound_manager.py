from unittest.mock import patch, MagicMock
from src.managers.sound_manager import SoundManager


class TestSoundManager:
    def test_init_enabled_with_valid_sounds(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            sm = SoundManager()
            assert sm._enabled is True

    def test_init_disabled_on_mixer_error(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.error = type("error", (Exception,), {})
            mock_pg.mixer.init.side_effect = mock_pg.error("no audio")
            sm = SoundManager()
            assert sm._enabled is False

    def test_play_methods_noop_when_disabled(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.error = type("error", (Exception,), {})
            mock_pg.mixer.init.side_effect = mock_pg.error("no audio")
            sm = SoundManager()
            sm.play_shoot()
            sm.play_brick_hit()
            sm.play_explosion()
            sm.play_powerup()
            sm.play_game_over()

    def test_play_shoot_calls_sound_play(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_sound = MagicMock()
            mock_pg.mixer.Sound.return_value = mock_sound
            sm = SoundManager()
            sm.play_shoot()
            mock_sound.play.assert_called()


class TestLoopManagement:
    def test_start_loop_plays_on_channel(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_sound = MagicMock()
            mock_pg.mixer.Sound.return_value = mock_sound
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm._start_loop("shoot")  # use existing sound key for test
            mock_channel.play.assert_called_once_with(mock_sound, loops=-1)
            assert "shoot" in sm._looping_channels

    def test_start_loop_noop_when_already_looping(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_sound = MagicMock()
            mock_pg.mixer.Sound.return_value = mock_sound
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm._start_loop("shoot")
            mock_channel.play.reset_mock()
            sm._start_loop("shoot")
            mock_channel.play.assert_not_called()

    def test_start_loop_noop_when_disabled(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.error = type("error", (Exception,), {})
            mock_pg.mixer.init.side_effect = mock_pg.error("no audio")
            sm = SoundManager()
            sm._start_loop("shoot")
            assert len(sm._looping_channels) == 0

    def test_start_loop_noop_when_no_channel_available(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            mock_pg.mixer.find_channel.return_value = None
            sm = SoundManager()
            sm._start_loop("shoot")
            assert "shoot" not in sm._looping_channels

    def test_start_loop_noop_for_unknown_sound(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            sm = SoundManager()
            sm._start_loop("nonexistent")
            assert len(sm._looping_channels) == 0

    def test_stop_loop_fades_out_channel(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm._start_loop("shoot")
            sm._stop_loop("shoot")
            mock_channel.fadeout.assert_called_once_with(50)
            assert "shoot" not in sm._looping_channels

    def test_stop_loop_noop_when_not_looping(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            sm = SoundManager()
            sm._stop_loop("shoot")  # should not raise

    def test_stop_loops_stops_all_active_loops(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            channel_a = MagicMock()
            channel_b = MagicMock()
            mock_pg.mixer.find_channel.side_effect = [channel_a, channel_b]
            sm = SoundManager()
            sm._start_loop("shoot")
            sm._start_loop("explosion")
            sm.stop_loops()
            channel_a.fadeout.assert_called_once_with(50)
            channel_b.fadeout.assert_called_once_with(50)
            assert len(sm._looping_channels) == 0
