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

    Uses a grid where each cell is one TMX tile (8x8 in the atlas,
    rendered at SUB_TILE_SIZE). Each TMX cell maps 1:1 to one grid cell.
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
            f"Map loaded from {map_file}: {self.width}x{self.height} tiles, "
            f"{len(self.spawn_points)} spawn points, "
            f"player spawn at {self.player_spawn}"
        )

    def _load_from_tmx(self, map_file: str) -> None:
        """Load map data from a TMX file. Each TMX cell maps 1:1 to a grid cell."""
        tiled_map = load_pygame(map_file)

        self.width = tiled_map.width
        self.height = tiled_map.height

        # Scan tileset for brick variant and water frame sprites
        self._brick_variant_sprites: dict[str, pygame.Surface] = {}
        self._water_frame_sprites: dict[int, pygame.Surface] = {}
        self._scan_tileset(tiled_map)

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
                tile_type = TileType.EMPTY
                brick_variant = "full"
                tile_image = None

                if gid:
                    props = tiled_map.get_tile_properties_by_gid(gid)
                    if props:
                        tile_type_str = props.get("tile_type")
                        if tile_type_str and tile_type_str.strip():
                            tile_type = TileType[tile_type_str.strip()]
                        brick_variant = props.get("brick_variant") or "full"

                    raw_img = tiled_map.get_tile_image_by_gid(gid)
                    if raw_img:
                        tile_image = pygame.transform.scale(
                            raw_img,
                            (SUB_TILE_SIZE, SUB_TILE_SIZE),
                        )

                tile = Tile(
                    tile_type,
                    x,
                    y,
                    self.tile_size,
                    tmx_sprite=tile_image,
                    brick_variant=brick_variant,
                )

                # Set up water animation with TMX sprites if available
                if tile_type == TileType.WATER and self._water_frame_sprites:
                    frames = sorted(self._water_frame_sprites.keys())
                    tile.animation_sprites = [
                        self._water_frame_sprites[f] for f in frames
                    ]

                self.tiles[y][x] = tile

        # Fill any remaining None tiles with EMPTY
        for y in range(self.height):
            for x in range(self.width):
                if self.tiles[y][x] is None:
                    self.tiles[y][x] = Tile(TileType.EMPTY, x, y, self.tile_size)

        # Read spawn points from object layer
        self._load_spawn_points(tiled_map)

    def _scan_tileset(self, tiled_map: pytmx.TiledMap) -> None:
        """Scan the tileset for brick variant and water frame sprites."""
        if not tiled_map.tilesets:
            return
        ts = tiled_map.tilesets[0]
        for gid in range(ts.firstgid, ts.firstgid + ts.tilecount):
            props = tiled_map.get_tile_properties_by_gid(gid)
            if not props:
                continue
            tt = props.get("tile_type") or ""
            if tt == "BRICK":
                variant = props.get("brick_variant") or "full"
                if variant not in self._brick_variant_sprites:
                    raw_img = tiled_map.get_tile_image_by_gid(gid)
                    if raw_img:
                        self._brick_variant_sprites[variant] = (
                            pygame.transform.scale(
                                raw_img, (SUB_TILE_SIZE, SUB_TILE_SIZE)
                            )
                        )
            elif tt == "WATER":
                frame = props.get("water_frame")
                if frame is not None and int(frame) not in self._water_frame_sprites:
                    raw_img = tiled_map.get_tile_image_by_gid(gid)
                    if raw_img:
                        self._water_frame_sprites[int(frame)] = (
                            pygame.transform.scale(
                                raw_img, (SUB_TILE_SIZE, SUB_TILE_SIZE)
                            )
                        )

    def _load_spawn_points(self, tiled_map: pytmx.TiledMap) -> None:
        """Read spawn points and player spawn from TMX object layers.

        Converts TMX pixel coordinates to grid coordinates.
        """
        try:
            spawn_layer = tiled_map.get_layer_by_name("spawn_points")
        except ValueError:
            logger.warning("No 'spawn_points' object layer found in TMX")
            self.player_spawn = (self.width // 2 - 1, self.height - 2)
            return

        player_spawn_found = False
        tmx_tw = tiled_map.tilewidth
        tmx_th = tiled_map.tileheight
        for obj in spawn_layer:
            # Convert pixel coords to grid coords using TMX tile dimensions
            grid_x = int(obj.x // tmx_tw)
            grid_y = int(obj.y // tmx_th)

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
        """Get the tile at the specified grid coordinates."""
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.tiles[y][x]
        return None

    def mark_tile_cache_dirty(self) -> None:
        """Mark tile caches as needing rebuild."""
        self._tile_cache_dirty = True

    def damage_brick(self, tile: Tile, bullet_direction: str) -> None:
        """Damage a brick tile based on bullet direction.

        Full bricks become half-bricks (keeping the side opposite to impact).
        Half-bricks are destroyed entirely (set to EMPTY).
        """
        if tile.type != TileType.BRICK:
            return

        if tile.brick_variant == "full":
            # Map bullet direction to the half that survives
            direction_to_variant = {
                "right": "right",
                "left": "left",
                "down": "bottom",
                "up": "top",
            }
            surviving_variant = direction_to_variant.get(bullet_direction, "full")
            sprite = self._brick_variant_sprites.get(surviving_variant)
            if sprite:
                tile.brick_variant = surviving_variant
                tile.tmx_sprite = sprite
            else:
                # No half-brick sprite available — destroy entirely
                self.set_tile_type(tile, TileType.EMPTY)
        else:
            # Half-brick hit — destroy entirely
            self.set_tile_type(tile, TileType.EMPTY)

    def set_tile_type(self, tile: Tile, new_type: TileType) -> None:
        """Change a tile's type and invalidate caches."""
        old_type = tile.type
        tile.type = new_type
        self._tile_cache_dirty = True
        if old_type == TileType.EMPTY and new_type != TileType.EMPTY:
            self._drawable_tiles.append(tile)
        elif old_type != TileType.EMPTY and new_type == TileType.EMPTY:
            if tile in self._drawable_tiles:
                self._drawable_tiles.remove(tile)

    def destroy_base(self) -> None:
        """Destroy all BASE tiles on the map."""
        for t in self.get_tiles_by_type([TileType.BASE]):
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

    def get_base_surrounding_tiles(self) -> List[Tile]:
        """Return non-empty tiles in the ring around the base.

        Finds all BASE tiles to determine the base bounds, then returns
        non-empty, non-BASE tiles in a ring around them.
        """
        base_tiles = self.get_tiles_by_type([TileType.BASE])
        if not base_tiles:
            return []

        # Find bounding box of all base tiles
        min_x = min(t.x for t in base_tiles)
        max_x = max(t.x for t in base_tiles)
        min_y = min(t.y for t in base_tiles)
        max_y = max(t.y for t in base_tiles)
        base_positions = {(t.x, t.y) for t in base_tiles}

        # Ring around the base bounding box
        surrounding = []
        for y in range(min_y - 1, max_y + 2):
            for x in range(min_x - 1, max_x + 2):
                if (x, y) in base_positions:
                    continue
                tile = self.get_tile_at(x, y)
                if tile is not None and tile.type != TileType.EMPTY:
                    surrounding.append(tile)
        return surrounding
