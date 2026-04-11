"""Manages sound effect loading and playback."""

import pygame
from loguru import logger

from src.utils.constants import AUDIO_MIXER_CHANNELS, SOUND_FADEOUT_MS
from src.utils.paths import resource_path


class SoundManager:
    """Loads and plays sound effects with graceful degradation."""

    _SOUND_FILES = {
        "shoot": "assets/sounds/shoot.wav",
        "brick_hit": "assets/sounds/brick_hit.wav",
        "explosion": "assets/sounds/explosion.wav",
        "powerup": "assets/sounds/powerup.wav",
        "game_over": "assets/sounds/game_over.wav",
        "engine": "assets/sounds/engine.wav",
        "bullet_hit_bullet": "assets/sounds/bullet_hit_bullet.wav",
        "stage_start": "assets/sounds/stage_start.wav",
        "victory": "assets/sounds/victory.wav",
        "menu_select": "assets/sounds/menu_select.wav",
        "ice_slide": "assets/sounds/ice_slide.wav",
        "powerup_spawn": "assets/sounds/powerup_spawn.wav",
    }

    def __init__(self, master_volume: float = 1.0) -> None:
        self._enabled: bool = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._looping_channels: dict[str, pygame.mixer.Channel] = {}
        self._master_volume: float = 1.0

        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(AUDIO_MIXER_CHANNELS)
        except pygame.error:
            logger.warning("Audio mixer failed to initialize; sounds disabled.")
            return

        for name, rel_path in self._SOUND_FILES.items():
            try:
                path = resource_path(rel_path)
                self._sounds[name] = pygame.mixer.Sound(path)
            except (pygame.error, FileNotFoundError):
                logger.warning(f"Could not load sound '{rel_path}'; skipping.")

        self._enabled = True
        n_loaded = len(self._sounds)
        n_total = len(self._SOUND_FILES)
        logger.info(f"SoundManager loaded {n_loaded}/{n_total} sounds.")

        self.set_master_volume(master_volume)

    def set_master_volume(self, volume: float) -> None:
        """Set master volume for all sounds, clamped to 0.0-1.0."""
        self._master_volume = max(0.0, min(1.0, volume))
        for sound in self._sounds.values():
            sound.set_volume(self._master_volume)
        for channel in self._looping_channels.values():
            channel.set_volume(self._master_volume)

    def _play(self, name: str) -> None:
        """Play a named sound if enabled and loaded."""
        if not self._enabled:
            return
        sound = self._sounds.get(name)
        if sound is not None:
            sound.play()

    def play_shoot(self) -> None:
        self._play("shoot")

    def play_brick_hit(self) -> None:
        self._play("brick_hit")

    def play_explosion(self) -> None:
        self._play("explosion")

    def play_powerup(self) -> None:
        self._play("powerup")

    def play_game_over(self) -> None:
        self._play("game_over")

    def play_bullet_hit_bullet(self) -> None:
        self._play("bullet_hit_bullet")

    def play_stage_start(self) -> None:
        self._play("stage_start")

    def play_victory(self) -> None:
        self._play("victory")

    def play_menu_select(self) -> None:
        self._play("menu_select")

    def play_ice_slide(self) -> None:
        self._play("ice_slide")

    def update_engine(self, any_moving: bool) -> None:
        """Start or stop engine loop based on whether any tank is moving."""
        if any_moving:
            self._start_loop("engine")
        else:
            self._stop_loop("engine")

    def update_powerup_blink(self, any_active: bool) -> None:
        """Start or stop powerup blink loop based on active powerups."""
        if any_active:
            self._start_loop("powerup_spawn")
        else:
            self._stop_loop("powerup_spawn")

    def _start_loop(self, name: str) -> None:
        """Start looping a sound. No-op if already looping or not loaded."""
        if not self._enabled or name in self._looping_channels:
            return
        sound = self._sounds.get(name)
        if sound is None:
            return
        channel = pygame.mixer.find_channel()
        if channel is not None:
            channel.play(sound, loops=-1)
            channel.set_volume(self._master_volume)
            self._looping_channels[name] = channel

    def _stop_loop(self, name: str) -> None:
        """Stop a looping sound with short fadeout to avoid audio pops."""
        channel = self._looping_channels.pop(name, None)
        if channel is not None:
            channel.fadeout(SOUND_FADEOUT_MS)

    def stop_loops(self) -> None:
        """Stop all looping sounds. Does not affect one-shot sounds."""
        for channel in self._looping_channels.values():
            channel.fadeout(SOUND_FADEOUT_MS)
        self._looping_channels.clear()
