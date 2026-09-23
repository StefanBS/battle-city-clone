import pytest
import pygame
from unittest.mock import MagicMock
from src.core.tile import Tile, TileType
from src.managers.texture_manager import TextureManager
from src.utils.constants import SUB_TILE_SIZE


class TestTileAnimation:
    """Tests for Tile animation logic."""

    def test_tile_not_animated_until_frames_set(self):
        tile = Tile(TileType.WATER, 0, 0)
        assert not tile.is_animated
        assert not tile.update(1.0)


class TestTileNativeAnimation:
    """Tests for Tile animation driven by frame data (Tiled native)."""

    @pytest.fixture
    def animated_tile(self):
        """Create a tile with 3 animation frames at 500ms each."""
        frame1 = MagicMock(spec=pygame.Surface)
        frame2 = MagicMock(spec=pygame.Surface)
        frame3 = MagicMock(spec=pygame.Surface)
        frames = [
            (frame1, 0.5),
            (frame2, 0.5),
            (frame3, 0.5),
        ]
        tile = Tile(TileType.WATER, 0, 0)
        tile.set_animation_frames(frames)
        return tile

    def test_initial_frame_index_zero(self, animated_tile):
        assert animated_tile.current_frame_index == 0

    def test_update_before_duration_stays(self, animated_tile):
        animated_tile.update(0.3)
        assert animated_tile.current_frame_index == 0

    def test_update_at_duration_advances(self, animated_tile):
        animated_tile.update(0.5)
        assert animated_tile.current_frame_index == 1

    def test_update_wraps_around(self, animated_tile):
        animated_tile.update(0.5)
        animated_tile.update(0.5)
        animated_tile.update(0.5)
        assert animated_tile.current_frame_index == 0

    def test_per_frame_duration(self):
        """Frames can have different durations."""
        frame1 = MagicMock(spec=pygame.Surface)
        frame2 = MagicMock(spec=pygame.Surface)
        tile = Tile(TileType.WATER, 0, 0)
        tile.set_animation_frames([(frame1, 0.3), (frame2, 0.7)])
        tile.update(0.3)
        assert tile.current_frame_index == 1
        tile.update(0.6)
        assert tile.current_frame_index == 1  # not yet at 0.7
        tile.update(0.1)
        assert tile.current_frame_index == 0  # wrapped


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

    def test_draw_animated_tile_uses_animation_sprites(self, mock_surface, mock_tm):
        """Animated tile uses animation_sprites for drawing."""
        frame1 = MagicMock(spec=pygame.Surface)
        frame2 = MagicMock(spec=pygame.Surface)
        tile = Tile(TileType.WATER, 0, 0)
        tile.set_animation_frames([(frame1, 0.5), (frame2, 0.5)])
        tile.draw(mock_surface, mock_tm)
        mock_surface.blit.assert_called_once_with(frame1, (0, 0))

    def test_draw_animated_tile_second_frame(self, mock_surface, mock_tm):
        """Animated tile after frame advance uses next sprite."""
        frame1 = MagicMock(spec=pygame.Surface)
        frame2 = MagicMock(spec=pygame.Surface)
        tile = Tile(TileType.WATER, 0, 0)
        tile.set_animation_frames([(frame1, 0.5), (frame2, 0.5)])
        tile.update(0.5)
        tile.draw(mock_surface, mock_tm)
        mock_surface.blit.assert_called_once_with(frame2, (0, 0))

    def test_draw_with_tmx_sprite(self, mock_surface, mock_tm):
        """Tile with TMX sprite uses it directly."""
        tmx_sprite = MagicMock(spec=pygame.Surface)
        tile = Tile(TileType.BRICK, 2, 3, tmx_sprite=tmx_sprite)
        tile.draw(mock_surface, mock_tm)
        expected_pos = (2 * SUB_TILE_SIZE, 3 * SUB_TILE_SIZE)
        mock_surface.blit.assert_called_once_with(tmx_sprite, expected_pos)

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


class TestTileRuleFlags:
    """Tests for the rule flags a Tile is built with."""

    def test_flags_default_false(self):
        tile = Tile(TileType.EMPTY, 0, 0)
        assert not tile.blocks_tanks
        assert not tile.blocks_bullets
        assert not tile.is_destructible
        assert not tile.is_overlay
        assert not tile.is_slidable

    def test_flags_set_from_constructor(self):
        """Each keyword lands on its own flag (mixed values catch swaps)."""
        tile = Tile(
            TileType.BRICK,
            0,
            0,
            blocks_tanks=True,
            blocks_bullets=False,
            is_destructible=True,
            is_overlay=False,
            is_slidable=True,
        )
        assert tile.blocks_tanks
        assert not tile.blocks_bullets
        assert tile.is_destructible
        assert not tile.is_overlay
        assert tile.is_slidable
