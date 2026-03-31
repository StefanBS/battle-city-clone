from enum import Enum, auto
from typing import List, Optional
import pygame
from loguru import logger
from src.managers.texture_manager import TextureManager
from src.utils.constants import SUB_TILE_SIZE, TILE_ANIMATION_INTERVAL


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

# Tile types that render at full TILE_SIZE from the top-left sub-tile only
_FULL_SIZE_TILE_TYPES = frozenset({TileType.BASE, TileType.BASE_DESTROYED})


class Tile:
    """Represents a single sub-tile (16x16) in the game map.

    Most tiles are part of a 2x2 group that corresponds to one visual tile.
    Bricks are independently destructible. Base tiles render as a single
    32x32 sprite from the top-left sub-tile of their group.
    """

    SPRITE_NAME_MAP = {
        TileType.EMPTY: None,
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
        is_group_primary: bool = False,
    ) -> None:
        logger.trace(f"Creating Tile ({tile_type.name}) at grid ({x}, {y})")
        self.type = tile_type
        self.x = x
        self.y = y
        self.size = size
        self.rect = pygame.Rect(x * size, y * size, size, size)
        self.is_group_primary = is_group_primary

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
            logger.trace(
                f"Tile ({self.x},{self.y}) animation frame updated to index "
                f"{self.current_frame_index}"
            )
            return True
        return False

    def draw(self, surface: pygame.Surface, texture_manager: TextureManager) -> None:
        """Draw the tile on the given surface using textures."""
        sprite_name: Optional[str] = None

        if self.is_animated:
            if self.animation_frames:
                sprite_name = self.animation_frames[self.current_frame_index]
        else:
            sprite_name = self.SPRITE_NAME_MAP.get(self.type)

        if not sprite_name:
            return

        # Base/base_destroyed: only the group primary renders, at full TILE_SIZE
        if self.type in _FULL_SIZE_TILE_TYPES:
            if not self.is_group_primary:
                return
            sprite = texture_manager.get_sprite(sprite_name)
            surface.blit(sprite, self.rect.topleft)
        else:
            # All other tiles render at sub-tile size
            sprite = texture_manager.get_sub_sprite(sprite_name)
            surface.blit(sprite, self.rect.topleft)
