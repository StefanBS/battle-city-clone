from enum import Enum, auto
import pygame
from loguru import logger
from src.managers.texture_manager import TextureManager
from src.utils.constants import TILE_SIZE


class TileType(Enum):
    """Types of tiles in the game."""

    EMPTY = auto()
    BRICK = auto()
    STEEL = auto()
    WATER = auto()
    BUSH = auto()  # Tile that can be driven over but hides tanks
    ICE = auto()
    BASE = auto()
    BASE_DESTROYED = auto()  # Added destroyed state


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

        # Define colors for different tile types
        self.colors = {
            TileType.EMPTY: (0, 0, 0),  # Black
            TileType.BRICK: (139, 69, 19),  # Brown
            TileType.STEEL: (128, 128, 128),  # Gray
            TileType.WATER: (0, 0, 255),  # Blue
            TileType.BUSH: (0, 100, 0),  # Dark Green
            TileType.ICE: (200, 200, 255),  # Light Blue
            TileType.BASE: (255, 215, 0),  # Gold
            TileType.BASE_DESTROYED: (139, 69, 19),  # Brown
        }

    def draw(self, surface: pygame.Surface, texture_manager: TextureManager) -> None:
        """Draw the tile on the given surface."""
        if self.type == TileType.WATER:
            try:
                water_sprite = texture_manager.get_sprite("water")
                surface.blit(water_sprite, self.rect.topleft)
            except KeyError:
                logger.error("Water sprite not found in TextureManager. Drawing fallback color.")
                # Fallback to drawing a color if sprite is missing
                pygame.draw.rect(surface, (0, 0, 255), self.rect) # Blue fallback
        else:
            color = self.colors.get(self.type, (0, 0, 0))
            pygame.draw.rect(surface, color, self.rect)
