import pytest
import pygame
from unittest.mock import MagicMock, patch

from src.managers.renderer import Renderer
from src.states.game_state import GameState


@pytest.fixture
def mock_screen():
    """Create a mock screen surface."""
    screen = MagicMock(spec=pygame.Surface)
    screen.get_width.return_value = 1024
    screen.get_height.return_value = 1024
    return screen


@pytest.fixture
def renderer(mock_screen):
    """Create a Renderer instance with mocked pygame fonts and surface."""
    with (
        patch("pygame.font.SysFont"),
        patch("pygame.Surface", return_value=MagicMock(spec=pygame.Surface)),
    ):
        return Renderer(mock_screen, 512, 512)


class TestRendererInitialization:
    """Tests for Renderer initialization."""

    def test_initialization(self, mock_screen):
        """Renderer creates game_surface, fonts, and background_color."""
        with patch("pygame.font.SysFont"), patch("pygame.Surface") as mock_surface_cls:
            renderer = Renderer(mock_screen, 512, 512)

        assert renderer.screen is mock_screen
        assert renderer.logical_width == 512
        assert renderer.logical_height == 512
        assert mock_surface_cls.call_count == 2
        mock_surface_cls.assert_any_call((512, 512))
        mock_surface_cls.assert_any_call((1024, 1024))
        assert renderer.background_color == (0, 0, 0)
        assert renderer.font is not None
        assert renderer.small_font is not None


class TestRendererRender:
    """Tests for the render method."""

    def test_render_calls_draw_methods(self, renderer):
        """Render calls map.draw, player.draw, enemy.draw, bullet.draw."""
        mock_map = MagicMock()
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = False

        mock_enemy1 = MagicMock()
        mock_enemy2 = MagicMock()

        mock_bullet1 = MagicMock()
        mock_bullet1.active = True
        mock_bullet2 = MagicMock()
        mock_bullet2.active = False

        with (
            patch("pygame.transform.scale") as mock_scale,
            patch("pygame.display.flip"),
        ):
            mock_scale.return_value = MagicMock()
            renderer.render(
                mock_map,
                mock_player,
                [mock_enemy1, mock_enemy2],
                [mock_bullet1, mock_bullet2],
                GameState.RUNNING,
            )

        mock_map.draw.assert_called_once_with(renderer.game_surface)
        mock_player.draw.assert_called_once_with(renderer.game_surface)
        mock_enemy1.draw.assert_called_once_with(renderer.game_surface)
        mock_enemy2.draw.assert_called_once_with(renderer.game_surface)
        mock_bullet1.draw.assert_called_once_with(renderer.game_surface)
        mock_bullet2.draw.assert_not_called()

    def test_render_game_over_overlay(self, renderer):
        """Game over overlay is drawn when state is GAME_OVER."""
        mock_map = MagicMock()
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = False

        with (
            patch.object(renderer, "_draw_game_over") as mock_draw_go,
            patch.object(renderer, "_draw_victory") as mock_draw_v,
            patch("pygame.transform.scale") as mock_scale,
            patch("pygame.display.flip"),
        ):
            mock_scale.return_value = MagicMock()
            renderer.render(mock_map, mock_player, [], [], GameState.GAME_OVER)

        mock_draw_go.assert_called_once()
        mock_draw_v.assert_not_called()

    def test_render_victory_overlay(self, renderer):
        """Victory overlay is drawn when state is VICTORY."""
        mock_map = MagicMock()
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = False

        with (
            patch.object(renderer, "_draw_game_over") as mock_draw_go,
            patch.object(renderer, "_draw_victory") as mock_draw_v,
            patch("pygame.transform.scale") as mock_scale,
            patch("pygame.display.flip"),
        ):
            mock_scale.return_value = MagicMock()
            renderer.render(mock_map, mock_player, [], [], GameState.VICTORY)

        mock_draw_v.assert_called_once()
        mock_draw_go.assert_not_called()

    def test_render_running_no_overlay(self, renderer):
        """No overlay is drawn when state is RUNNING."""
        mock_map = MagicMock()
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = False

        with (
            patch.object(renderer, "_draw_game_over") as mock_draw_go,
            patch.object(renderer, "_draw_victory") as mock_draw_v,
            patch("pygame.transform.scale") as mock_scale,
            patch("pygame.display.flip"),
        ):
            mock_scale.return_value = MagicMock()
            renderer.render(mock_map, mock_player, [], [], GameState.RUNNING)

        mock_draw_go.assert_not_called()
        mock_draw_v.assert_not_called()

    def test_render_scales_and_flips(self, renderer):
        """Render scales game_surface to screen and flips display."""
        mock_map = MagicMock()
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = False
        mock_scaled = MagicMock()

        with (
            patch("pygame.transform.scale") as mock_scale,
            patch("pygame.display.flip") as mock_flip,
        ):
            mock_scale.return_value = mock_scaled
            renderer.render(mock_map, mock_player, [], [], GameState.RUNNING)

        mock_scale.assert_called_once_with(
            renderer.game_surface, (1024, 1024), renderer._scaled_surface
        )
        renderer.screen.blit.assert_called_once_with(renderer._scaled_surface, (0, 0))
        mock_flip.assert_called_once()


class TestRendererHUD:
    """Tests for HUD and overlay rendering."""

    def test_hud_shows_invincibility_timer(self, renderer):
        """Test that HUD renders invincibility text when player is invincible."""
        mock_map = MagicMock()
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = True
        mock_player.invincibility_duration = 3.0
        mock_player.invincibility_timer = 1.0

        with (
            patch("pygame.transform.scale") as mock_scale,
            patch("pygame.display.flip"),
        ):
            mock_scale.return_value = MagicMock()
            renderer.render(
                mock_map, mock_player, [], [], GameState.RUNNING
            )

        # small_font.render should be called twice: lives + invincibility
        assert renderer.small_font.render.call_count == 2

    def test_overlay_screen_renders_title_and_subtitle(self, renderer):
        """Test that _draw_overlay_screen blits overlay, title, and subtitle."""
        mock_overlay = MagicMock(spec=pygame.Surface)
        with patch("pygame.Surface") as mock_surface_cls:
            mock_surface_cls.return_value = mock_overlay
            renderer._draw_overlay_screen("TEST", (255, 0, 0), "subtitle")

        # Should blit: overlay background, title text, subtitle text
        assert renderer.game_surface.blit.call_count >= 3
