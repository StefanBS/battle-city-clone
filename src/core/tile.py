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
    BUSH = auto()  # Tile that can be driven over but hides tanks
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
    TMX sprite that determines its visual appearance. Bricks are
    destroyed as whole tiles when hit by bullets.
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
    ) -> None:
        logger.trace(f"Creating Tile ({tile_type.name}) at grid ({x}, {y})")
        self.type = tile_type
        self.x = x
        self.y = y
        self.size = size
        self.rect = pygame.Rect(x * size, y * size, size, size)

        # TMX sprite: the actual tile image from the map editor (if available)
        self.tmx_sprite: Optional[pygame.Surface] = tmx_sprite

        # Animation attributes
        self.is_animated: bool = False
        self.animation_frames: List[str] = []
        self.current_frame_index: int = 0
        self.animation_timer: float = 0.0
        self.animation_interval: float = TILE_ANIMATION_INTERVAL

        if self.type == TileType.WATER:
            self.is_animated = True
            self.animation_frames = ["water_1", "water_2"]

    def update(self, dt: float) -> bool:
        """Update tile animation state."""
        if not self.is_animated:
            return False

        self.animation_timer += dt
        if self.animation_timer >= self.animation_interval:
            self.animation_timer -= self.animation_interval
            self.current_frame_index = (self.current_frame_index + 1) % len(
                self.animation_frames
            )
            return True
        return False

    def draw(self, surface: pygame.Surface, texture_manager: TextureManager) -> None:
        """Draw the tile on the given surface."""
        if self.type == TileType.EMPTY:
            return

        # Animated tiles (water) use frame-based sprites
        if self.is_animated and self.animation_frames:
            sprite_name = self.animation_frames[self.current_frame_index]
            sprite = texture_manager.get_sub_sprite(sprite_name)
            surface.blit(sprite, self.rect.topleft)
            return

        # Use TMX sprite if available (exact tile image from map editor)
        if self.tmx_sprite is not None:
            surface.blit(self.tmx_sprite, self.rect.topleft)
            return

        # Fallback: use type-based sprite lookup
        sprite_name = self.SPRITE_NAME_MAP.get(self.type)
        if sprite_name:
            sprite = texture_manager.get_sub_sprite(sprite_name)
            surface.blit(sprite, self.rect.topleft)
