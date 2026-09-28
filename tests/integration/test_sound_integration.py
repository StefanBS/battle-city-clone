"""Integration tests for the sounds a Battle asks for, with real game objects."""

from src.utils.constants import FPS
from tests.integration.conftest import (
    SoundRecorder,
    first_player,
    make_battle,
    tick,
)


class TestEngineSoundWiring:
    """Engine sound updates are called during the game loop."""

    def test_engine_sound_updates_during_gameplay(self):
        """Each frame tells the engine sound whether any tank is moving."""
        sound = SoundRecorder()
        battle = make_battle(sound=sound)
        tick(battle, 5)
        assert sound.engine_running is False

    def test_player_movement_sets_is_moving(self, battle):
        """Verify player tank reports is_moving after move()."""
        dt = 1.0 / FPS
        first_player(battle).move(1, 0, dt)
        assert first_player(battle).is_moving is True

    def test_player_is_moving_resets_after_update(self, battle):
        """Verify is_moving resets to False after tank.update()."""
        dt = 1.0 / FPS
        first_player(battle).move(1, 0, dt)
        assert first_player(battle).is_moving is True
        first_player(battle).update(dt)
        assert first_player(battle).is_moving is False


class TestPowerupBlinkWiring:
    """Powerup blink sound updates during gameplay."""

    def test_power_up_on_the_battlefield_blinks(self):
        """A frame with a Power-Up on the battlefield turns its blink sound on."""
        sound = SoundRecorder()
        battle = make_battle(sound=sound)
        battle.drop_power_up()
        assert len(battle.scene().power_ups) > 0
        tick(battle)
        assert sound.power_up_blinking is True
