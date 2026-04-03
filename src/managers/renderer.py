import pygame
from typing import List, Tuple
from src.states.game_state import GameState
from src.utils.constants import WHITE, YELLOW, BLACK, RED, GREEN, GRAY
from src.utils.paths import resource_path


class Renderer:
    """Handles all rendering logic for the game.

    Manages the logical game surface, fonts, HUD, and overlay screens.
    The map is drawn centered on a fixed-size logical surface with a
    gray border, matching the original NES Battle City style.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        logical_width: int,
        logical_height: int,
        map_width_px: int,
        map_height_px: int,
    ) -> None:
        """Initialize the renderer.

        Args:
            screen: The main display surface (window).
            logical_width: Width of the logical game surface in pixels.
            logical_height: Height of the logical game surface in pixels.
            map_width_px: Width of the map in pixels.
            map_height_px: Height of the map in pixels.
        """
        self.screen = screen
        self.logical_width = logical_width
        self.logical_height = logical_height
        self.game_surface: pygame.Surface = pygame.Surface(
            (logical_width, logical_height)
        )
        self.border_color: Tuple[int, int, int] = GRAY
        self.background_color: Tuple[int, int, int] = BLACK
        font_path = resource_path("assets/fonts/PressStart2P-Regular.ttf")
        self.font: pygame.font.Font = pygame.font.Font(font_path, 24)
        self.small_font: pygame.font.Font = pygame.font.Font(font_path, 12)
        self._scaled_surface: pygame.Surface = pygame.Surface(
            (screen.get_width(), screen.get_height())
        )

        # Map offset: center the map on the logical surface
        self.map_offset_x: int = (logical_width - map_width_px) // 2
        self.map_offset_y: int = (logical_height - map_height_px) // 2

        # Map area surface for rendering entities at map-relative positions
        self.map_surface: pygame.Surface = pygame.Surface((map_width_px, map_height_px))

    def render(
        self,
        game_map,
        player_tank,
        enemy_tanks: List,
        bullets: List,
        effect_manager,
        state: GameState,
        score: int = 0,
        power_up=None,  # Optional[PowerUp]
    ) -> None:
        """Render the complete game frame.

        Args:
            game_map: The game map to draw.
            player_tank: The player's tank.
            enemy_tanks: List of enemy tanks.
            bullets: List of bullets.
            state: Current game state.
            score: Current player score.
            power_up: Optional active power-up to draw.
        """
        # Fill logical surface with border color (gray)
        self.game_surface.fill(self.border_color)

        # Clear the map area with black background
        self.map_surface.fill(self.background_color)

        # Draw the map onto the map surface
        game_map.draw(self.map_surface)

        # Draw the player tank onto the map surface
        player_tank.draw(self.map_surface)

        # Draw enemy tanks onto the map surface
        for enemy in enemy_tanks:
            enemy.draw(self.map_surface)

        # Draw power-up
        if power_up:
            power_up.draw(self.map_surface)

        # Draw all bullets
        for bullet in bullets:
            if bullet.active:
                bullet.draw(self.map_surface)

        effect_manager.draw(self.map_surface)

        # Blit the map surface onto the logical surface at the offset
        self.game_surface.blit(self.map_surface, (self.map_offset_x, self.map_offset_y))

        # Draw HUD onto the logical surface (in the border area)
        self._draw_hud(player_tank, score)

        # Draw game over/victory screen if needed onto logical surface
        if state == GameState.GAME_OVER:
            self._draw_game_over()
        elif state == GameState.VICTORY:
            self._draw_victory()

        self._present_surface()

    def _present_surface(self) -> None:
        """Scale the logical surface to the screen and flip the display."""
        pygame.transform.scale(
            self.game_surface,
            (self.screen.get_width(), self.screen.get_height()),
            self._scaled_surface,
        )
        self.screen.blit(self._scaled_surface, (0, 0))
        pygame.display.flip()

    def _draw_hud(self, player_tank, score: int = 0) -> None:
        """Draw the heads-up display.

        Args:
            player_tank: The player's tank (used for lives and invincibility).
            score: Current player score.
        """
        # Draw lives in the top border area
        lives_text = self.small_font.render(f"Lives: {player_tank.lives}", True, WHITE)
        self.game_surface.blit(lives_text, (10, 10))

        # Draw score
        score_text = self.small_font.render(
            f"Score: {score:>6}", True, WHITE
        )
        score_rect = score_text.get_rect(topright=(self.logical_width - 10, 10))
        self.game_surface.blit(score_text, score_rect)

        # Draw invincibility timer if active
        if player_tank.is_invincible:
            remaining_time = max(
                0,
                player_tank.invincibility_duration - player_tank.invincibility_timer,
            )
            invincible_text = self.small_font.render(
                f"Invincible: {remaining_time:.1f}s", True, YELLOW
            )
            self.game_surface.blit(invincible_text, (10, 30))

    def _draw_game_over(self) -> None:
        """Draw the game over screen."""
        self._draw_overlay_screen("GAME OVER", RED, "Press R for Title")

    def _draw_victory(self) -> None:
        """Draw the victory screen."""
        self._draw_overlay_screen("VICTORY!", GREEN, "Press R for Title")

    def _draw_overlay_screen(
        self,
        title: str,
        title_color: Tuple[int, int, int],
        subtitle: str,
    ) -> None:
        """Draw a semi-transparent overlay with centered title and subtitle."""
        overlay = pygame.Surface(
            (self.logical_width, self.logical_height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 128))
        self.game_surface.blit(overlay, (0, 0))

        text = self.font.render(title, True, title_color)
        text_rect = text.get_rect(
            center=(self.logical_width // 2, self.logical_height // 2)
        )
        self.game_surface.blit(text, text_rect)

        subtitle_text = self.font.render(subtitle, True, WHITE)
        subtitle_rect = subtitle_text.get_rect(
            center=(self.logical_width // 2, self.logical_height // 2 + 50)
        )
        self.game_surface.blit(subtitle_text, subtitle_rect)

    def render_title_screen(self, menu_selection: int) -> None:
        """Render the title screen with menu options.

        Args:
            menu_selection: Currently selected menu item (0 or 1).
        """
        self.game_surface.fill(BLACK)

        cx = self.logical_width // 2
        cy = self.logical_height // 2

        # Title
        title = self.font.render("BATTLE CITY", True, WHITE)
        title_rect = title.get_rect(center=(cx, cy - 80))
        self.game_surface.blit(title, title_rect)

        # Menu options
        options = ["1 PLAYER", "2 PLAYERS"]
        colors = [WHITE, GRAY]  # 2 Players is greyed out (disabled)
        for i, (label, color) in enumerate(zip(options, colors)):
            text = self.small_font.render(label, True, color)
            text_rect = text.get_rect(center=(cx, cy + i * 30))
            self.game_surface.blit(text, text_rect)

        # Tank cursor next to selected option
        cursor_y = cy + menu_selection * 30
        cursor_text = self.small_font.render(">", True, WHITE)
        cursor_rect = cursor_text.get_rect(
            midright=(cx - 60, cursor_y)
        )
        self.game_surface.blit(cursor_text, cursor_rect)

        self._present_surface()
