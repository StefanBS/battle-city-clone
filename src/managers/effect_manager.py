import pygame
from typing import Dict, List, Tuple
from loguru import logger
from src.core.effect import Effect
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    ATLAS_BG_COLOR,
    EffectType,
    LARGE_EXPLOSION_SIZE,
    SMALL_EXPLOSION_FRAME_DURATION,
    LARGE_EXPLOSION_FRAME_DURATION,
    SPAWN_FRAME_DURATION,
)


class EffectManager:
    """Manages transient visual effects (explosions, etc.)."""

    def __init__(self, texture_manager: TextureManager) -> None:
        """Initialize the EffectManager.

        Args:
            texture_manager: TextureManager for loading sprites.
        """
        self.effects: List[Effect] = []
        self._effect_data: Dict[EffectType, Tuple[List[pygame.Surface], float]] = {}
        self._build_frame_cache(texture_manager)

    @staticmethod
    def _apply_colorkey(
        surface: pygame.Surface, key_color=ATLAS_BG_COLOR
    ) -> pygame.Surface:
        """Return a copy with key_color pixels made fully transparent.

        The explosion sprites in the atlas have an opaque near-black
        background (0,0,1) instead of true transparency. This converts
        those pixels to alpha=0 so explosions don't overwrite the scene.
        """
        copy = surface.convert()
        copy.set_colorkey(key_color)
        result = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        result.blit(copy, (0, 0))
        return result

    def _build_frame_cache(self, texture_manager: TextureManager) -> None:
        """Pre-load and cache sprite frames for each effect type.

        Small explosion uses 3 frames at 32x32.
        Large explosion uses the same 3 frames at 32x32 followed by
        explosion_2 and explosion_3 scaled up to 64x64.
        """
        frame_1 = self._apply_colorkey(texture_manager.get_sprite("explosion_1"))
        frame_2 = self._apply_colorkey(texture_manager.get_sprite("explosion_2"))
        frame_3 = self._apply_colorkey(texture_manager.get_sprite("explosion_3"))

        small_frames = [frame_1, frame_2, frame_3]

        size = (LARGE_EXPLOSION_SIZE, LARGE_EXPLOSION_SIZE)
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

        # Spawn animation: 4 frames bounced twice (1→2→3→4→3→2→1→2→3→4→3→2)
        f1, f2, f3, f4 = [
            self._apply_colorkey(texture_manager.get_sprite(f"spawn_{i}"))
            for i in range(1, 5)
        ]
        bounce = [f1, f2, f3, f4, f3, f2]
        spawn_cycle = bounce + bounce
        self._effect_data[EffectType.SPAWN] = (
            spawn_cycle,
            SPAWN_FRAME_DURATION,
        )

    def spawn(self, effect_type: EffectType, x: float, y: float) -> Effect:
        """Spawn a new effect at the given center position.

        Args:
            effect_type: Type of effect to spawn.
            x: Center x position.
            y: Center y position.

        Returns:
            The created Effect instance.
        """
        frames, duration = self._effect_data[effect_type]
        effect = Effect(x, y, frames, duration)
        self.effects.append(effect)
        logger.trace(f"Spawned {effect_type.name} at ({x:.1f}, {y:.1f})")
        return effect

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
