import pytest
from src.core.map import Map
from src.core.tile import TileType
from src.utils.constants import TankType
from src.utils.paths import resource_path

TEST_MAP_PATH = "tests/assets/test_map.tmx"


@pytest.fixture
def game_map(mock_texture_manager):
    return Map(TEST_MAP_PATH, mock_texture_manager)


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

    def test_tile_types_from_tmx(self, game_map):
        """Tile types from TMX tile_type property."""
        # STEEL at (0,0)
        assert game_map.get_tile_at(0, 0).type == TileType.STEEL
        # STEEL at (8,0)
        assert game_map.get_tile_at(8, 0).type == TileType.STEEL
        # BRICK at (2,2)
        assert game_map.get_tile_at(2, 2).type == TileType.BRICK
        # BRICK at (6,2)
        assert game_map.get_tile_at(6, 2).type == TileType.BRICK
        # WATER at (4,4)
        assert game_map.get_tile_at(4, 4).type == TileType.WATER
        # BASE at (4,8)
        assert game_map.get_tile_at(4, 8).type == TileType.BASE
        # EMPTY tiles
        assert game_map.get_tile_at(2, 0).type == TileType.EMPTY
        assert game_map.get_tile_at(4, 6).type == TileType.EMPTY

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


class TestTileCollisionFromTMX:
    """Verify tiles loaded from TMX have correct collision properties."""

    @pytest.fixture
    def game_map(self, mock_texture_manager):
        return Map(TEST_MAP_PATH, mock_texture_manager)

    def test_steel_blocks_tanks(self, game_map):
        tile = game_map.get_tile_at(0, 0)  # STEEL
        assert tile.blocks_tanks is True

    def test_steel_blocks_bullets(self, game_map):
        tile = game_map.get_tile_at(0, 0)  # STEEL
        assert tile.blocks_bullets is True

    def test_water_blocks_tanks(self, game_map):
        tile = game_map.get_tile_at(4, 4)  # WATER
        assert tile.blocks_tanks is True

    def test_water_does_not_block_bullets(self, game_map):
        tile = game_map.get_tile_at(4, 4)  # WATER
        assert tile.blocks_bullets is False

    def test_empty_does_not_block(self, game_map):
        tile = game_map.get_tile_at(4, 6)  # EMPTY
        assert tile.blocks_tanks is False
        assert tile.blocks_bullets is False

    def test_base_blocks_both(self, game_map):
        tile = game_map.get_tile_at(4, 8)  # BASE
        assert tile.blocks_tanks is True
        assert tile.blocks_bullets is True

    def test_brick_blocks_both(self, game_map):
        tile = game_map.get_tile_at(2, 2)  # BRICK
        assert tile.blocks_tanks is True
        assert tile.blocks_bullets is True


class TestGetBlockingTiles:
    """Tests for get_blocking_tiles and get_bullet_blocking_tiles."""

    @pytest.fixture
    def game_map(self, mock_texture_manager):
        return Map(TEST_MAP_PATH, mock_texture_manager)

    def test_get_blocking_tiles_returns_tank_blockers(self, game_map):
        tiles = game_map.get_blocking_tiles()
        assert len(tiles) > 0
        for tile in tiles:
            assert tile.blocks_tanks is True

    def test_get_bullet_blocking_tiles_returns_bullet_blockers(self, game_map):
        tiles = game_map.get_bullet_blocking_tiles()
        assert len(tiles) > 0
        for tile in tiles:
            assert tile.blocks_bullets is True

    def test_water_in_blocking_but_not_bullet_blocking(self, game_map):
        blocking = game_map.get_blocking_tiles()
        bullet_blocking = game_map.get_bullet_blocking_tiles()
        water_tiles = [t for t in blocking if t.type == TileType.WATER]
        assert len(water_tiles) > 0
        for wt in water_tiles:
            assert wt not in bullet_blocking


