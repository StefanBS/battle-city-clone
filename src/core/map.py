from typing import Iterable, List, Optional, Tuple
import pygame
import pytmx
from pytmx.util_pygame import load_pygame
from loguru import logger
from .tile import Tile, TileType, IMPASSABLE_TILE_TYPES
from src.managers.texture_manager import TextureManager
from src.utils.constants import SUB_TILE_SIZE


class Map:
    """Manages the game map and its tiles.

    Internally uses a sub-tile grid (16x16 cells). Each TMX tile is expanded
    to a 2x2 block of sub-tiles. Bricks are independently destructible.
    Base tiles are grouped — destroying any sub-tile destroys the whole group.
    """

    def __init__(self, map_file: str, texture_manager: TextureManager) -> None:
        self.tile_size = SUB_TILE_SIZE
        self.texture_manager = texture_manager
        self.tiles: List[List[Optional[Tile]]] = []
        self.spawn_points: List[Tuple[int, int]] = []
        self.player_spawn: Tuple[int, int] = (0, 0)
        self._animated_tiles: List[Tile] = []
        self._drawable_tiles: List[Tile] = []
        self._tile_cache_dirty: bool = True
        self._cached_tiles_by_type: dict = {}
        self._cached_collidable_rects: List[pygame.Rect] = []
        self._cached_base: Optional[Tile] = None

        self._load_from_tmx(map_file)
        self._build_derived_tile_lists()
        self._rebuild_tile_caches()

        logger.info(
            f"Map loaded from {map_file}: {self.width}x{self.height} sub-tiles, "
            f"{len(self.spawn_points)} spawn points, "
            f"player spawn at {self.player_spawn}"
        )

    def _load_from_tmx(self, map_file: str) -> None:
        """Load map data from a TMX file and expand to sub-tile grid."""
        tiled_map = load_pygame(map_file)

        tmx_width = tiled_map.width
        tmx_height = tiled_map.height

        # Sub-tile grid is 2x the TMX grid
        self.width = tmx_width * 2
        self.height = tmx_height * 2

        # Initialize grid
        self.tiles = [[None for _ in range(self.width)] for _ in range(self.height)]

        # Find first tile layer
        tile_layer = None
        for layer in tiled_map.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                tile_layer = layer
                break

        if tile_layer is not None:
            for x, y, gid in tile_layer.iter_data():
                if gid == 0:
                    tile_type = TileType.EMPTY
                else:
                    props = tiled_map.get_tile_properties_by_gid(gid)
                    if props:
                        tile_type_str = props.get("tile_type")
                        if tile_type_str and tile_type_str.strip():
                            tile_type = TileType[tile_type_str.strip()]
                        else:
                            tile_type = TileType.EMPTY
                    else:
                        tile_type = TileType.EMPTY

                # Expand each TMX tile to 2x2 sub-tiles
                self._place_tile_group(x * 2, y * 2, tile_type)

        # Fill any remaining None tiles with EMPTY
        for y in range(self.height):
            for x in range(self.width):
                if self.tiles[y][x] is None:
                    self.tiles[y][x] = Tile(TileType.EMPTY, x, y, self.tile_size)

        # Read spawn points from object layer (convert to sub-tile coords)
        self._load_spawn_points(tiled_map)

    def _place_tile_group(self, sub_x: int, sub_y: int, tile_type: TileType) -> None:
        """Place a 2x2 group of sub-tiles at the given sub-tile coordinates."""
        group_tiles = []
        for dy in range(2):
            for dx in range(2):
                sx, sy = sub_x + dx, sub_y + dy
                is_primary = dx == 0 and dy == 0
                tile = Tile(
                    tile_type,
                    sx,
                    sy,
                    self.tile_size,
                    is_group_primary=is_primary,
                    group_dx=dx,
                    group_dy=dy,
                )
                self.tiles[sy][sx] = tile
                group_tiles.append(tile)

        for tile in group_tiles:
            tile.group_tiles = group_tiles

    def _load_spawn_points(self, tiled_map: pytmx.TiledMap) -> None:
        """Read spawn points and player spawn from TMX object layers.

        Converts TMX pixel coordinates to sub-tile grid coordinates.
        """
        try:
            spawn_layer = tiled_map.get_layer_by_name("spawn_points")
        except ValueError:
            logger.warning("No 'spawn_points' object layer found in TMX")
            self.player_spawn = (self.width // 2 - 1, self.height - 2)
            return

        player_spawn_found = False
        for obj in spawn_layer:
            # Convert pixel coords to sub-tile coords
            grid_x = int(obj.x // tiled_map.tilewidth) * 2
            grid_y = int(obj.y // tiled_map.tileheight) * 2

            if obj.name == "player_spawn":
                self.player_spawn = (grid_x, grid_y)
                player_spawn_found = True
            else:
                self.spawn_points.append((grid_x, grid_y))

        if not player_spawn_found:
            self.player_spawn = (self.width // 2 - 2, self.height - 4)
            logger.warning(
                "No 'player_spawn' object found, defaulting to bottom-center"
            )

    def _build_derived_tile_lists(self) -> None:
        """Build the lists of animated and drawable (non-empty) tiles."""
        self._animated_tiles = []
        self._drawable_tiles = []
        for row in self.tiles:
            for tile in row:
                if not tile:
                    continue
                if tile.type != TileType.EMPTY:
                    self._drawable_tiles.append(tile)
                if tile.is_animated:
                    self._animated_tiles.append(tile)

    def update(self, dt: float) -> None:
        """Update animated tiles only."""
        for tile in self._animated_tiles:
            tile.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw non-empty tiles on the given surface."""
        for tile in self._drawable_tiles:
            tile.draw(surface, self.texture_manager)

    def get_tile_at(self, x: int, y: int) -> Optional[Tile]:
        """Get the tile at the specified sub-tile grid coordinates."""
        if 0 <= y < self.height and 0 <= x < self.width:
            logger.trace(f"Getting tile at ({x}, {y})")
            return self.tiles[y][x]
        else:
            logger.warning(f"Attempted to get tile outside map bounds at ({x}, {y})")
            return None

    def mark_tile_cache_dirty(self) -> None:
        """Mark tile caches as needing rebuild."""
        self._tile_cache_dirty = True

    def set_tile_type(self, tile: Tile, new_type: TileType) -> None:
        """Change a tile's type and invalidate caches."""
        old_type = tile.type
        tile.type = new_type
        self._tile_cache_dirty = True
        # Keep drawable tiles list in sync
        if old_type == TileType.EMPTY and new_type != TileType.EMPTY:
            self._drawable_tiles.append(tile)
        elif old_type != TileType.EMPTY and new_type == TileType.EMPTY:
            if tile in self._drawable_tiles:
                self._drawable_tiles.remove(tile)

    def destroy_base_group(self, tile: Tile) -> None:
        """Destroy all sub-tiles in a base group."""
        group = tile.group_tiles if tile.group_tiles else [tile]
        for t in group:
            self.set_tile_type(t, TileType.BASE_DESTROYED)

    def place_tile(self, x: int, y: int, tile: Tile) -> None:
        """Place a tile at grid coordinates and invalidate caches."""
        old_tile = self.tiles[y][x]
        if old_tile and old_tile.type != TileType.EMPTY:
            try:
                self._drawable_tiles.remove(old_tile)
            except ValueError:
                pass
        self.tiles[y][x] = tile
        if tile.type != TileType.EMPTY:
            self._drawable_tiles.append(tile)
        self._tile_cache_dirty = True

    def _rebuild_tile_caches(self) -> None:
        """Rebuild all cached tile lists from the grid."""
        self._cached_tiles_by_type = {}
        collidable_types = IMPASSABLE_TILE_TYPES
        collidable_rects = []
        base = None

        for row in self.tiles:
            for tile in row:
                if not tile:
                    continue
                tt = tile.type
                if tt not in self._cached_tiles_by_type:
                    self._cached_tiles_by_type[tt] = []
                self._cached_tiles_by_type[tt].append(tile)
                if tt in collidable_types:
                    collidable_rects.append(tile.rect)
                if tt == TileType.BASE and base is None:
                    base = tile

        self._cached_collidable_rects = collidable_rects
        self._cached_base = base
        self._tile_cache_dirty = False

    def _ensure_cache(self) -> None:
        """Rebuild caches if dirty."""
        if self._tile_cache_dirty:
            self._rebuild_tile_caches()

    def get_tiles_by_type(self, types: Iterable[TileType]) -> List[Tile]:
        """Get a list of tiles matching the specified types."""
        self._ensure_cache()
        result = []
        for tt in types:
            result.extend(self._cached_tiles_by_type.get(tt, []))
        return result

    def get_base(self) -> Optional[Tile]:
        """Find and return a player base tile, if it exists."""
        self._ensure_cache()
        return self._cached_base

    def get_collidable_tiles(self) -> List[pygame.Rect]:
        """Get a list of rectangles for all collidable tiles."""
        self._ensure_cache()
        return self._cached_collidable_rects
