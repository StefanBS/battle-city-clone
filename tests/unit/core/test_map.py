import pytest
from unittest.mock import MagicMock
from src.core.map import Map, load_spawn_points
from src.core.tile import TileDefaults, TileType
from src.utils.constants import (
    Difficulty,
    ENEMY_SPAWN_INTERVAL,
    POWERUP_CARRIER_INDICES,
    TankType,
)
from src.utils.paths import resource_path

TEST_MAP_PATH = "tests/assets/test_map.tmx"


@pytest.fixture
def game_map(mock_texture_manager):
    return Map(TEST_MAP_PATH, mock_texture_manager)


@pytest.fixture
def write_tmx(tmp_path):
    """Write an ad-hoc TMX string to ``tmp_path`` and return its path.

    The TMX body may use the placeholder ``{tsx}`` in the tileset ``source``
    attribute; it will be substituted with the absolute path to the bundled
    ``assets/sprites/sprites.tsx`` so the map loads from outside
    ``tests/assets/``.
    """
    tsx_path = resource_path("assets/sprites/sprites.tsx")

    def _write(content: str, filename: str = "map.tmx") -> str:
        path = tmp_path / filename
        path.write_text(content.format(tsx=tsx_path))
        return str(path)

    return _write


# Formatted twice: ``{properties}`` by minimal_tmx, then ``{tsx}`` by write_tmx.
_MINIMAL_TMX = """\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.11.2" orientation="orthogonal" \
renderorder="right-down" width="2" height="2" tilewidth="8" tileheight="8" \
infinite="0" nextlayerid="2" nextobjectid="1">
{properties}
 <tileset firstgid="1" source="{{tsx}}"/>
 <layer id="1" name="Tile Layer 1" width="2" height="2">
  <data encoding="csv">
0,0,
0,0
</data>
 </layer>
</map>
"""


def minimal_tmx(**properties: str) -> str:
    """Return a 2x2 empty TMX with the given map properties, for ``write_tmx``."""
    block = ""
    if properties:
        lines = "".join(
            f'  <property name="{name}" value="{value}"/>\n'
            for name, value in properties.items()
        )
        block = f" <properties>\n{lines} </properties>"
    return _MINIMAL_TMX.format(properties=block)


def _rules(tile):
    """Return a tile's rule flags as a TileDefaults, for comparing to a table row."""
    return TileDefaults(
        blocks_tanks=tile.blocks_tanks,
        blocks_bullets=tile.blocks_bullets,
        is_destructible=tile.is_destructible,
        is_overlay=tile.is_overlay,
        is_slidable=tile.is_slidable,
    )


