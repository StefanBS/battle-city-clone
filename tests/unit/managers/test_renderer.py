import pytest
import pygame
from unittest.mock import MagicMock, patch

from src.managers.renderer import Renderer
from src.states.game_state import GameState
from src.utils.constants import Difficulty


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
        patch("src.managers.renderer.resource_path", return_value="fake_font.ttf"),
        patch("pygame.font.Font"),
        patch("pygame.Surface", return_value=MagicMock(spec=pygame.Surface)),
    ):
        return Renderer(mock_screen, 512, 512, 416, 416)


class TestRendererInitialization:
    """Tests for Renderer initialization."""

    def test_initialization(self, mock_screen):
        """Renderer creates game_surface, fonts, and computes map offset."""
        with (
            patch("src.managers.renderer.resource_path", return_value="fake_font.ttf"),
            patch("pygame.font.Font"),
            patch("pygame.Surface"),
        ):
            renderer = Renderer(mock_screen, 512, 512, 416, 416)

        assert renderer.screen is mock_screen
        assert renderer.logical_width == 512
        assert renderer.logical_height == 512
        assert renderer.map_offset_x == (512 - 416) // 2
        assert renderer.map_offset_y == (512 - 416) // 2
        assert renderer.font is not None
        assert renderer.small_font is not None


class TestRendererRender:
    """Tests for the render method."""

    def test_render_calls_draw_methods(self, renderer):
        """Render calls draw methods on map_surface."""
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
            mock_effect_manager = MagicMock()
            renderer.render(
                mock_map,
                [mock_player],
                [mock_enemy1, mock_enemy2],
                [mock_bullet1, mock_bullet2],
                mock_effect_manager,
                GameState.RUNNING,
            )

        mock_map.draw.assert_called_once_with(renderer.map_surface)
        mock_player.draw.assert_called_once_with(renderer.map_surface)
        mock_enemy1.draw.assert_called_once_with(renderer.map_surface)
        mock_enemy2.draw.assert_called_once_with(renderer.map_surface)
        mock_bullet1.draw.assert_called_once_with(renderer.map_surface)
        mock_bullet2.draw.assert_not_called()

    def test_render_victory_overlay(self, renderer):
        """Victory overlay is drawn when state is VICTORY."""
        mock_map = MagicMock()
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = False

        with (
            patch.object(renderer, "_draw_victory") as mock_draw_v,
            patch("pygame.transform.scale") as mock_scale,
            patch("pygame.display.flip"),
        ):
            mock_scale.return_value = MagicMock()
            mock_em = MagicMock()
            renderer.render(mock_map, mock_player, [], [], mock_em, GameState.VICTORY)

        mock_draw_v.assert_called_once()

    def test_render_running_no_overlay(self, renderer):
        """No overlay is drawn when state is RUNNING."""
        mock_map = MagicMock()
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = False

        with (
            patch.object(renderer, "_draw_victory") as mock_draw_v,
            patch("pygame.transform.scale") as mock_scale,
            patch("pygame.display.flip"),
        ):
            mock_scale.return_value = MagicMock()
            mock_em = MagicMock()
            renderer.render(mock_map, mock_player, [], [], mock_em, GameState.RUNNING)

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
            mock_em = MagicMock()
            renderer.render(mock_map, mock_player, [], [], mock_em, GameState.RUNNING)

        mock_scale.assert_called_once_with(
            renderer.game_surface, (1024, 1024), renderer.screen
        )
        mock_flip.assert_called_once()


class TestRendererHUD:
    """Tests for HUD and overlay rendering."""

    def test_hud_does_not_show_invincibility_timer(self, renderer):
        """Test that HUD does not render invincibility text."""
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
            mock_em = MagicMock()
            renderer.render(mock_map, mock_player, [], [], mock_em, GameState.RUNNING)

        # small_font.render: lives + score only (no invincibility)
        assert renderer.small_font.render.call_count == 2

    def test_overlay_screen_renders_title_and_subtitle(self, renderer):
        """Test that _draw_overlay_screen blits overlay, title, and subtitle."""
        mock_overlay = MagicMock(spec=pygame.Surface)
        with patch("pygame.Surface") as mock_surface_cls:
            mock_surface_cls.return_value = mock_overlay
            renderer._draw_overlay_screen("TEST", (255, 0, 0), "subtitle")

        # Should blit: overlay background, title text, subtitle text
        assert renderer.game_surface.blit.call_count >= 3


class TestRenderCurtain:
    @pytest.fixture
    def renderer(self):
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
        screen = pygame.Surface((1024, 1024))
        return Renderer(screen, 512, 512, 416, 416)

    def test_render_curtain_no_crash(self, renderer):
        for progress in [0.0, 0.25, 0.5, 0.75, 1.0]:
            renderer.render_curtain(progress, 1)

    def test_render_curtain_shows_stage_text_when_closed(self, renderer):
        """At progress=1.0, a STAGE N text surface is blitted to game_surface."""
        font_render_calls = []
        real_font_render = renderer.font.render

        class SpyFont:
            """Wraps a real pygame Font to record render calls."""

            def __init__(self, real):
                self._real = real

            def render(self, text, antialias, color):
                font_render_calls.append(text)
                return self._real.render(text, antialias, color)

            def size(self, text):
                return self._real.size(text)

        renderer.font = SpyFont(real_font_render.__self__)

        with patch("pygame.display.flip"):
            renderer.render_curtain(0.0, 3)
            calls_at_open = len(font_render_calls)
            renderer.render_curtain(1.0, 3)
            calls_at_closed = len(font_render_calls)

        # font.render should be called at progress=1.0 but not at 0.0
        assert calls_at_closed > calls_at_open
        assert any("STAGE 3" in c for c in font_render_calls)


