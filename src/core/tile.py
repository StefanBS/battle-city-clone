from enum import Enum, auto
from typing import List, Optional
import pygame
from loguru import logger
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    SUB_TILE_SIZE,
    TILE_ANIMATION_INTERVAL,
    SEGMENT_TOP_LEFT,
    SEGMENT_TOP_RIGHT,
    SEGMENT_BOTTOM_LEFT,
    SEGMENT_BOTTOM_RIGHT,
    SEGMENT_FULL,
    BRICK_SEGMENT_SIZE,
)

# Quadrant pixel offsets within a sub-tile: (dx, dy)
_QUADRANT_OFFSETS = {
    SEGMENT_TOP_LEFT: (0, 0),
    SEGMENT_TOP_RIGHT: (BRICK_SEGMENT_SIZE, 0),
    SEGMENT_BOTTOM_LEFT: (0, BRICK_SEGMENT_SIZE),
    SEGMENT_BOTTOM_RIGHT: (BRICK_SEGMENT_SIZE, BRICK_SEGMENT_SIZE),
}


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
        group_dx: int = 0,
        group_dy: int = 0,
    ) -> None:
        logger.trace(f"Creating Tile ({tile_type.name}) at grid ({x}, {y})")
        self.type = tile_type
        self.x = x
        self.y = y
        self.size = size
        self.rect = pygame.Rect(x * size, y * size, size, size)
        self.is_group_primary = is_group_primary
        # 2x2 group siblings (set by Map._place_tile_group)
        self.group_tiles: List["Tile"] = []
        # Source rect for this sub-tile's quarter within the full sprite
        self._sub_tile_source_rect: pygame.Rect = pygame.Rect(
            group_dx * size, group_dy * size, size, size
        )
        # False once any sibling takes damage; avoids per-frame group scan
        self._group_intact: bool = True

        # Brick segment tracking: each sub-tile has 4 quadrants (8x8 each)
        self.brick_segments: int = SEGMENT_FULL if tile_type == TileType.BRICK else 0
        # Cached draw data for partial bricks: list of (dest, source_rect)
        self._segment_draw_cache: List = []

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

    def get_segment_rect(self, segment: int) -> pygame.Rect:
        """Return the pixel rect for a single quadrant segment."""
        base_x = self.x * self.size
        base_y = self.y * self.size
        dx, dy = _QUADRANT_OFFSETS[segment]
        return pygame.Rect(
            base_x + dx, base_y + dy, BRICK_SEGMENT_SIZE, BRICK_SEGMENT_SIZE
        )

    def remove_brick_segment(self, segment: int) -> None:
        """Remove segment(s) and update the collision rect.

        If all segments are gone the tile should be set to EMPTY by the caller.
        """
        self.brick_segments &= ~segment
        for t in self.group_tiles:
            t._group_intact = False
        if self.brick_segments == 0 or self.brick_segments == SEGMENT_FULL:
            self._segment_draw_cache = []
            return
        # Recompute bounding rect and draw cache from remaining quadrants
        base_x = self.x * self.size
        base_y = self.y * self.size
        min_x = base_x + self.size
        min_y = base_y + self.size
        max_x = base_x
        max_y = base_y
        draw_cache = []
        for quad, (dx, dy) in _QUADRANT_OFFSETS.items():
            if self.brick_segments & quad:
                sx, sy = base_x + dx, base_y + dy
                min_x = min(min_x, sx)
                min_y = min(min_y, sy)
                max_x = max(max_x, sx + BRICK_SEGMENT_SIZE)
                max_y = max(max_y, sy + BRICK_SEGMENT_SIZE)
                s = BRICK_SEGMENT_SIZE
                src_x = self._sub_tile_source_rect.x + dx
                src_y = self._sub_tile_source_rect.y + dy
                draw_cache.append(
                    ((sx, sy), pygame.Rect(src_x, src_y, s, s))
                )
        self.rect = pygame.Rect(min_x, min_y, max_x - min_x, max_y - min_y)
        self._segment_draw_cache = draw_cache

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

        sprite = texture_manager.get_sprite(sprite_name)

        if self.type == TileType.BRICK:
            if self._segment_draw_cache:
                for dest, source_rect in self._segment_draw_cache:
                    surface.blit(sprite, dest, source_rect)
            elif self._group_intact:
                if not self.is_group_primary:
                    return
                surface.blit(sprite, self.rect.topleft)
            else:
                # Sibling damaged — render only our quarter of the full sprite
                surface.blit(sprite, self.rect.topleft, self._sub_tile_source_rect)
        else:
            if not self.is_group_primary:
                return
            surface.blit(sprite, self.rect.topleft)