class TestMapLoading:
    """Tests for TMX-based map loading.

    The test TMX is 10x10 tiles at 8x8. Each cell maps 1:1 to a grid cell.

    Layout (showing 2x2 blocks corresponding to old 16x16 tiles):
    Row 0-1: STEEL .. .. .. STEEL
    Row 2-3: .. BRICK .. BRICK ..
    Row 4-5: .. .. WATER .. ..
    Row 6-7: .. .. .. .. ..
    Row 8-9: .. .. BASE .. ..
    """

    def test_map_dimensions(self, game_map):
        """Grid matches TMX dimensions directly (no expansion)."""
        assert game_map.width == 10
        assert game_map.height == 10

    def test_tiles_populated(self, game_map):
        for y in range(game_map.height):
            for x in range(game_map.width):
                tile = game_map.get_tile_at(x, y)
                assert tile is not None, f"Tile at ({x}, {y}) is None"

    def test_spawn_points_from_tmx(self, game_map):
        assert len(game_map.spawn_points) >= 1
        for point in game_map.spawn_points:
            assert isinstance(point, tuple)
            assert len(point) == 2

    def test_player_spawn_from_tmx(self, game_map):
        assert isinstance(game_map.player_spawn, tuple)
        assert len(game_map.player_spawn) == 2
        # player_spawn is at pixel (32, 48), tilewidth=8
        # grid coords: (32//8, 48//8) = (4, 6)
        assert game_map.player_spawn == (4, 6)

    def test_brick_tiles_independently_destructible(self, game_map):
        """Each brick tile can be destroyed independently."""
        # BRICK tiles at (2,2), (3,2), (2,3), (3,3)
        for sx, sy in [(2, 2), (3, 2), (2, 3), (3, 3)]:
            assert game_map.get_tile_at(sx, sy).type == TileType.BRICK

        # Destroy one tile
        tile = game_map.get_tile_at(2, 2)
        game_map.set_tile_type(tile, TileType.EMPTY)

        # Only that tile is EMPTY, others remain BRICK
        assert game_map.get_tile_at(2, 2).type == TileType.EMPTY
        assert game_map.get_tile_at(3, 2).type == TileType.BRICK
        assert game_map.get_tile_at(2, 3).type == TileType.BRICK
        assert game_map.get_tile_at(3, 3).type == TileType.BRICK

    def test_base_destruction(self, game_map):
        """Destroying base destroys all BASE tiles."""
        # BASE at (4,8), (5,8), (4,9), (5,9)
        for sx, sy in [(4, 8), (5, 8), (4, 9), (5, 9)]:
            assert game_map.get_tile_at(sx, sy).type == TileType.BASE

        game_map.destroy_base()

        for sx, sy in [(4, 8), (5, 8), (4, 9), (5, 9)]:
            assert game_map.get_tile_at(sx, sy).type == TileType.BASE_DESTROYED

    def test_base_destruction_uses_distinct_quadrant_sprites(self, game_map):
        """Each destroyed-base sub-tile gets its matching quadrant sprite."""
        game_map.destroy_base()

        tl = game_map.get_tile_at(4, 8).tmx_sprite
        tr = game_map.get_tile_at(5, 8).tmx_sprite
        bl = game_map.get_tile_at(4, 9).tmx_sprite
        br = game_map.get_tile_at(5, 9).tmx_sprite

        # All four sub-tiles must carry a sprite and none may share identity
        # with another — that was the original bug (all four rendered the
        # top-left sub-sprite).
        sprites = [tl, tr, bl, br]
        assert all(s is not None for s in sprites)
        assert len({id(s) for s in sprites}) == 4


class TestTileRulesFromTileset:
    """Tile rules come from the TSX properties of each tile's type."""

    @pytest.mark.parametrize(
        "cell, tile_type, rules",
        [
            ((4, 6), TileType.EMPTY, TileDefaults()),
            (
                (2, 2),
                TileType.BRICK,
                TileDefaults(
                    blocks_tanks=True, blocks_bullets=True, is_destructible=True
                ),
            ),
            (
                (0, 0),
                TileType.STEEL,
                TileDefaults(blocks_tanks=True, blocks_bullets=True),
            ),
            ((4, 4), TileType.WATER, TileDefaults(blocks_tanks=True)),
            ((0, 6), TileType.BUSH, TileDefaults(is_overlay=True)),
            ((1, 6), TileType.ICE, TileDefaults(is_slidable=True)),
            (
                (4, 8),
                TileType.BASE,
                TileDefaults(blocks_tanks=True, blocks_bullets=True),
            ),
        ],
    )
    def test_tile_rules(self, game_map, cell, tile_type, rules):
        tile = game_map.get_tile_at(*cell)
        assert tile.type == tile_type
        assert _rules(tile) == rules

    def test_blocking_lists_follow_flags(self, game_map):
        tiles = [t for row in game_map.tiles for t in row]
        assert set(game_map.get_blocking_tiles()) == {
            t for t in tiles if t.blocks_tanks
        }
        assert set(game_map.get_bullet_blocking_tiles()) == {
            t for t in tiles if t.blocks_bullets
        }


class TestWaterAnimationFromTMX:
    """Verify water tiles get animation frames from TSX native animation."""

    def test_water_tile_is_animated(self, game_map):
        tile = game_map.get_tile_at(4, 4)  # WATER
        assert tile.is_animated is True

    def test_water_has_three_animation_frames(self, game_map):
        tile = game_map.get_tile_at(4, 4)  # WATER
        assert len(tile.animation_sprites) == 3

    def test_non_water_not_animated(self, game_map):
        tile = game_map.get_tile_at(0, 0)  # STEEL
        assert tile.is_animated is False


