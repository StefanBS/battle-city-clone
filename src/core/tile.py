from enum import Enum, auto
from typing import List, Optional
import pygame
from loguru import logger
from src.managers.texture_manager import TextureManager
from src.utils.constants import TILE_SIZE, TILE_ANIMATION_INTERVAL


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


class Tile:
    """Represents a single tile in the game map."""

    def __init__(
        self, tile_type: TileType, x: int, y: int, size: int = TILE_SIZE
    ) -> None:
        logger.trace(f"Creating Tile ({tile_type.name}) at grid ({x}, {y})")
        self.type = tile_type
        self.x = x
        self.y = y
        self.size = size
        self.rect = pygame.Rect(x * size, y * size, size, size)

        # Animation attributes
        self.is_animated: bool = False
        self.animation_frames: List[str] = []
        self.current_frame_index: int = 0
        self.animation_timer: float = 0.0
        self.animation_interval: float = TILE_ANIMATION_INTERVAL

        if self.type == TileType.WATER:
            self.is_animated = True
            self.animation_frames = ["water_1", "water_2"]

    def update(self, dt: float) -> None:
        """Update tile animation state."""
        if not self.is_animated:
            return

        self.animation_timer += dt
        if self.animation_timer >= self.animation_interval:
            self.animation_timer -= self.animation_interval
            self.current_frame_index = (self.current_frame_index + 1) % len(self.animation_frames)
            logger.trace(f"Tile ({self.x},{self.y}) animation frame updated to index {self.current_frame_index}")

    def draw(self, surface: pygame.Surface, texture_manager: TextureManager) -> None:
        """Draw the tile on the given surface using textures if available."""
        sprite_name: Optional[str] = None

        if self.is_animated:
            if self.animation_frames:
                sprite_name = self.animation_frames[self.current_frame_index]
        else:
            # Static sprite mapping (excluding animated types)
            sprite_name_map = {
                TileType.EMPTY: None,
                TileType.BRICK: "brick",
                TileType.STEEL: "steel",
                TileType.BUSH: "bush",
                TileType.ICE: "ice",
                TileType.BASE: "base",
                TileType.BASE_DESTROYED: "base_destroyed",
            }
            sprite_name = sprite_name_map.get(self.type)

        if sprite_name:
            # No fallback color drawing - if sprite is missing, let KeyError propagate
            sprite = texture_manager.get_sprite(sprite_name)
            surface.blit(sprite, self.rect.topleft)
