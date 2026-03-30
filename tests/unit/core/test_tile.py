import pytest
import pygame
from unittest.mock import MagicMock
from src.core.tile import Tile, TileType
from src.managers.texture_manager import TextureManager
from src.utils.constants import TILE_ANIMATION_INTERVAL


class TestTileAnimation:
    """Tests for Tile animation logic."""

    @pytest.fixture
    def water_tile(self):
        """Create a water tile (animated) for testing."""
        return Tile(TileType.WATER, 0, 0)

    @pytest.fixture
    def brick_tile(self):
        """Create a brick tile (not animated) for testing."""
        return Tile(TileType.BRICK, 0, 0)

    def test_water_tile_is_animated(self, water_tile):
        """Test that water tiles are initialized as animated."""
        assert water_tile.is_animated
        assert water_tile.animation_frames == ["water_1", "water_2"]
        assert water_tile.current_frame_index == 0

    def test_brick_tile_is_not_animated(self, brick_tile):
        """Test that non-water tiles are not animated."""
        assert not brick_tile.is_animated
        assert brick_tile.animation_frames == []

    def test_update_non_animated_returns_false(self, brick_tile):
        """Test that update() on non-animated tile returns False."""
        assert not brick_tile.update(1.0)

    def test_update_before_interval_returns_false(self, water_tile):
        """Test that update returns False before animation interval."""
        assert not water_tile.update(TILE_ANIMATION_INTERVAL * 0.5)
        assert water_tile.current_frame_index == 0

    def test_update_at_interval_cycles_frame(self, water_tile):
        """Test that update cycles frame index at animation interval."""
        result = water_tile.update(TILE_ANIMATION_INTERVAL)
        assert result is True
        assert water_tile.current_frame_index == 1

    def test_update_wraps_frame_index(self, water_tile):
        """Test that frame index wraps back to 0."""
        water_tile.update(TILE_ANIMATION_INTERVAL)  # frame 0 -> 1
        water_tile.update(TILE_ANIMATION_INTERVAL)  # frame 1 -> 0
        assert water_tile.current_frame_index == 0


class TestTileDraw:
    """Tests for Tile.draw() method."""

    @pytest.fixture
    def mock_tm(self):
        mock = MagicMock(spec=TextureManager)
        mock.get_sprite.return_value = MagicMock(spec=pygame.Surface)
        return mock

    @pytest.fixture
    def mock_surface(self):
        return MagicMock(spec=pygame.Surface)

    def test_draw_animated_tile(self, mock_surface, mock_tm):
        """Test that animated tile uses current frame sprite name."""
        tile = Tile(TileType.WATER, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sprite.assert_called_once_with("water_1")
        mock_surface.blit.assert_called_once()

    def test_draw_animated_tile_second_frame(self, mock_surface, mock_tm):
        """Test animated tile after frame advance uses next sprite."""
        tile = Tile(TileType.WATER, 0, 0)
        tile.update(TILE_ANIMATION_INTERVAL)  # advance to frame 1
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sprite.assert_called_once_with("water_2")

    def test_draw_static_tile(self, mock_surface, mock_tm):
        """Test that static tile uses SPRITE_NAME_MAP lookup."""
        tile = Tile(TileType.BRICK, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sprite.assert_called_once_with("brick")
        mock_surface.blit.assert_called_once()

    def test_draw_empty_tile_no_blit(self, mock_surface, mock_tm):
        """Test that EMPTY tile does not blit (sprite_name is None)."""
        tile = Tile(TileType.EMPTY, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sprite.assert_not_called()
        mock_surface.blit.assert_not_called()
