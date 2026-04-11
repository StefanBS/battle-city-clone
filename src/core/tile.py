from enum import Enum, auto
from typing import List, Optional, Tuple
import pygame
from loguru import logger
from src.managers.texture_manager import TextureManager
from src.utils.constants import SUB_TILE_SIZE


class TileType(Enum):
    """Types of tiles in the game."""

    EMPTY = auto()
    BRICK = auto()
    STEEL = auto()
    WATER = auto()
    BUSH = auto()
    ICE = auto()
    BASE = auto()
    BASE_DESTROYED = auto()


class BrickVariant(str, Enum):
    """Brick tile variants matching Tiled BrickVariant property type."""

    FULL = "full"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"
    TOP = "top"

    def __str__(self) -> str:
        return self.value


class Tile:
    """Represents a single 8x8 tile in the game map, rendered at SUB_TILE_SIZE.

    Each tile has a type that determines its collision behavior and a
    TMX sprite that determines its visual appearance.
    """

    is_destructible: bool = False
    is_overlay: bool = False
    is_slidable: bool = False
    blocks_tanks: bool = False
    blocks_bullets: bool = False

    def __init__(
        self,
        tile_type: TileType,
        x: int,
        y: int,
        size: int = SUB_TILE_SIZE,
        tmx_sprite: Optional[pygame.Surface] = None,
        brick_variant: "BrickVariant" = BrickVariant.FULL,
        blocks_tanks: bool = False,
        blocks_bullets: bool = False,
        is_destructible: bool = False,
        is_overlay: bool = False,
        is_slidable: bool = False,
    ) -> None:
        logger.trace(f"Creating Tile ({tile_type.name}) at grid ({x}, {y})")
        self.type = tile_type
        self.x = x
        self.y = y
        self.size = size
        self.rect = pygame.Rect(x * size, y * size, size, size)
        self.blocks_tanks = blocks_tanks
        self.blocks_bullets = blocks_bullets
        self.is_destructible = is_destructible
        self.is_overlay = is_overlay
        self.is_slidable = is_slidable

        # TMX sprite: the actual tile image from the map editor
        self.tmx_sprite: Optional[pygame.Surface] = tmx_sprite

        self.brick_variant: BrickVariant = brick_variant

        # Animation attributes
        self.is_animated: bool = False
        self.animation_sprites: List[pygame.Surface] = []
        self._frame_durations: List[float] = []
        self.current_frame_index: int = 0
        self.animation_timer: float = 0.0

    def set_animation_frames(self, frames: List[Tuple[pygame.Surface, float]]) -> None:
        """Set animation frames with per-frame durations.

        Args:
            frames: List of (surface, duration_seconds) tuples.
        """
        self.animation_sprites = [surface for surface, _ in frames]
        self._frame_durations = [duration for _, duration in frames]
        self.is_animated = True
        self.current_frame_index = 0
        self.animation_timer = 0.0

    def reset_rect(self) -> None:
        """Reset the collision rect to full tile size."""
        s = self.size
        self.rect = pygame.Rect(self.x * s, self.y * s, s, s)

    def update(self, dt: float) -> bool:
        """Update tile animation state."""
        if not self.is_animated:
            return False

        frame_count = len(self.animation_sprites)
        if frame_count == 0:
            return False

        self.animation_timer += dt
        current_duration = self._frame_durations[self.current_frame_index]
        if self.animation_timer >= current_duration:
            self.animation_timer -= current_duration
            self.current_frame_index = (self.current_frame_index + 1) % frame_count
            return True
        return False

    def draw(self, surface: pygame.Surface, texture_manager: TextureManager) -> None:
        """Draw the tile on the given surface."""
        if self.type == TileType.EMPTY:
            return

        # Draw position: always at grid origin (rect may be offset for half-bricks)
        draw_pos = (self.x * self.size, self.y * self.size)

        # Animated tiles: use animation sprites
        if self.is_animated and self.animation_sprites:
            surface.blit(self.animation_sprites[self.current_frame_index], draw_pos)
            return

        # Non-animated tile with TMX sprite (most common)
        if self.tmx_sprite is not None:
            surface.blit(self.tmx_sprite, draw_pos)
