import pygame
from typing import Dict, List, Tuple
from loguru import logger
from src.core.effect import Effect
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    EffectType,
    TILE_SIZE,
    SMALL_EXPLOSION_FRAME_DURATION,
    LARGE_EXPLOSION_FRAME_DURATION,
)

# Size of scaled-up explosion frames for large explosions
_LARGE_EXPLOSION_SIZE = TILE_SIZE * 2


class EffectManager:
    """Manages transient visual effects (explosions, etc.)."""

    def __init__(self, texture_manager: TextureManager) -> None:
        """Initialize the EffectManager.

        Args:
            texture_manager: TextureManager for loading sprites.
        """
        self.effects: List[Effect] = []
        self._effect_data: Dict[
            EffectType, Tuple[List[pygame.Surface], float]
        ] = {}
        self._build_frame_cache(texture_manager)

    def _build_frame_cache(self, texture_manager: TextureManager) -> None:
        """Pre-load and cache sprite frames for each effect type.

        Small explosion uses 3 frames at 32x32.
        Large explosion uses the same 3 frames at 32x32 followed by
        explosion_2 and explosion_3 scaled up to 64x64.
        """
        frame_1 = texture_manager.get_sprite("explosion_1")
        frame_2 = texture_manager.get_sprite("explosion_2")
        frame_3 = texture_manager.get_sprite("explosion_3")

        small_frames = [frame_1, frame_2, frame_3]

        size = (_LARGE_EXPLOSION_SIZE, _LARGE_EXPLOSION_SIZE)
        large_frames = small_frames + [
            pygame.transform.scale(frame_2, size),
            pygame.transform.scale(frame_3, size),
        ]

        self._effect_data[EffectType.SMALL_EXPLOSION] = (
            small_frames,
            SMALL_EXPLOSION_FRAME_DURATION,
        )
        self._effect_data[EffectType.LARGE_EXPLOSION] = (
            large_frames,
            LARGE_EXPLOSION_FRAME_DURATION,
        )

    def spawn(self, effect_type: EffectType, x: float, y: float) -> None:
        """Spawn a new effect at the given center position.

        Args:
            effect_type: Type of effect to spawn.
            x: Center x position.
            y: Center y position.
        """
        frames, duration = self._effect_data[effect_type]
        effect = Effect(x, y, frames, duration)
        self.effects.append(effect)
        logger.trace(f"Spawned {effect_type.name} at ({x:.1f}, {y:.1f})")

    def update(self, dt: float) -> None:
        """Update all effects and remove inactive ones.

        Args:
            dt: Time elapsed since last update in seconds.
        """
        any_expired = False
        for effect in self.effects:
            effect.update(dt)
            if not effect.active:
                any_expired = True
        if any_expired:
            self.effects = [e for e in self.effects if e.active]

    def draw(self, surface: pygame.Surface) -> None:
        """Draw all active effects.

        Args:
            surface: Surface to draw on.
        """
        for effect in self.effects:
            effect.draw(surface)
