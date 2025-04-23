from typing import List, Optional
import pygame
from loguru import logger
from .tile import Tile, TileType
from src.utils.constants import (
    TILE_SIZE,
    GRID_WIDTH,
    GRID_HEIGHT,
)


class Map:
    """Manages the game map and its tiles."""

    def __init__(self) -> None:
        logger.info(f"Initializing Map ({GRID_WIDTH}x{GRID_HEIGHT}) with tile size {TILE_SIZE}")
        self.width = GRID_WIDTH
        self.height = GRID_HEIGHT
        self.tile_size = TILE_SIZE
        self.tiles: List[List[Tile]] = []

        # Initialize empty map
        self._initialize_map()

        # Create a simple test map
        self._create_test_map()

    def _initialize_map(self) -> None:
        """Initialize the map with empty tiles."""
        logger.debug("Initializing map with empty tiles.")
        self.tiles = [
            [Tile(TileType.EMPTY, x, y, self.tile_size) for x in range(self.width)]
            for y in range(self.height)
        ]

    def _create_test_map(self) -> None:
        """Create a simple test map layout."""
        logger.debug("Creating test map layout.")
        # Add some walls around the border
        for x in range(self.width):
            self.tiles[0][x].type = TileType.STEEL  # Top wall
            self.tiles[self.height - 1][x].type = TileType.STEEL  # Bottom wall

        for y in range(self.height):
            self.tiles[y][0].type = TileType.STEEL  # Left wall
            self.tiles[y][self.width - 1].type = TileType.STEEL  # Right wall

        # Add some steel blocks
        for x in range(5, 8):
            for y in range(5, 8):
                self.tiles[y][x].type = TileType.WATER

        # Add the base
        self.tiles[self.height - 2][self.width // 2].type = TileType.BASE

    def draw(self, surface: pygame.Surface) -> None:
        """Draw all tiles on the given surface."""
        for row in self.tiles:
            for tile in row:
                tile.draw(surface)

    def get_tile_at(self, x: int, y: int) -> Optional[Tile]:
        """Get the tile at the specified grid coordinates."""
        if 0 <= y < self.height and 0 <= x < self.width:
            logger.trace(f"Getting tile at ({x}, {y})")
            return self.tiles[y][x]
        else:
            logger.warning(f"Attempted to get tile outside map bounds at ({x}, {y})")
            return None

    def get_tiles_by_type(self, types: List[TileType]) -> List[Tile]:
        """Get a list of tiles matching the specified types."""
        matching_tiles = []
        for row in self.tiles:
            for tile in row:
                if tile.type in types:
                    matching_tiles.append(tile)
        return matching_tiles

    def get_base(self) -> Optional[Tile]:
        """Find and return the player base tile, if it exists."""
        for row in self.tiles:
            for tile in row:
                if tile.type == TileType.BASE:
                    return tile
        return None

    def get_collidable_tiles(self) -> List[pygame.Rect]:
        """
        Get a list of rectangles for all collidable tiles.

        Returns:
            A list of pygame.Rect objects representing collidable tiles
        """
        collidable_rects = []
        for row in self.tiles:
            for tile in row:
                if tile.type in [
                    TileType.BRICK,
                    TileType.STEEL,
                    TileType.BASE,
                    TileType.WATER,
                ]:
                    collidable_rects.append(tile.rect)
        return collidable_rects
