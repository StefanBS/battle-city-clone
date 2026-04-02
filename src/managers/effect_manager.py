import pygame
from typing import Dict, List
from loguru import logger
from src.core.effect import Effect
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    EffectType,
    SMALL_EXPLOSION_FRAME_DURATION,
    LARGE_EXPLOSION_FRAME_DURATION,
)


class EffectManager:
    """Manages transient visual effects (explosions, etc.)."""

    def __init__(self, texture_manager: TextureManager) -> None:
        """Initialize the EffectManager.

        Args:
            texture_manager: TextureManager for loading sprites.
        """
        self.effects: List[Effect] = []
        self._frame_cache: Dict[EffectType, List[pygame.Surface]] = {}
        self._duration_map: Dict[EffectType, float] = {
            EffectType.SMALL_EXPLOSION: SMALL_EXPLOSION_FRAME_DURATION,
            EffectType.LARGE_EXPLOSION: LARGE_EXPLOSION_FRAME_DURATION,
        }
        self._build_frame_cache(texture_manager)

    def _build_frame_cache(self, texture_manager: TextureManager) -> None:
        """Pre-load and cache sprite frames for each effect type.

        Small explosion uses 3 frames at 32x32.
        Large explosion uses the same 3 frames at 32x32 followed by
        explosion_3 and explosion_4 scaled up to 64x64.
        """
        frame_1 = texture_manager.get_sprite("explosion_1")
        frame_2 = texture_manager.get_sprite("explosion_2")
        frame_3 = texture_manager.get_sprite("explosion_3")
        frame_4 = texture_manager.get_sprite("explosion_4")

        small_frames = [frame_1, frame_2, frame_3]

        # Scale frames 3 and 4 up to 64x64 for the large explosion
        large_frame_1 = pygame.transform.scale(frame_3, (64, 64))
        large_frame_2 = pygame.transform.scale(frame_4, (64, 64))
        large_frames = [frame_1, frame_2, frame_3, large_frame_1, large_frame_2]

        self._frame_cache[EffectType.SMALL_EXPLOSION] = small_frames
        self._frame_cache[EffectType.LARGE_EXPLOSION] = large_frames

    def spawn(self, effect_type: EffectType, x: float, y: float) -> None:
        """Spawn a new effect at the given center position.

        Args:
            effect_type: Type of effect to spawn.
            x: Center x position.
            y: Center y position.
        """
        frames = self._frame_cache[effect_type]
        duration = self._duration_map[effect_type]
        effect = Effect(x, y, frames, duration)
        self.effects.append(effect)
        logger.trace(f"Spawned {effect_type.name} at ({x:.1f}, {y:.1f})")

    def update(self, dt: float) -> None:
        """Update all effects and remove inactive ones.

        Args:
            dt: Time elapsed since last update in seconds.
        """
        for effect in self.effects:
            effect.update(dt)
        self.effects = [e for e in self.effects if e.active]

    def draw(self, surface: pygame.Surface) -> None:
        """Draw all active effects.

        Args:
            surface: Surface to draw on.
        """
        for effect in self.effects:
            effect.draw(surface)
