import pytest
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


class TestNewPlayMethods:
    @pytest.mark.parametrize(
        "method",
        [
            "play_bullet_hit_bullet",
            "play_stage_start",
            "play_victory",
            "play_menu_select",
            "play_ice_slide",
        ],
    )
    def test_oneshot_methods_call_sound_play(self, method):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_sound = MagicMock()
            mock_pg.mixer.Sound.return_value = mock_sound
            sm = SoundManager()
            getattr(sm, method)()
            mock_sound.play.assert_called()

    @pytest.mark.parametrize(
        "method",
        [
            "play_bullet_hit_bullet",
            "play_stage_start",
            "play_victory",
            "play_menu_select",
            "play_ice_slide",
        ],
    )
    def test_oneshot_methods_noop_when_disabled(self, method):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.error = type("error", (Exception,), {})
            mock_pg.mixer.init.side_effect = mock_pg.error("no audio")
            sm = SoundManager()
            getattr(sm, method)()  # should not raise


class TestUpdateEngine:
    def test_update_engine_true_starts_loop(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm.update_engine(True)
            assert "engine" in sm._looping_channels

    def test_update_engine_false_stops_loop(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm.update_engine(True)
            sm.update_engine(False)
            assert "engine" not in sm._looping_channels
            mock_channel.fadeout.assert_called_once_with(50)

    def test_update_engine_repeated_true_is_noop(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm.update_engine(True)
            mock_channel.play.reset_mock()
            sm.update_engine(True)
            mock_channel.play.assert_not_called()


class TestUpdatePowerupBlink:
    def test_update_powerup_blink_true_starts_loop(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm.update_powerup_blink(True)
            assert "powerup_spawn" in sm._looping_channels

    def test_update_powerup_blink_false_stops_loop(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm.update_powerup_blink(True)
            sm.update_powerup_blink(False)
            assert "powerup_spawn" not in sm._looping_channels


class TestMasterVolume:
    def test_set_master_volume_stores_value(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            sm = SoundManager()
            sm.set_master_volume(0.5)
            assert sm._master_volume == 0.5

    def test_set_master_volume_applies_to_sounds(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_sound = MagicMock()
            mock_pg.mixer.Sound.return_value = mock_sound
            sm = SoundManager()
            sm.set_master_volume(0.3)
            mock_sound.set_volume.assert_called_with(0.3)

    def test_set_master_volume_applies_to_looping_channels(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_sound = MagicMock()
            mock_pg.mixer.Sound.return_value = mock_sound
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager()
            sm._start_loop("engine")
            sm.set_master_volume(0.4)
            mock_channel.set_volume.assert_called_with(0.4)

    def test_init_with_master_volume(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_sound = MagicMock()
            mock_pg.mixer.Sound.return_value = mock_sound
            sm = SoundManager(master_volume=0.6)
            assert sm._master_volume == 0.6
            mock_sound.set_volume.assert_called_with(0.6)

    def test_start_loop_applies_master_volume_to_channel(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_sound = MagicMock()
            mock_pg.mixer.Sound.return_value = mock_sound
            mock_channel = MagicMock()
            mock_pg.mixer.find_channel.return_value = mock_channel
            sm = SoundManager(master_volume=0.7)
            sm._start_loop("engine")
            mock_channel.set_volume.assert_called_with(0.7)

    def test_set_master_volume_clamps_high(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            sm = SoundManager()
            sm.set_master_volume(1.5)
            assert sm._master_volume == 1.0

    def test_set_master_volume_clamps_low(self):
        with patch("src.managers.sound_manager.pygame") as mock_pg:
            mock_pg.mixer.Sound.return_value = MagicMock()
            sm = SoundManager()
            sm.set_master_volume(-0.3)
            assert sm._master_volume == 0.0
