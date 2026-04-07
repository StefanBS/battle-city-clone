from typing import Iterable, List, Optional, Tuple
import pygame
import pytmx
from pytmx.util_pygame import load_pygame
from loguru import logger
from .tile import Tile, TileType
from src.managers.texture_manager import TextureManager
from src.utils.constants import SUB_TILE_SIZE


class Map:
    """Manages the game map and its tiles.

    Uses a grid where each cell is one TMX tile (8x8 in the atlas,
    rendered at SUB_TILE_SIZE). Each TMX cell maps 1:1 to one grid cell.
    """

    # Bullet direction → surviving brick half variant
    _DIRECTION_TO_VARIANT = {
        "right": "right",
        "left": "left",
        "down": "bottom",
        "up": "top",
    }

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
        self._cached_blocking_tiles: List[Tile] = []
        self._cached_bullet_blocking_tiles: List[Tile] = []
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

        # Scan tileset for brick variant sprites
        self._brick_variant_sprites: dict[str, pygame.Surface] = {}
        self._tile_type_sprites: dict[TileType, pygame.Surface] = {}
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
            scaled_cache: dict[int, pygame.Surface] = {}
            # Cache for shared animation frame lists (keyed by source GID)
            animation_cache: dict[int, list] = {}
            for x, y, gid in tile_layer.iter_data():
                tile_type = TileType.EMPTY
                brick_variant = "full"
                tile_image = None
                blocks_tanks = False
                blocks_bullets = False
                props = None

                if gid:
                    props = tiled_map.get_tile_properties_by_gid(gid)
                    if props:
                        tile_type_str = (props.get("tile_type") or "").strip()
                        if tile_type_str:
                            tile_type = TileType[tile_type_str]
                        brick_variant = props.get("brick_variant") or "full"
                        blocks_tanks = bool(props.get("blocks_tanks", False))
                        blocks_bullets = bool(props.get("blocks_bullets", False))

                    self._cache_sprite(scaled_cache, gid, tiled_map, gid)
                    tile_image = scaled_cache.get(gid)

                tile = Tile(
                    tile_type,
                    x,
                    y,
                    self.tile_size,
                    tmx_sprite=tile_image,
                    brick_variant=brick_variant,
                    blocks_tanks=blocks_tanks,
                    blocks_bullets=blocks_bullets,
                )

                # Check for native animation frames from TSX
                frames_data = props.get("frames") if props else None
                if frames_data:
                    if gid not in animation_cache:
                        animation_frames = []
                        for anim_frame in frames_data:
                            raw_img = tiled_map.get_tile_image_by_gid(
                                anim_frame.gid
                            )
                            if raw_img:
                                scaled = pygame.transform.scale(
                                    raw_img,
                                    (self.tile_size, self.tile_size),
                                )
                                duration_s = anim_frame.duration / 1000.0
                                animation_frames.append((scaled, duration_s))
                        animation_cache[gid] = animation_frames
                    if animation_cache[gid]:
                        tile.set_animation_frames(animation_cache[gid])

                self.tiles[y][x] = tile

        # Fill any remaining None tiles with EMPTY
        for y in range(self.height):
            for x in range(self.width):
                if self.tiles[y][x] is None:
                    self.tiles[y][x] = Tile(TileType.EMPTY, x, y, self.tile_size)

        # Read spawn points from object layer
        self._load_spawn_points(tiled_map)

    def _scan_tileset(self, tiled_map: pytmx.TiledMap) -> None:
        """Scan the tileset for brick variant sprites.

        Only iterates tiles that have custom properties defined,
        skipping the majority of tiles in large tilesets.
        """
        if not tiled_map.tilesets:
            return
        ts = tiled_map.tilesets[0]
        # Only iterate tiles with defined properties (sparse iteration)
        tile_ids = getattr(ts, "tiles", {})
        if not tile_ids:
            # Fallback: iterate all GIDs if tileset doesn't expose tiles dict
            gids = range(ts.firstgid, ts.firstgid + ts.tilecount)
        else:
            gids = [tid + ts.firstgid for tid in tile_ids]
        for gid in gids:
            props = tiled_map.get_tile_properties_by_gid(gid)
            if not props:
                continue
            tt = props.get("tile_type") or ""
            if tt:
                tile_type_enum = TileType[tt]
                if tile_type_enum not in self._tile_type_sprites:
                    self._cache_sprite(
                        self._tile_type_sprites, tile_type_enum, tiled_map, gid
                    )
            if tt == "BRICK":
                key = props.get("brick_variant") or "full"
                self._cache_sprite(self._brick_variant_sprites, key, tiled_map, gid)

    def _cache_sprite(self, cache: dict, key, tiled_map, gid: int) -> None:
        """Store a scaled tile sprite in cache if not already present."""
        if key in cache:
            return
        raw_img = tiled_map.get_tile_image_by_gid(gid)
        if raw_img:
            cache[key] = pygame.transform.scale(raw_img, (SUB_TILE_SIZE, SUB_TILE_SIZE))

    def _load_spawn_points(self, tiled_map: pytmx.TiledMap) -> None:
        """Read spawn points and player spawn from TMX object layers.

        Converts TMX pixel coordinates to grid coordinates.
        """
        spawn_layer = next(
            (g for g in tiled_map.objectgroups if g.name == "spawn_points"),
            None,
        )
        if spawn_layer is None:
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

    def damage_brick(
        self, tile: Tile, bullet_direction: str, bullet_rect: pygame.Rect
    ) -> None:
        """Damage a brick tile and any adjacent brick the bullet overlaps.

        Full bricks become half-bricks (keeping the side opposite to impact).
        Half-bricks are destroyed entirely (set to EMPTY).
        Adjacent tiles in the perpendicular direction are also damaged if
        the bullet rect overlaps them.
        """
        self._damage_single_brick(tile, bullet_direction)

        # Check adjacent tiles PERPENDICULAR to bullet direction.
        # The bullet may straddle two tiles across its narrow axis.
        if bullet_direction in ("left", "right"):
            offsets = [(0, -1), (0, 1)]  # above and below
        else:
            offsets = [(-1, 0), (1, 0)]  # left and right

        for dx, dy in offsets:
            adj = self.get_tile_at(tile.x + dx, tile.y + dy)
            if adj and adj.type == TileType.BRICK and bullet_rect.colliderect(adj.rect):
                self._damage_single_brick(adj, bullet_direction)

    # Half-brick rect offsets: variant → (dx, dy, w, h) as fractions of tile size
    _VARIANT_RECT = {
        "left": (0, 0, 0.5, 1),
        "right": (0.5, 0, 0.5, 1),
        "top": (0, 0, 1, 0.5),
        "bottom": (0, 0.5, 1, 0.5),
    }

    def _damage_single_brick(self, tile: Tile, bullet_direction: str) -> None:
        """Damage one brick tile. Full → half, half → destroyed."""
        if tile.type != TileType.BRICK:
            return

        # Non-full bricks are destroyed entirely
        if tile.brick_variant != "full":
            self.set_tile_type(tile, TileType.EMPTY)
            return

        surviving_variant = self._DIRECTION_TO_VARIANT.get(bullet_direction)
        sprite = (
            self._brick_variant_sprites.get(surviving_variant)
            if surviving_variant
            else None
        )
        if not sprite:
            self.set_tile_type(tile, TileType.EMPTY)
            return

        tile.brick_variant = surviving_variant
        tile.tmx_sprite = sprite
        # Shrink collision rect to match the surviving half
        fracs = self._VARIANT_RECT.get(surviving_variant)
        if fracs:
            dx, dy, w, h = fracs
            base_x = tile.x * tile.size
            base_y = tile.y * tile.size
            tile.rect = pygame.Rect(
                int(base_x + dx * tile.size),
                int(base_y + dy * tile.size),
                int(w * tile.size),
                int(h * tile.size),
            )
        self._tile_cache_dirty = True

    # Default collision flags for tile types set at runtime via set_tile_type.
    _TILE_COLLISION_DEFAULTS: dict[TileType, tuple[bool, bool]] = {
        TileType.BRICK: (True, True),
        TileType.STEEL: (True, True),
        TileType.WATER: (True, False),
        TileType.BASE: (True, True),
        TileType.BASE_DESTROYED: (False, False),
        TileType.BUSH: (False, False),
        TileType.ICE: (False, False),
        TileType.EMPTY: (False, False),
    }

    def set_tile_type(self, tile: Tile, new_type: TileType) -> None:
        """Change a tile's type, update collision flags, and invalidate caches."""
        old_type = tile.type
        tile.type = new_type
        tile.tmx_sprite = self._tile_type_sprites.get(new_type)
        bt, bb = self._TILE_COLLISION_DEFAULTS.get(new_type, (False, False))
        tile.blocks_tanks = bt
        tile.blocks_bullets = bb
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
        collidable_rects = []
        blocking_tiles: List[Tile] = []
        bullet_blocking_tiles: List[Tile] = []
        base = None

        for row in self.tiles:
            for tile in row:
                if not tile:
                    continue
                tt = tile.type
                if tt not in self._cached_tiles_by_type:
                    self._cached_tiles_by_type[tt] = []
                self._cached_tiles_by_type[tt].append(tile)
                if tile.blocks_tanks:
                    collidable_rects.append(tile.rect)
                    blocking_tiles.append(tile)
                if tile.blocks_bullets:
                    bullet_blocking_tiles.append(tile)
                if tt == TileType.BASE and base is None:
                    base = tile

        self._cached_collidable_rects = collidable_rects
        self._cached_blocking_tiles = blocking_tiles
        self._cached_bullet_blocking_tiles = bullet_blocking_tiles
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

    def get_blocking_tiles(self) -> List[Tile]:
        """Get all tiles that block tank movement."""
        self._ensure_cache()
        return self._cached_blocking_tiles

    def get_bullet_blocking_tiles(self) -> List[Tile]:
        """Get all tiles that block bullets."""
        self._ensure_cache()
        return self._cached_bullet_blocking_tiles

    def get_base_surrounding_tiles(self, include_empty: bool = False) -> List[Tile]:
        """Return tiles in the ring around the base.

        Finds all BASE tiles to determine the base bounds, then returns
        non-BASE tiles in a ring around them.

        Args:
            include_empty: If True, include EMPTY tiles in the result.
                Useful for restoring destroyed base walls.
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
                if tile is None:
                    continue
                if tile.type != TileType.EMPTY or include_empty:
                    surrounding.append(tile)
        return surrounding
