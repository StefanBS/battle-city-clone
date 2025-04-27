from typing import List, Optional
import pygame
from loguru import logger
from .tile import Tile, TileType
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    TILE_SIZE,
    GRID_WIDTH,
    GRID_HEIGHT,
)


class Map:
    """Manages the game map and its tiles."""

    def __init__(self, texture_manager: TextureManager) -> None:
        logger.info(
            f"Initializing Map ({GRID_WIDTH}x{GRID_HEIGHT}) with tile size {TILE_SIZE}"
        )
        self.width = GRID_WIDTH
        self.height = GRID_HEIGHT
        self.tile_size = TILE_SIZE
        self.tiles: List[List[Optional[Tile]]] = []
        self.texture_manager = texture_manager

        # Create a simple test map
        self._create_test_map()

    def _initialize_map(self) -> None:
        # Initialize grid structure with None
        logger.debug("Initializing map grid structure.")
        self.tiles = [[None for _ in range(self.width)] for _ in range(self.height)]

    def _create_test_map(self) -> None:
        """Create a simple test map layout by populating the grid with Tiles."""
        logger.debug("Creating test map layout and Tile objects.")

        # Initialize grid structure first if not already done
        if not self.tiles or not self.tiles[0]:
             self.tiles = [[None for _ in range(self.width)] for _ in range(self.height)]

        for y in range(self.height):
            for x in range(self.width):
                tile_type = TileType.EMPTY # Default to EMPTY

                # Determine type based on position (example logic from previous version)
                is_border_top = y == 0
                is_border_bottom = y == self.height - 1
                is_border_left = x == 0
                is_border_right = x == self.width - 1

                if is_border_top or is_border_bottom or is_border_left or is_border_right:
                    tile_type = TileType.STEEL
                elif 5 <= x < 8 and 5 <= y < 8:
                    tile_type = TileType.WATER
                elif y == self.height - 2 and x == self.width // 2:
                    tile_type = TileType.BASE

                # Create the Tile object with the determined type
                self.tiles[y][x] = Tile(tile_type, x, y, self.tile_size)

    def update(self, dt: float) -> None:
        """Update all tiles in the map (e.g., for animations)."""
        for row in self.tiles:
            for tile in row:
                if tile:
                    tile.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw all tiles on the given surface."""
        for row in self.tiles:
            for tile in row:
                if tile:
                    tile.draw(surface, self.texture_manager)

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
                if tile and tile.type in types:
                    matching_tiles.append(tile)
        return matching_tiles

    def get_base(self) -> Optional[Tile]:
        """Find and return the player base tile, if it exists."""
        for row in self.tiles:
            for tile in row:
                if tile and tile.type == TileType.BASE:
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
                if tile and tile.type in [
                    TileType.BRICK,
                    TileType.STEEL,
                    TileType.BASE,
                    TileType.WATER,
                ]:
                    collidable_rects.append(tile.rect)
        return collidable_rects