class TestEnemyCompositionFromTMX:
    """Verify Map reads enemy composition from TMX properties."""

    def test_enemy_composition_values(self, game_map):
        comp = game_map.enemy_composition
        assert comp[TankType.BASIC] == 18
        assert comp[TankType.FAST] == 2
        assert comp[TankType.POWER] == 0
        assert comp[TankType.ARMOR] == 0


class TestSetTileType:
    """set_tile_type applies the new type's rules from the tileset."""

    @pytest.mark.parametrize(
        "cell, new_type, rules",
        [
            ((2, 2), TileType.EMPTY, TileDefaults()),
            ((0, 6), TileType.EMPTY, TileDefaults()),
            (
                (4, 6),
                TileType.STEEL,
                TileDefaults(blocks_tanks=True, blocks_bullets=True),
            ),
            ((4, 6), TileType.WATER, TileDefaults(blocks_tanks=True)),
            (
                (4, 6),
                TileType.BRICK,
                TileDefaults(
                    blocks_tanks=True, blocks_bullets=True, is_destructible=True
                ),
            ),
        ],
    )
    def test_set_tile_type_applies_new_rules(self, game_map, cell, new_type, rules):
        tile = game_map.get_tile_at(*cell)
        game_map.set_tile_type(tile, new_type)
        assert tile.type == new_type
        assert _rules(tile) == rules


class TestEnemyCompositionFallback:
    """Verify fallback when map has no enemy composition properties."""

    def test_missing_properties_defaults_to_20_basic(
        self, mock_texture_manager, write_tmx
    ):
        """Map without enemy properties falls back to 20 basic enemies."""
        tmx_path = write_tmx(minimal_tmx())
        game_map = Map(tmx_path, mock_texture_manager)
        assert game_map.enemy_composition == {
            TankType.BASIC: 20,
            TankType.FAST: 0,
            TankType.POWER: 0,
            TankType.ARMOR: 0,
        }


class TestLevelPropertiesFromTMX:
    """Verify Map reads per-level properties from TMX map properties."""

    def test_spawn_interval_from_map(self, game_map):
        assert game_map.spawn_interval == 3.5

    def test_difficulty_override_from_map(self, game_map):
        assert game_map.difficulty_override == Difficulty.EASY

    def test_powerup_carrier_indices_from_map(self, game_map):
        assert game_map.powerup_carrier_indices == (2, 7, 14)


class TestLevelPropertiesFallback:
    """Verify fallback when map has no level properties."""

    def test_missing_spawn_interval_defaults(self, mock_texture_manager, write_tmx):
        """Map without spawn_interval falls back to ENEMY_SPAWN_INTERVAL."""
        tmx_path = write_tmx(minimal_tmx())
        game_map = Map(tmx_path, mock_texture_manager)
        assert game_map.spawn_interval == ENEMY_SPAWN_INTERVAL
        assert game_map.difficulty_override is None
        assert game_map.powerup_carrier_indices == POWERUP_CARRIER_INDICES

    def test_invalid_difficulty_falls_back(self, mock_texture_manager, write_tmx):
        """Map with invalid difficulty string falls back to None."""
        tmx_path = write_tmx(minimal_tmx(difficulty="hard"))
        game_map = Map(tmx_path, mock_texture_manager)
        assert game_map.difficulty_override is None

    def test_invalid_powerup_carriers_falls_back(self, mock_texture_manager, write_tmx):
        """Map with invalid powerup_carriers string falls back to constant."""
        tmx_path = write_tmx(minimal_tmx(powerup_carriers="3,abc,17"))
        game_map = Map(tmx_path, mock_texture_manager)
        assert game_map.powerup_carrier_indices == POWERUP_CARRIER_INDICES


class TestOverlayPropertyRendering:
    """Verify overlay list uses is_overlay property, not TileType."""

    def test_bush_in_overlay_list(self, game_map):
        overlay = game_map.overlay_tiles
        bush_found = any(t.is_overlay for t in overlay)
        assert bush_found

    def test_bush_not_in_drawable_list(self, game_map):
        drawable = game_map.drawable_tiles
        overlay_in_drawable = any(t.is_overlay for t in drawable)
        assert not overlay_in_drawable

    def test_set_tile_type_bush_to_empty_removes_from_overlay(self, game_map):
        overlay_tile = None
        for t in game_map.overlay_tiles:
            if t.is_overlay:
                overlay_tile = t
                break
        assert overlay_tile is not None
        game_map.set_tile_type(overlay_tile, TileType.EMPTY)
        assert overlay_tile not in game_map.overlay_tiles