class TestRenderPauseMenu:
    """Tests for render_pause_menu."""

    def test_overlay_is_blitted(self, renderer):
        """Pause menu blits the pre-created overlay onto the game surface."""
        with (
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_pause_menu(0)

        # The cached overlay should be blitted onto the game surface
        blit_calls = renderer.game_surface.blit.call_args_list
        assert any(call.args[0] is renderer._pause_overlay for call in blit_calls), (
            "Expected _pause_overlay to be blitted onto game_surface"
        )

    def test_paused_title_is_rendered(self, renderer):
        """Pause menu renders 'PAUSED' title."""
        with (
            patch("pygame.Surface"),
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_pause_menu(0)

        render_calls = [call.args[0] for call in renderer.font.render.call_args_list]
        assert "PAUSED" in render_calls

    def test_four_menu_items_rendered(self, renderer):
        """Pause menu renders RESUME, OPTIONS, TITLE SCREEN, QUIT."""
        with (
            patch("pygame.Surface"),
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_pause_menu(0)

        render_calls = [
            call.args[0] for call in renderer.small_font.render.call_args_list
        ]
        assert "RESUME" in render_calls
        assert "OPTIONS" in render_calls
        assert "TITLE SCREEN" in render_calls
        assert "QUIT" in render_calls

    def test_cursor_is_rendered(self, renderer):
        """Pause menu renders '>' cursor."""
        with (
            patch("pygame.Surface"),
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_pause_menu(0)

        render_calls = [
            call.args[0] for call in renderer.small_font.render.call_args_list
        ]
        assert ">" in render_calls


class TestRenderOptionsMenu:
    """Tests for render_options_menu."""

    def test_options_title_rendered(self, renderer):
        """Options menu renders 'OPTIONS' title."""
        with (
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_options_menu(0.8, Difficulty.NORMAL, 0)

        render_calls = [call.args[0] for call in renderer.font.render.call_args_list]
        assert "OPTIONS" in render_calls

    def test_volume_bar_contains_volume_info(self, renderer):
        """Options menu renders volume bar with percentage."""
        with (
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_options_menu(0.8, Difficulty.NORMAL, 0)

        render_calls = [
            call.args[0] for call in renderer.small_font.render.call_args_list
        ]
        volume_calls = [c for c in render_calls if "VOLUME" in c]
        assert len(volume_calls) == 1
        assert "80%" in volume_calls[0]

    def test_back_is_rendered(self, renderer):
        """Options menu renders 'BACK' option."""
        with (
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_options_menu(0.8, Difficulty.NORMAL, 0)

        render_calls = [
            call.args[0] for call in renderer.small_font.render.call_args_list
        ]
        assert "BACK" in render_calls

    def test_cursor_rendered(self, renderer):
        """Options menu renders '>' cursor."""
        with (
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_options_menu(0.8, Difficulty.NORMAL, 0)

        render_calls = [
            call.args[0] for call in renderer.small_font.render.call_args_list
        ]
        assert ">" in render_calls


class TestTwoPlayerHUD:
    def test_two_player_hud_shows_both_players(self, renderer):
        """2P HUD renders info for both players."""
        p1 = MagicMock()
        p1.lives = 3
        p1.health = 1
        p1.player_id = 1
        p2 = MagicMock()
        p2.lives = 2
        p2.health = 1
        p2.player_id = 2

        renderer.small_font.render.reset_mock()
        renderer._draw_hud([p1, p2], {1: 100, 2: 200})
        rendered_texts = [c[0][0] for c in renderer.small_font.render.call_args_list]
        assert any("P1" in t for t in rendered_texts)
        assert any("P2" in t for t in rendered_texts)

    def test_one_player_hud_no_prefix(self, renderer):
        """1P HUD shows lives/score without P1/P2 prefix."""
        p1 = MagicMock()
        p1.lives = 3
        p1.health = 1
        p1.player_id = 1

        renderer.small_font.render.reset_mock()
        renderer._draw_hud([p1], {1: 100})
        rendered_texts = [c[0][0] for c in renderer.small_font.render.call_args_list]
        assert not any("P1" in t for t in rendered_texts)

    def test_eliminated_player_shows_out(self, renderer):
        """Eliminated player shows 'OUT'."""
        p1 = MagicMock()
        p1.lives = 3
        p1.health = 1
        p1.player_id = 1
        p2 = MagicMock()
        p2.lives = 0
        p2.health = 0
        p2.player_id = 2

        renderer.small_font.render.reset_mock()
        renderer._draw_hud([p1, p2], {1: 100, 2: 50})
        rendered_texts = [c[0][0] for c in renderer.small_font.render.call_args_list]
        assert any("OUT" in t for t in rendered_texts)


class TestRenderTitleScreenUpdated:
    """Tests for updated title screen with OPTIONS and QUIT."""

    def test_menu_items_rendered(self, renderer):
        """Title screen renders 1 PLAYER, 2 PLAYERS, OPTIONS, QUIT."""
        with (
            patch("pygame.transform.scale"),
            patch("pygame.display.flip"),
        ):
            renderer.render_title_screen(0)

        render_calls = [
            call.args[0] for call in renderer.small_font.render.call_args_list
        ]
        assert "1 PLAYER" in render_calls
        assert "2 PLAYERS" in render_calls
        assert "OPTIONS" in render_calls
        assert "QUIT" in render_calls
