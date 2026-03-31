import pytest
import pygame
from unittest.mock import MagicMock
from src.core.tile import Tile, TileType
from src.managers.texture_manager import TextureManager
from src.utils.constants import (
    TILE_ANIMATION_INTERVAL,
    SEGMENT_TOP_LEFT,
    SEGMENT_TOP_RIGHT,
    SEGMENT_BOTTOM_RIGHT,
    SEGMENT_LEFT,
    SEGMENT_RIGHT,
    SEGMENT_TOP,
    SEGMENT_BOTTOM,
    SEGMENT_FULL,
    BRICK_SEGMENT_SIZE,
    SUB_TILE_SIZE,
)


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
        mock.get_sub_sprite.return_value = MagicMock(spec=pygame.Surface)
        return mock

    @pytest.fixture
    def mock_surface(self):
        return MagicMock(spec=pygame.Surface)

    def test_draw_animated_tile(self, mock_surface, mock_tm):
        """Test that animated tile uses current frame sub-sprite."""
        tile = Tile(TileType.WATER, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sub_sprite.assert_called_once_with("water_1")
        mock_surface.blit.assert_called_once()

    def test_draw_animated_tile_second_frame(self, mock_surface, mock_tm):
        """Test animated tile after frame advance uses next sub-sprite."""
        tile = Tile(TileType.WATER, 0, 0)
        tile.update(TILE_ANIMATION_INTERVAL)  # advance to frame 1
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sub_sprite.assert_called_once_with("water_2")

    def test_draw_static_tile(self, mock_surface, mock_tm):
        """Test that static tile uses SPRITE_NAME_MAP lookup via sub-sprite."""
        tile = Tile(TileType.BRICK, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sub_sprite.assert_called_once_with("brick")
        mock_surface.blit.assert_called_once()

    def test_draw_base_primary_uses_full_sprite(self, mock_surface, mock_tm):
        """Test that base primary sub-tile uses full-size sprite."""
        tile = Tile(TileType.BASE, 0, 0, is_group_primary=True)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sprite.assert_called_once_with("base")
        mock_surface.blit.assert_called_once()

    def test_draw_base_non_primary_does_nothing(self, mock_surface, mock_tm):
        """Test that non-primary base sub-tile does not render."""
        tile = Tile(TileType.BASE, 1, 0, is_group_primary=False)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sprite.assert_not_called()
        mock_tm.get_sub_sprite.assert_not_called()
        mock_surface.blit.assert_not_called()

    def test_draw_empty_tile_no_blit(self, mock_surface, mock_tm):
        """Test that EMPTY tile does not blit (sprite_name is None)."""
        tile = Tile(TileType.EMPTY, 0, 0)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sprite.assert_not_called()
        mock_tm.get_sub_sprite.assert_not_called()
        mock_surface.blit.assert_not_called()

    def test_draw_partial_brick_one_quadrant(self, mock_surface, mock_tm):
        """Brick with one quadrant removed draws remaining three quadrants."""
        tile = Tile(TileType.BRICK, 2, 3)
        tile.remove_brick_segment(SEGMENT_TOP_RIGHT)
        tile.draw(mock_surface, mock_tm)
        mock_tm.get_sub_sprite.assert_called_once_with("brick")
        # Should blit 3 remaining quadrants
        assert mock_surface.blit.call_count == 3

    def test_draw_partial_brick_quadrant_source_rects(self, mock_surface, mock_tm):
        """Each remaining quadrant blits the correct 8x8 source region."""
        tile = Tile(TileType.BRICK, 0, 0)
        # Remove top row, keep only bottom row
        tile.remove_brick_segment(SEGMENT_TOP)
        tile.draw(mock_surface, mock_tm)
        calls = mock_surface.blit.call_args_list
        source_rects = [tuple(c[0][2]) for c in calls]
        h = BRICK_SEGMENT_SIZE
        w = BRICK_SEGMENT_SIZE
        bl = tuple(pygame.Rect(0, h, w, h))
        br = tuple(pygame.Rect(w, h, w, h))
        assert bl in source_rects
        assert br in source_rects


class TestBrickSegments:
    """Tests for brick quadrant tracking and rect updates."""

    def test_new_brick_has_full_segments(self):
        tile = Tile(TileType.BRICK, 0, 0)
        assert tile.brick_segments == SEGMENT_FULL

    def test_non_brick_has_no_segments(self):
        tile = Tile(TileType.STEEL, 0, 0)
        assert tile.brick_segments == 0

    def test_remove_left_column_updates_rect(self):
        tile = Tile(TileType.BRICK, 4, 4)  # px: (64, 64, 16, 16)
        tile.remove_brick_segment(SEGMENT_LEFT)
        assert tile.brick_segments == SEGMENT_RIGHT
        assert tile.rect == pygame.Rect(
            4 * SUB_TILE_SIZE + BRICK_SEGMENT_SIZE,
            4 * SUB_TILE_SIZE,
            BRICK_SEGMENT_SIZE,
            SUB_TILE_SIZE,
        )

    def test_remove_top_row_updates_rect(self):
        tile = Tile(TileType.BRICK, 4, 4)
        tile.remove_brick_segment(SEGMENT_TOP)
        assert tile.brick_segments == SEGMENT_BOTTOM
        assert tile.rect == pygame.Rect(
            4 * SUB_TILE_SIZE,
            4 * SUB_TILE_SIZE + BRICK_SEGMENT_SIZE,
            SUB_TILE_SIZE,
            BRICK_SEGMENT_SIZE,
        )

    def test_remove_single_quadrant_updates_rect(self):
        tile = Tile(TileType.BRICK, 4, 4)
        tile.remove_brick_segment(SEGMENT_BOTTOM_RIGHT)
        assert tile.brick_segments == (SEGMENT_FULL & ~SEGMENT_BOTTOM_RIGHT)
        # Bounding box still covers full sub-tile (3 of 4 corners occupied)
        assert tile.rect == pygame.Rect(
            4 * SUB_TILE_SIZE, 4 * SUB_TILE_SIZE, SUB_TILE_SIZE, SUB_TILE_SIZE
        )

    def test_remove_all_segments_zeroes_bitmask(self):
        tile = Tile(TileType.BRICK, 0, 0)
        tile.remove_brick_segment(SEGMENT_FULL)
        assert tile.brick_segments == 0

    def test_get_segment_rect_top_left(self):
        tile = Tile(TileType.BRICK, 4, 4)
        rect = tile.get_segment_rect(SEGMENT_TOP_LEFT)
        assert rect == pygame.Rect(64, 64, BRICK_SEGMENT_SIZE, BRICK_SEGMENT_SIZE)

    def test_get_segment_rect_bottom_right(self):
        tile = Tile(TileType.BRICK, 4, 4)
        rect = tile.get_segment_rect(SEGMENT_BOTTOM_RIGHT)
        assert rect == pygame.Rect(
            64 + BRICK_SEGMENT_SIZE,
            64 + BRICK_SEGMENT_SIZE,
            BRICK_SEGMENT_SIZE,
            BRICK_SEGMENT_SIZE,
        )