class TestGetBaseSurroundingTiles:
    @pytest.fixture
    def stage_map(self, mock_texture_manager):
        return Map(resource_path("assets/maps/level_01.tmx"), mock_texture_manager)

    def test_returns_tiles_around_base(self, stage_map):
        tiles = stage_map.get_base_surrounding_tiles()
        assert len(tiles) > 0
        base = stage_map.get_base()
        assert base is not None

    def test_no_base_tiles_in_result(self, stage_map):
        tiles = stage_map.get_base_surrounding_tiles()
        for tile in tiles:
            assert tile.type != TileType.BASE

    def test_no_empty_tiles_in_result(self, stage_map):
        tiles = stage_map.get_base_surrounding_tiles()
        for tile in tiles:
            assert tile.type != TileType.EMPTY


def _mock_spawn_obj(name: str, x: int, y: int, properties: dict | None = None):
    """Build a minimal TMX-like spawn object for load_spawn_points tests."""
    obj = MagicMock()
    obj.name = name
    obj.x = x
    obj.y = y
    obj.properties = properties or {}
    return obj


def _mock_tiled_map(spawn_objects, tilewidth: int = 8, tileheight: int = 8):
    """Build a minimal TMX-like map wrapping the given spawn objects."""
    tiled = MagicMock()
    tiled.tilewidth = tilewidth
    tiled.tileheight = tileheight
    layer = MagicMock()
    layer.name = "spawn_points"
    layer.__iter__ = lambda self: iter(spawn_objects)
    tiled.objectgroups = [layer]
    return tiled


class TestLoadSpawnPoints:
    """Unit tests for the pure load_spawn_points function."""

    def test_player_spawn_2_loaded_from_tmx(self):
        """player_spawn_2 is loaded from spawn_points object layer."""
        tiled = _mock_tiled_map(
            [
                _mock_spawn_obj("player_spawn", 64, 192),
                _mock_spawn_obj("player_spawn_2", 128, 192),
                _mock_spawn_obj("enemy_spawn", 0, 0),
            ]
        )

        result = load_spawn_points(tiled, map_width=26, map_height=26)

        assert result.player_spawn == (8, 24)
        assert result.player_spawn_2 == (16, 24)
        assert len(result.enemy_spawns) == 1

    def test_player_spawn_2_defaults_to_none(self):
        """player_spawn_2 is None when not present in TMX."""
        tiled = _mock_tiled_map([_mock_spawn_obj("player_spawn", 64, 192)])

        result = load_spawn_points(tiled, map_width=26, map_height=26)

        assert result.player_spawn_2 is None

    def test_missing_spawn_layer_falls_back(self):
        """A map with no spawn_points layer yields a centered-bottom default."""
        tiled = MagicMock()
        tiled.objectgroups = []

        result = load_spawn_points(tiled, map_width=26, map_height=26)

        assert result.player_spawn == (26 // 2 - 1, 26 - 2)
        assert result.player_spawn_2 is None
        assert result.enemy_spawns == []

    def test_missing_player_spawn_falls_back(self):
        """Spawn layer with no player_spawn object uses bottom-center default."""
        tiled = _mock_tiled_map([_mock_spawn_obj("enemy_spawn", 0, 0)])

        result = load_spawn_points(tiled, map_width=26, map_height=26)

        assert result.player_spawn == (26 // 2 - 2, 26 - 4)
        assert result.enemy_spawns == [(0, 0)]

    def test_spawn_point_type_property_wins_over_name(self):
        """spawn_point_type property takes precedence over obj.name."""
        tiled = _mock_tiled_map(
            [
                _mock_spawn_obj(
                    "ignored", 64, 192, properties={"spawn_point_type": "player_spawn"}
                ),
            ]
        )

        result = load_spawn_points(tiled, map_width=26, map_height=26)

        assert result.player_spawn == (8, 24)
