import pytest
import pygame
from unittest.mock import MagicMock
from src.core.tile import Tile, TileType
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    TILE_ANIMATION_INTERVAL,
    SUB_TILE_SIZE,
)


class TestTileAnimation:
    """Tests for Tile animation logic."""

    @pytest.fixture
    def water_tile(self):
        return Tile(TileType.WATER, 0, 0)

    @pytest.fixture
    def brick_tile(self):
        return Tile(TileType.BRICK, 0, 0)

    def test_water_tile_is_animated(self, water_tile):
        assert water_tile.is_animated
        assert water_tile.animation_frames == ["water_1", "water_2"]
        assert water_tile.current_frame_index == 0

    def test_brick_tile_is_not_animated(self, brick_tile):
        assert not brick_tile.is_animated
        assert brick_tile.animation_frames == []

    def test_update_non_animated_returns_false(self, brick_tile):
        assert not brick_tile.update(1.0)

    def test_update_before_interval_returns_false(self, water_tile):
        assert not water_tile.update(TILE_ANIMATION_INTERVAL * 0.5)
        assert water_tile.current_frame_index == 0

    def test_update_at_interval_cycles_frame(self, water_tile):
        result = water_tile.update(TILE_ANIMATION_INTERVAL)
        assert result is True
        assert water_tile.current_frame_index == 1

    def test_update_wraps_frame_index(self, water_tile):
        water_tile.update(TILE_ANIMATION_INTERVAL)
        water_tile.update(TILE_ANIMATION_INTERVAL)
        assert water_tile.current_frame_index == 0


class TestTileDraw:
    """Tests for Tile.draw() method."""

    @pytest.fixture
    def mock_tm(self):
        mock = MagicMock(spec=TextureManager)
        mock.get_sub_sprite.return_value = MagicMock(spec=pygame.Surface)
        return mock

    @pytest.fixture
    def mock_surface(self):
        return MagicMock(spec=pygame.Surface)

    def test_draw_animated_tile(self, mock_surface, mock_tm):
        """Animated tile uses current frame sub-sprite."""
        tile = Tile(TileType.WATER, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sub_sprite.assert_called_once_with("water_1")
        mock_surface.blit.assert_called_once()

    def test_draw_animated_tile_second_frame(self, mock_surface, mock_tm):
        """Animated tile after frame advance uses next sub-sprite."""
        tile = Tile(TileType.WATER, 0, 0)
        tile.update(TILE_ANIMATION_INTERVAL)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sub_sprite.assert_called_once_with("water_2")

    def test_draw_with_tmx_sprite(self, mock_surface, mock_tm):
        """Tile with TMX sprite uses it directly."""
        tmx_sprite = MagicMock(spec=pygame.Surface)
        tile = Tile(TileType.BRICK, 2, 3, tmx_sprite=tmx_sprite)
        tile.draw(mock_surface, mock_tm)
        expected_pos = (2 * SUB_TILE_SIZE, 3 * SUB_TILE_SIZE)
        mock_surface.blit.assert_called_once_with(tmx_sprite, expected_pos)

    def test_draw_fallback_uses_type_sprite(self, mock_surface, mock_tm):
        """Tile without TMX sprite falls back to type-based sub-sprite."""
        tile = Tile(TileType.BRICK, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sub_sprite.assert_called_once_with("brick")
        mock_surface.blit.assert_called_once()

    def test_draw_empty_tile_no_blit(self, mock_surface, mock_tm):
        """EMPTY tile does not blit."""
        tile = Tile(TileType.EMPTY, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sub_sprite.assert_not_called()
        mock_surface.blit.assert_not_called()

    def test_tile_rect_position(self):
        """Tile rect is at grid position * tile_size."""
        tile = Tile(TileType.BRICK, 3, 5)
        assert tile.rect == pygame.Rect(
            3 * SUB_TILE_SIZE, 5 * SUB_TILE_SIZE, SUB_TILE_SIZE, SUB_TILE_SIZE
        )


class TestTileCollisionProperties:
    """Tests for Tile blocks_tanks and blocks_bullets attributes."""

    def test_default_blocks_tanks_false(self):
        tile = Tile(TileType.EMPTY, 0, 0)
        assert tile.blocks_tanks is False

    def test_default_blocks_bullets_false(self):
        tile = Tile(TileType.EMPTY, 0, 0)
        assert tile.blocks_bullets is False

    def test_blocks_tanks_set_from_constructor(self):
        tile = Tile(TileType.BRICK, 0, 0, blocks_tanks=True, blocks_bullets=True)
        assert tile.blocks_tanks is True

    def test_blocks_bullets_set_from_constructor(self):
        tile = Tile(TileType.WATER, 0, 0, blocks_tanks=True, blocks_bullets=False)
        assert tile.blocks_bullets is False
