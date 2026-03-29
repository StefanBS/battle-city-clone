import pytest
from src.core.map import Map
from src.core.tile import TileType

TEST_MAP_PATH = "tests/assets/test_map.tmx"


@pytest.fixture
def game_map(mock_texture_manager):
    return Map(TEST_MAP_PATH, mock_texture_manager)


class TestMapLoading:
    """Tests for TMX-based map loading."""

    def test_map_dimensions(self, game_map):
        """Test that map dimensions come from the TMX file."""
        assert game_map.width == 5
        assert game_map.height == 5

    def test_tiles_populated(self, game_map):
        """Test that all positions have Tile objects."""
        for y in range(game_map.height):
            for x in range(game_map.width):
                tile = game_map.get_tile_at(x, y)
                assert tile is not None, f"Tile at ({x}, {y}) is None"

    def test_tile_types_from_tmx(self, game_map):
        """Test that specific tiles have correct types from TMX tile_type property."""
        # Based on test_map.tmx layout:
        # Row 0: STEEL, EMPTY, EMPTY, EMPTY, STEEL
        # Row 1: EMPTY, BRICK, EMPTY, BRICK, EMPTY
        # Row 2: EMPTY, EMPTY, WATER, EMPTY, EMPTY
        # Row 3: EMPTY, EMPTY, EMPTY, EMPTY, EMPTY
        # Row 4: EMPTY, EMPTY, BASE,  EMPTY, EMPTY
        assert game_map.get_tile_at(0, 0).type == TileType.STEEL
        assert game_map.get_tile_at(4, 0).type == TileType.STEEL
        assert game_map.get_tile_at(1, 1).type == TileType.BRICK
        assert game_map.get_tile_at(3, 1).type == TileType.BRICK
        assert game_map.get_tile_at(2, 2).type == TileType.WATER
        assert game_map.get_tile_at(2, 4).type == TileType.BASE
        # Check some EMPTY tiles
        assert game_map.get_tile_at(1, 0).type == TileType.EMPTY
        assert game_map.get_tile_at(2, 3).type == TileType.EMPTY

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
        # So grid coords: (32//16, 48//16) = (2, 3)
        assert game_map.player_spawn == (2, 3)