class TestWaterAnimationFromTMX:
    """Verify water tiles get animation frames from TSX native animation."""

    @pytest.fixture
    def game_map(self, mock_texture_manager):
        return Map(TEST_MAP_PATH, mock_texture_manager)

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

    @pytest.fixture
    def game_map(self, mock_texture_manager):
        return Map("tests/assets/test_map.tmx", mock_texture_manager)

    def test_enemy_composition_available(self, game_map):
        assert hasattr(game_map, "enemy_composition")

    def test_enemy_composition_values(self, game_map):
        comp = game_map.enemy_composition
        assert comp[TankType.BASIC] == 18
        assert comp[TankType.FAST] == 2
        assert comp[TankType.POWER] == 0
        assert comp[TankType.ARMOR] == 0

    def test_enemy_composition_sum(self, game_map):
        comp = game_map.enemy_composition
        assert sum(comp.values()) == 20


class TestCollisionDefaultsFromTSX:
    """Verify collision defaults are read from TSX, not hardcoded."""

    @pytest.fixture
    def game_map(self, mock_texture_manager):
        return Map(TEST_MAP_PATH, mock_texture_manager)

    def test_set_tile_type_updates_collision_flags(self, game_map):
        """Changing tile type via set_tile_type updates collision flags."""
        tile = game_map.get_tile_at(2, 2)  # BRICK
        assert tile.blocks_tanks is True
        game_map.set_tile_type(tile, TileType.EMPTY)
        assert tile.blocks_tanks is False
        assert tile.blocks_bullets is False

    def test_set_tile_type_to_steel(self, game_map):
        tile = game_map.get_tile_at(4, 6)  # EMPTY
        game_map.set_tile_type(tile, TileType.STEEL)
        assert tile.blocks_tanks is True
        assert tile.blocks_bullets is True

    def test_set_tile_type_to_water(self, game_map):
        tile = game_map.get_tile_at(4, 6)  # EMPTY
        game_map.set_tile_type(tile, TileType.WATER)
        assert tile.blocks_tanks is True
        assert tile.blocks_bullets is False

    def test_defaults_populated_from_tsx(self, game_map):
        """Collision defaults dict is populated by _scan_tileset."""
        defaults = game_map._tile_collision_defaults
        assert TileType.STEEL in defaults
        assert TileType.WATER in defaults
        assert defaults[TileType.STEEL] == (True, True)
        assert defaults[TileType.WATER] == (True, False)


class TestEnemyCompositionFallback:
    """Verify fallback when map has no enemy composition properties."""

    def test_missing_properties_defaults_to_20_basic(self, mock_texture_manager):
        """Map without enemy properties falls back to 20 basic enemies."""
        import os

        # Create a minimal TMX next to the test map so TSX path resolves
        tmx_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.11.2" orientation="orthogonal" \
renderorder="right-down" width="2" height="2" tilewidth="8" tileheight="8" \
infinite="0" nextlayerid="2" nextobjectid="1">
 <tileset firstgid="1" source="../../assets/sprites/sprites.tsx"/>
 <layer id="1" name="Tile Layer 1" width="2" height="2">
  <data encoding="csv">
0,0,
0,0
</data>
 </layer>
</map>
"""
        tmx_path = "tests/assets/no_enemies.tmx"
        with open(tmx_path, "w") as f:
            f.write(tmx_content)
        try:
            game_map = Map(tmx_path, mock_texture_manager)
            assert game_map.enemy_composition == {
                TankType.BASIC: 20,
                TankType.FAST: 0,
                TankType.POWER: 0,
                TankType.ARMOR: 0,
            }
        finally:
            os.remove(tmx_path)


class TestGetBaseSurroundingTiles:
    @pytest.fixture
    def game_map(self, mock_texture_manager):
        return Map(resource_path("assets/maps/level_01.tmx"), mock_texture_manager)

    def test_returns_tiles_around_base(self, game_map):
        tiles = game_map.get_base_surrounding_tiles()
        assert len(tiles) > 0
        base = game_map.get_base()
        assert base is not None

    def test_no_base_tiles_in_result(self, game_map):
        tiles = game_map.get_base_surrounding_tiles()
        for tile in tiles:
            assert tile.type != TileType.BASE

    def test_no_empty_tiles_in_result(self, game_map):
        tiles = game_map.get_base_surrounding_tiles()
        for tile in tiles:
            assert tile.type != TileType.EMPTY
