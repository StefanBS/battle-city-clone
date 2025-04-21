from typing import List
import pygame
from .tile import Tile, TileType
from utils.constants import (
    TILE_SIZE,
    GRID_WIDTH,
    GRID_HEIGHT,
)


class Map:
    """Manages the game map and its tiles."""

    def __init__(self):
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
        self.tiles = [
            [Tile(TileType.EMPTY, x, y, self.tile_size) for x in range(self.width)]
            for y in range(self.height)
        ]

    def _create_test_map(self) -> None:
        """Create a simple test map layout."""
        # Add some walls around the border
        for x in range(self.width):
            self.tiles[0][x].type = TileType.BRICK  # Top wall
            self.tiles[self.height - 1][x].type = TileType.BRICK  # Bottom wall

        for y in range(self.height):
            self.tiles[y][0].type = TileType.BRICK  # Left wall
            self.tiles[y][self.width - 1].type = TileType.BRICK  # Right wall

        # Add some steel blocks
        for x in range(5, 8):
            for y in range(5, 8):
                self.tiles[y][x].type = TileType.STEEL

        # Add the base
        self.tiles[self.height - 2][self.width // 2].type = TileType.BASE

    def draw(self, surface) -> None:
        """Draw all tiles on the given surface."""
        for row in self.tiles:
            for tile in row:
                tile.draw(surface)

    def get_tile_at(self, x: int, y: int) -> Tile:
        """Get the tile at the specified coordinates."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
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
                if tile.type in [TileType.BRICK, TileType.STEEL, TileType.BASE]:
                    collidable_rects.append(tile.rect)
        return collidable_rects
