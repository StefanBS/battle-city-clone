import pytest
from src.core.map import Map
from src.core.tile import TileType
from src.utils.paths import resource_path

TEST_MAP_PATH = "tests/assets/test_map.tmx"


@pytest.fixture
def game_map(mock_texture_manager):
    return Map(TEST_MAP_PATH, mock_texture_manager)


class TestMapLoading:
    """Tests for TMX-based map loading.

    The test TMX is 5x5 tiles. With 2x sub-tile expansion, the internal
    grid is 10x10. Each TMX tile at (x, y) maps to sub-tiles at
    (2x, 2y), (2x+1, 2y), (2x, 2y+1), (2x+1, 2y+1).
    """

    def test_map_dimensions(self, game_map):
        """Test that map dimensions are 2x the TMX file (sub-tile expansion)."""
        assert game_map.width == 10  # 5 * 2
        assert game_map.height == 10  # 5 * 2

    def test_tiles_populated(self, game_map):
        """Test that all positions have Tile objects."""
        for y in range(game_map.height):
            for x in range(game_map.width):
                tile = game_map.get_tile_at(x, y)
                assert tile is not None, f"Tile at ({x}, {y}) is None"

    def test_tile_types_from_tmx(self, game_map):
        """Test that specific tiles have correct types from TMX tile_type property.

        Original TMX layout (5x5):
        Row 0: STEEL, EMPTY, EMPTY, EMPTY, STEEL
        Row 1: EMPTY, BRICK, EMPTY, BRICK, EMPTY
        Row 2: EMPTY, EMPTY, WATER, EMPTY, EMPTY
        Row 3: EMPTY, EMPTY, EMPTY, EMPTY, EMPTY
        Row 4: EMPTY, EMPTY, BASE,  EMPTY, EMPTY

        Sub-tile coords are 2x the TMX coords.
        """
        # STEEL at TMX (0,0) → sub-tile (0,0)
        assert game_map.get_tile_at(0, 0).type == TileType.STEEL
        # STEEL at TMX (4,0) → sub-tile (8,0)
        assert game_map.get_tile_at(8, 0).type == TileType.STEEL
        # BRICK at TMX (1,1) → sub-tile (2,2)
        assert game_map.get_tile_at(2, 2).type == TileType.BRICK
        # BRICK at TMX (3,1) → sub-tile (6,2)
        assert game_map.get_tile_at(6, 2).type == TileType.BRICK
        # WATER at TMX (2,2) → sub-tile (4,4)
        assert game_map.get_tile_at(4, 4).type == TileType.WATER
        # BASE at TMX (2,4) → sub-tile (4,8)
        assert game_map.get_tile_at(4, 8).type == TileType.BASE
        # Check some EMPTY tiles: TMX (1,0) → sub-tile (2,0)
        assert game_map.get_tile_at(2, 0).type == TileType.EMPTY
        # TMX (2,3) → sub-tile (4,6)
        assert game_map.get_tile_at(4, 6).type == TileType.EMPTY

    def test_spawn_points_from_tmx(self, game_map):
        """Test that spawn points are read from TMX object layer."""
        assert len(game_map.spawn_points) >= 1
        for point in game_map.spawn_points:
            assert isinstance(point, tuple)
            assert len(point) == 2

    def test_player_spawn_from_tmx(self, game_map):
        """Test that player spawn is read from TMX object layer."""
        assert isinstance(game_map.player_spawn, tuple)
        assert len(game_map.player_spawn) == 2
        # player_spawn is at pixel (32, 48), TMX tilewidth=16
        # TMX grid coords: (32//16, 48//16) = (2, 3)
        # Sub-tile coords: (2*2, 3*2) = (4, 6)
        assert game_map.player_spawn == (4, 6)

    def test_brick_subtiles_are_independent(self, game_map):
        """Test that each brick sub-tile can be destroyed independently."""
        # BRICK at TMX (1,1) → 4 sub-tiles at (2,2), (3,2), (2,3), (3,3)
        for sx, sy in [(2, 2), (3, 2), (2, 3), (3, 3)]:
            tile = game_map.get_tile_at(sx, sy)
            assert tile.type == TileType.BRICK

        # Destroy just one sub-tile
        tile_to_destroy = game_map.get_tile_at(2, 2)
        game_map.set_tile_type(tile_to_destroy, TileType.EMPTY)

        # That sub-tile is EMPTY, siblings remain BRICK
        assert game_map.get_tile_at(2, 2).type == TileType.EMPTY
        assert game_map.get_tile_at(3, 2).type == TileType.BRICK
        assert game_map.get_tile_at(2, 3).type == TileType.BRICK
        assert game_map.get_tile_at(3, 3).type == TileType.BRICK

    def test_base_group_destruction(self, game_map):
        """Test that destroying any base sub-tile destroys the whole group."""
        # BASE at TMX (2,4) → sub-tiles at (4,8), (5,8), (4,9), (5,9)
        for sx, sy in [(4, 8), (5, 8), (4, 9), (5, 9)]:
            assert game_map.get_tile_at(sx, sy).type == TileType.BASE

        # Destroy via any sub-tile
        any_base_tile = game_map.get_tile_at(5, 9)
        game_map.destroy_base_group(any_base_tile)

        # All 4 should be BASE_DESTROYED
        for sx, sy in [(4, 8), (5, 8), (4, 9), (5, 9)]:
            assert game_map.get_tile_at(sx, sy).type == TileType.BASE_DESTROYED


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
