from enum import Enum, auto
from typing import List, Optional
import pygame
from loguru import logger
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    SUB_TILE_SIZE,
    TILE_ANIMATION_INTERVAL,
)


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


# Tile types that block tank movement
IMPASSABLE_TILE_TYPES = frozenset(
    {TileType.BRICK, TileType.STEEL, TileType.WATER, TileType.BASE}
)


class Tile:
    """Represents a single 8x8 tile in the game map, rendered at SUB_TILE_SIZE.

    Each tile has a type that determines its collision behavior and a
    TMX sprite that determines its visual appearance.
    """

    # Fallback sprite names when no TMX sprite is available
    SPRITE_NAME_MAP = {
        TileType.BRICK: "brick",
        TileType.STEEL: "steel",
        TileType.BUSH: "bush",
        TileType.ICE: "ice",
        TileType.BASE: "base",
        TileType.BASE_DESTROYED: "base_destroyed",
    }

    def __init__(
        self,
        tile_type: TileType,
        x: int,
        y: int,
        size: int = SUB_TILE_SIZE,
        tmx_sprite: Optional[pygame.Surface] = None,
        brick_variant: str = "full",
    ) -> None:
        logger.trace(f"Creating Tile ({tile_type.name}) at grid ({x}, {y})")
        self.type = tile_type
        self.x = x
        self.y = y
        self.size = size
        self.rect = pygame.Rect(x * size, y * size, size, size)

        # TMX sprite: the actual tile image from the map editor
        self.tmx_sprite: Optional[pygame.Surface] = tmx_sprite

        # Brick variant: "full", "left", "right", "top", "bottom"
        self.brick_variant: str = brick_variant

        # Animation attributes
        self.is_animated: bool = False
        self.animation_sprites: List[pygame.Surface] = []
        self.animation_frames: List[str] = []  # fallback frame names
        self.current_frame_index: int = 0
        self.animation_timer: float = 0.0
        self.animation_interval: float = TILE_ANIMATION_INTERVAL

        if self.type == TileType.WATER:
            self.is_animated = True
            self.animation_frames = ["water_1", "water_2"]

    def reset_rect(self) -> None:
        """Reset the collision rect to full tile size."""
        s = self.size
        self.rect = pygame.Rect(self.x * s, self.y * s, s, s)

    def update(self, dt: float) -> bool:
        """Update tile animation state."""
        if not self.is_animated:
            return False

        frame_count = len(self.animation_sprites) or len(self.animation_frames)
        if frame_count == 0:
            return False

        self.animation_timer += dt
        if self.animation_timer >= self.animation_interval:
            self.animation_timer -= self.animation_interval
            self.current_frame_index = (self.current_frame_index + 1) % frame_count
            return True
        return False

    def draw(self, surface: pygame.Surface, texture_manager: TextureManager) -> None:
        """Draw the tile on the given surface."""
        if self.type == TileType.EMPTY:
            return

        # Draw position: always at grid origin (rect may be offset for half-bricks)
        draw_pos = (self.x * self.size, self.y * self.size)

        # Fast path: non-animated tile with TMX sprite (most common)
        if self.tmx_sprite is not None and not self.is_animated:
            surface.blit(self.tmx_sprite, draw_pos)
            return

        # Animated tiles: use TMX animation sprites if available
        if self.is_animated and self.animation_sprites:
            surface.blit(self.animation_sprites[self.current_frame_index], draw_pos)
            return

        if self.is_animated and self.animation_frames:
            sprite_name = self.animation_frames[self.current_frame_index]
            surface.blit(texture_manager.get_sub_sprite(sprite_name), draw_pos)
            return

        # Fallback: use type-based sprite lookup
        sprite_name = self.SPRITE_NAME_MAP.get(self.type)
        if sprite_name:
            surface.blit(texture_manager.get_sub_sprite(sprite_name), draw_pos)
