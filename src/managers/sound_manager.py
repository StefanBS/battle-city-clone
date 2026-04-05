"""Manages sound effect loading and playback."""

import pygame
from loguru import logger

from src.utils.paths import resource_path


class SoundManager:
    """Loads and plays sound effects with graceful degradation."""

    _SOUND_FILES = {
        "shoot": "assets/sounds/shoot.wav",
        "brick_hit": "assets/sounds/brick_hit.wav",
        "explosion": "assets/sounds/explosion.wav",
        "powerup": "assets/sounds/powerup.wav",
        "game_over": "assets/sounds/game_over.wav",
    }

    def __init__(self) -> None:
        self._enabled: bool = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}

        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
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
