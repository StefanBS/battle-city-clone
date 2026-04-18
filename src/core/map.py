from dataclasses import dataclass, field
from collections.abc import Iterable
import pygame
import pytmx
from pytmx.util_pygame import load_pygame
from loguru import logger
from .tile import BrickVariant, Tile, TileDefaults, TileType
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    Difficulty,
    Direction,
    ENEMY_SPAWN_INTERVAL,
    POWERUP_CARRIER_INDICES,
    SUB_TILE_SIZE,
    TankType,
)


@dataclass(frozen=True)
class SpawnPoints:
    """Spawn-point layout parsed from a TMX map."""

    player_spawn: tuple[int, int]
    player_spawn_2: tuple[int, int] | None = None
    enemy_spawns: list[tuple[int, int]] = field(default_factory=list)


def load_spawn_points(
    tiled_map: pytmx.TiledMap, map_width: int, map_height: int
) -> SpawnPoints:
    """Parse spawn points and player spawn(s) from a TMX object layer.

    Converts TMX pixel coordinates to grid coordinates. Missing spawn
    layers or missing player_spawn objects fall back to sensible defaults
    derived from the map dimensions.
    """
    spawn_layer = next(
        (g for g in tiled_map.objectgroups if g.name == "spawn_points"),
        None,
    )
    if spawn_layer is None:
        logger.warning("No 'spawn_points' object layer found in TMX")
        return SpawnPoints(player_spawn=(map_width // 2 - 1, map_height - 2))

    player_spawn: tuple[int, int] | None = None
    player_spawn_2: tuple[int, int] | None = None
    enemy_spawns: list[tuple[int, int]] = []
    tmx_tw = tiled_map.tilewidth
    tmx_th = tiled_map.tileheight
    for obj in spawn_layer:
        grid_x = int(obj.x // tmx_tw)
        grid_y = int(obj.y // tmx_th)

        # Prefer spawn_point_type property, fall back to object name
        obj_props = obj.properties if hasattr(obj, "properties") else {}
        spawn_type = obj_props.get("spawn_point_type") if obj_props else None
        if spawn_type is None:
            spawn_type = obj.name

        if spawn_type == "player_spawn":
            player_spawn = (grid_x, grid_y)
        elif spawn_type == "player_spawn_2":
            player_spawn_2 = (grid_x, grid_y)
        else:
            enemy_spawns.append((grid_x, grid_y))

    if player_spawn is None:
        logger.warning("No 'player_spawn' object found, defaulting to bottom-center")
        player_spawn = (map_width // 2 - 2, map_height - 4)

    return SpawnPoints(
        player_spawn=player_spawn,
        player_spawn_2=player_spawn_2,
        enemy_spawns=enemy_spawns,
    )


class Map:
    """Manages the game map and its tiles.

    Uses a grid where each cell is one TMX tile (8x8 in the atlas,
    rendered at SUB_TILE_SIZE). Each TMX cell maps 1:1 to one grid cell.
    """

    # Bullet direction → surviving brick half variant
    _DIRECTION_TO_VARIANT = {
        Direction.RIGHT: BrickVariant.RIGHT,
        Direction.LEFT: BrickVariant.LEFT,
        Direction.DOWN: BrickVariant.BOTTOM,
        Direction.UP: BrickVariant.TOP,
    }

    def __init__(self, map_file: str, texture_manager: TextureManager) -> None:
        self.tile_size = SUB_TILE_SIZE
        self.texture_manager = texture_manager
        self.tiles: list[list[Tile | None]] = []
        self.spawn_points: list[tuple[int, int]] = []
        self.player_spawn: tuple[int, int] = (0, 0)
        self.player_spawn_2: tuple[int, int] | None = None
        self._animated_tiles: list[Tile] = []
        self._drawable_tiles: list[Tile] = []
        self._tile_cache_dirty: bool = True
        self._cached_tiles_by_type: dict = {}
        self._cached_blocking_tiles: list[Tile] = []
        self._cached_bullet_blocking_tiles: list[Tile] = []

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

        # Scan tileset for brick variant sprites and collision defaults
        self._brick_variant_sprites: dict[BrickVariant, pygame.Surface] = {}
        self._tile_type_sprites: dict[TileType, pygame.Surface] = {}
        self._base_destroyed_sprites: list[pygame.Surface] = []
        self._tile_collision_defaults: dict[TileType, TileDefaults] = {}
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
                brick_variant = BrickVariant.FULL
                tile_image = None
                blocks_tanks = False
                blocks_bullets = False
                is_destructible = False
                is_overlay = False
                is_slidable = False
                props = None

                if gid:
                    props = tiled_map.get_tile_properties_by_gid(gid)
                    if props:
                        tile_type_str = (props.get("tile_type") or "").strip()
                        if tile_type_str:
                            tile_type = TileType[tile_type_str]
                        bv_str = props.get("brick_variant")
                        if bv_str:
                            brick_variant = BrickVariant(bv_str)
                        blocks_tanks = bool(props.get("blocks_tanks", False))
                        blocks_bullets = bool(props.get("blocks_bullets", False))
                        is_destructible = bool(props.get("is_destructible", False))
                        is_overlay = bool(props.get("is_overlay", False))
                        is_slidable = bool(props.get("is_slidable", False))

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
                    is_destructible=is_destructible,
                    is_overlay=is_overlay,
                    is_slidable=is_slidable,
                )

                # Check for native animation frames from TSX
                frames_data = props.get("frames") if props else None
                if frames_data:
                    if gid not in animation_cache:
                        animation_frames = []
                        for anim_frame in frames_data:
                            raw_img = tiled_map.get_tile_image_by_gid(anim_frame.gid)
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
        spawns = load_spawn_points(tiled_map, self.width, self.height)
        self.player_spawn = spawns.player_spawn
        self.player_spawn_2 = spawns.player_spawn_2
        self.spawn_points = spawns.enemy_spawns

        # Read enemy composition from map-level properties
        self._read_level_properties(tiled_map)

    def _scan_tileset(self, tiled_map: pytmx.TiledMap) -> None:
        """Scan the tileset for brick variant sprites and collision defaults.

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
        base_destroyed_gids: list[int] = []
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
                # Build collision defaults from TSX (first occurrence wins)
                if tile_type_enum not in self._tile_collision_defaults:
                    self._tile_collision_defaults[tile_type_enum] = TileDefaults(
                        blocks_tanks=bool(props.get("blocks_tanks", False)),
                        blocks_bullets=bool(props.get("blocks_bullets", False)),
                        is_destructible=bool(props.get("is_destructible", False)),
                        is_overlay=bool(props.get("is_overlay", False)),
                        is_slidable=bool(props.get("is_slidable", False)),
                    )
            if tt == "BRICK":
                bv_str = props.get("brick_variant") or "full"
                key = BrickVariant(bv_str)
                self._cache_sprite(self._brick_variant_sprites, key, tiled_map, gid)
            if tt == "BASE_DESTROYED":
                base_destroyed_gids.append(gid)

        # Atlas GIDs are assigned left-to-right top-to-bottom, so sorting
        # yields row-major order [TL, TR, BL, BR] for the 2x2 base.
        for gid in sorted(base_destroyed_gids):
            raw_img = tiled_map.get_tile_image_by_gid(gid)
            if raw_img:
                self._base_destroyed_sprites.append(
                    pygame.transform.scale(raw_img, (SUB_TILE_SIZE, SUB_TILE_SIZE))
                )

    def _cache_sprite(self, cache: dict, key, tiled_map, gid: int) -> None:
        """Store a scaled tile sprite in cache if not already present."""
        if key in cache:
            return
        raw_img = tiled_map.get_tile_image_by_gid(gid)
        if raw_img:
            cache[key] = pygame.transform.scale(raw_img, (SUB_TILE_SIZE, SUB_TILE_SIZE))

    def _read_level_properties(self, tiled_map: pytmx.TiledMap) -> None:
        """Read per-level properties from TMX map-level custom properties.

        Reads enemy composition, spawn interval, difficulty override,
        and power-up carrier indices. All properties fall back to
        sensible defaults when absent.
        """
        props = tiled_map.properties or {}

        # Enemy composition (existing logic)
        composition = {
            TankType.BASIC: int(props.get("enemy_basic", 0)),
            TankType.FAST: int(props.get("enemy_fast", 0)),
            TankType.POWER: int(props.get("enemy_power", 0)),
            TankType.ARMOR: int(props.get("enemy_armor", 0)),
        }
        total = sum(composition.values())
        if total == 0:
            logger.warning("No enemy composition in map properties, using defaults")
            composition = {
                TankType.BASIC: 20,
                TankType.FAST: 0,
                TankType.POWER: 0,
                TankType.ARMOR: 0,
            }
        self.enemy_composition = composition

        # Spawn interval
        self.spawn_interval: float = float(
            props.get("spawn_interval", ENEMY_SPAWN_INTERVAL)
        )

        # Difficulty override
        diff_str = props.get("difficulty")
        if diff_str is not None:
            try:
                self.difficulty_override: Difficulty | None = Difficulty(
                    str(diff_str).strip()
                )
            except ValueError:
                logger.warning(
                    f"Invalid difficulty value '{diff_str}', ignoring override"
                )
                self.difficulty_override = None
        else:
            self.difficulty_override = None

        # Power-up carrier indices
        carriers_str = props.get("powerup_carriers")
        if carriers_str:
            try:
                self.powerup_carrier_indices: tuple[int, ...] = tuple(
                    int(s.strip()) for s in str(carriers_str).split(",")
                )
            except ValueError:
                logger.warning(
                    f"Invalid powerup_carriers '{carriers_str}', using defaults"
                )
                self.powerup_carrier_indices = POWERUP_CARRIER_INDICES
        else:
            self.powerup_carrier_indices = POWERUP_CARRIER_INDICES

    def _build_derived_tile_lists(self) -> None:
        """Build the lists of animated, drawable, and overlay tiles."""
        self._animated_tiles = []
        self._drawable_tiles = []
        self._overlay_tiles = []
        for row in self.tiles:
            for tile in row:
                if not tile:
                    continue
                if tile.is_overlay:
                    self._overlay_tiles.append(tile)
                elif tile.type != TileType.EMPTY:
                    self._drawable_tiles.append(tile)
                if tile.is_animated:
                    self._animated_tiles.append(tile)

    @property
    def width_px(self) -> int:
        """Map width in pixels."""
        return self.width * self.tile_size

    @property
    def height_px(self) -> int:
        """Map height in pixels."""
        return self.height * self.tile_size

    @property
    def drawable_tiles(self) -> list[Tile]:
        """Tiles that are drawn below tanks and bullets."""
        return self._drawable_tiles

    @property
    def overlay_tiles(self) -> list[Tile]:
        """Tiles that are drawn above tanks and bullets (e.g. bushes)."""
        return self._overlay_tiles

    def grid_to_pixels(self, grid_x: int, grid_y: int) -> tuple[int, int]:
        """Convert grid coordinates to pixel coordinates."""
        return grid_x * self.tile_size, grid_y * self.tile_size

    def update(self, dt: float) -> None:
        """Update animated tiles only."""
        for tile in self._animated_tiles:
            tile.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Draw non-empty, non-overlay tiles on the given surface."""
        for tile in self._drawable_tiles:
            tile.draw(surface, self.texture_manager)

    def draw_overlay(self, surface: pygame.Surface) -> None:
        """Draw overlay tiles (bushes) on top of tanks and bullets."""
        for tile in self._overlay_tiles:
            tile.draw(surface, self.texture_manager)

    def get_tile_at(self, x: int, y: int) -> Tile | None:
        """Get the tile at the specified grid coordinates."""
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.tiles[y][x]
        return None

    def mark_tile_cache_dirty(self) -> None:
        """Mark tile caches as needing rebuild."""
        self._tile_cache_dirty = True

    def damage_brick(
        self, tile: Tile, bullet_direction: Direction, bullet_rect: pygame.Rect
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
        if bullet_direction in (Direction.LEFT, Direction.RIGHT):
            offsets = [(0, -1), (0, 1)]  # above and below
        else:
            offsets = [(-1, 0), (1, 0)]  # left and right

        for dx, dy in offsets:
            adj = self.get_tile_at(tile.x + dx, tile.y + dy)
            if adj and adj.type == TileType.BRICK and bullet_rect.colliderect(adj.rect):
                self._damage_single_brick(adj, bullet_direction)

    # Half-brick rect offsets: variant → (dx, dy, w, h) as fractions of tile size
    _VARIANT_RECT = {
        BrickVariant.LEFT: (0, 0, 0.5, 1),
        BrickVariant.RIGHT: (0.5, 0, 0.5, 1),
        BrickVariant.TOP: (0, 0, 1, 0.5),
        BrickVariant.BOTTOM: (0, 0.5, 1, 0.5),
    }

    def _damage_single_brick(self, tile: Tile, bullet_direction: Direction) -> None:
        """Damage one brick tile. Full → half, half → destroyed."""
        if tile.type != TileType.BRICK:
            return

        if tile.brick_variant != BrickVariant.FULL:
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

    def _remove_from_render_lists(self, tile: Tile) -> None:
        """Remove a tile from drawable and overlay lists."""
        if tile in self._drawable_tiles:
            self._drawable_tiles.remove(tile)
        if tile in self._overlay_tiles:
            self._overlay_tiles.remove(tile)

    def _add_to_render_list(self, tile: Tile) -> None:
        """Add a tile to the appropriate render list based on its type."""
        if tile.is_overlay:
            self._overlay_tiles.append(tile)
        elif tile.type != TileType.EMPTY:
            self._drawable_tiles.append(tile)

    def set_tile_type(self, tile: Tile, new_type: TileType) -> None:
        """Change a tile's type, update collision flags, and invalidate caches."""
        old_type = tile.type
        tile.type = new_type
        tile.tmx_sprite = self._tile_type_sprites.get(new_type)
        defaults = self._tile_collision_defaults.get(new_type, TileDefaults())
        tile.blocks_tanks = defaults.blocks_tanks
        tile.blocks_bullets = defaults.blocks_bullets
        tile.is_destructible = defaults.is_destructible
        tile.is_overlay = defaults.is_overlay
        tile.is_slidable = defaults.is_slidable
        self._tile_cache_dirty = True
        if old_type != new_type:
            self._remove_from_render_lists(tile)
            self._add_to_render_list(tile)

    def destroy_base(self) -> None:
        """Destroy all BASE tiles, assigning each sub-tile its matching
        quadrant of the 2x2 destroyed-base artwork."""
        base_tiles = self.get_tiles_by_type([TileType.BASE])
        if not base_tiles:
            return
        min_x = min(t.x for t in base_tiles)
        min_y = min(t.y for t in base_tiles)
        for t in base_tiles:
            self.set_tile_type(t, TileType.BASE_DESTROYED)
            quadrant = (t.y - min_y) * 2 + (t.x - min_x)
            t.tmx_sprite = self._base_destroyed_sprites[quadrant]

    def place_tile(self, x: int, y: int, tile: Tile) -> None:
        """Place a tile at grid coordinates and invalidate caches."""
        old_tile = self.tiles[y][x]
        if old_tile:
            self._remove_from_render_lists(old_tile)
        self.tiles[y][x] = tile
        self._add_to_render_list(tile)
        self._tile_cache_dirty = True

    def _rebuild_tile_caches(self) -> None:
        """Rebuild all cached tile lists from the grid."""
        self._cached_tiles_by_type = {}
        blocking_tiles: list[Tile] = []
        bullet_blocking_tiles: list[Tile] = []

        for row in self.tiles:
            for tile in row:
                if not tile:
                    continue
                self._cached_tiles_by_type.setdefault(tile.type, []).append(tile)
                if tile.blocks_tanks:
                    blocking_tiles.append(tile)
                if tile.blocks_bullets:
                    bullet_blocking_tiles.append(tile)

        self._cached_blocking_tiles = blocking_tiles
        self._cached_bullet_blocking_tiles = bullet_blocking_tiles
        self._tile_cache_dirty = False

    def _ensure_cache(self) -> None:
        """Rebuild caches if dirty."""
        if self._tile_cache_dirty:
            self._rebuild_tile_caches()

    def get_tiles_by_type(self, types: Iterable[TileType]) -> list[Tile]:
        """Get a list of tiles matching the specified types."""
        self._ensure_cache()
        result = []
        for tt in types:
            result.extend(self._cached_tiles_by_type.get(tt, []))
        return result

    def is_tile_slidable(
        self, tank_x: float, tank_y: float, tank_w: float, tank_h: float
    ) -> bool:
        """Check if the tile under a tank's center is slidable (ice).

        Args:
            tank_x: Tank x position in pixels.
            tank_y: Tank y position in pixels.
            tank_w: Tank width in pixels.
            tank_h: Tank height in pixels.

        Returns:
            True if the tile under the tank center has is_slidable set.
        """
        center_x = int(tank_x + tank_w / 2)
        center_y = int(tank_y + tank_h / 2)
        grid_x = center_x // self.tile_size
        grid_y = center_y // self.tile_size
        tile = self.get_tile_at(grid_x, grid_y)
        return tile is not None and tile.is_slidable

    def get_base(self) -> Tile | None:
        """Find and return a player base tile, if it exists."""
        self._ensure_cache()
        base_tiles = self._cached_tiles_by_type.get(TileType.BASE)
        return base_tiles[0] if base_tiles else None

    def get_collidable_tiles(self) -> list[pygame.Rect]:
        """Get a list of rectangles for all collidable tiles."""
        self._ensure_cache()
        return [t.rect for t in self._cached_blocking_tiles]

    def get_blocking_tiles(self) -> list[Tile]:
        """Get all tiles that block tank movement."""
        self._ensure_cache()
        return self._cached_blocking_tiles

    def get_bullet_blocking_tiles(self) -> list[Tile]:
        """Get all tiles that block bullets."""
        self._ensure_cache()
        return self._cached_bullet_blocking_tiles

    def get_base_surrounding_tiles(self, include_empty: bool = False) -> list[Tile]:
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
