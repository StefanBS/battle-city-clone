from enum import Enum, auto
import pygame


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

    def __init__(self, tile_type: TileType, x: int, y: int, size: int = 32):
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

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the tile on the given surface."""
        color = self.colors.get(self.type, (0, 0, 0))
        pygame.draw.rect(surface, color, self.rect)

        # Add a border to make tiles more visible
        pygame.draw.rect(surface, (50, 50, 50), self.rect, 1)
