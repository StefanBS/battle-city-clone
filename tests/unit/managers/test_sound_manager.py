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
