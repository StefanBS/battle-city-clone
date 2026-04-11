import pygame
from typing import List, Optional, Sequence, Tuple
from src.states.game_state import GameState
from src.utils.constants import WHITE, BLACK, RED, GREEN, GRAY
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

        # Cached text surface for game over animation (set on first use)
        self._game_over_text: Optional[pygame.Surface] = None

        # HUD text cache (re-render only when values change)
        self._cached_lives: Optional[int] = None
        self._cached_lives_text: Optional[pygame.Surface] = None
        self._cached_score: Optional[int] = None
        self._cached_score_text: Optional[pygame.Surface] = None

        # Reusable overlay surfaces for pause/game-over screens
        self._pause_overlay: pygame.Surface = pygame.Surface(
            (logical_width, logical_height), pygame.SRCALPHA
        )
        self._pause_overlay.fill((0, 0, 0, 160))
        self._dark_overlay: pygame.Surface = pygame.Surface(
            (logical_width, logical_height), pygame.SRCALPHA
        )
        self._dark_overlay.fill((0, 0, 0, 128))

    def render(
        self,
        game_map,
        player_tank,
        enemy_tanks: List,
        bullets: List,
        effect_manager,
        state: GameState,
        score: int = 0,
        power_ups: Sequence = (),
        game_over_rise_progress: Optional[float] = None,
    ) -> None:
        """Render the complete game frame.

        Args:
            game_map: The game map to draw.
            player_tank: The player's tank.
            enemy_tanks: List of enemy tanks.
            bullets: List of bullets.
            state: Current game state.
            score: Current player score.
            power_ups: Active power-ups to draw.
        """
        # Fill logical surface with border color (gray)
        self.game_surface.fill(self.border_color)

        # Clear the map area with black background
        self.map_surface.fill(self.background_color)

        # Draw ground tiles (everything except bushes)
        game_map.draw(self.map_surface)

        # Draw game objects (tanks pass under bushes)
        player_tank.draw(self.map_surface)
        for enemy in enemy_tanks:
            enemy.draw(self.map_surface)
        for power_up in power_ups:
            power_up.draw(self.map_surface)
        for bullet in bullets:
            if bullet.active:
                bullet.draw(self.map_surface)

        # Draw bush overlay on top of tanks/bullets
        game_map.draw_overlay(self.map_surface)

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
        elif state == GameState.GAME_COMPLETE:
            self._draw_overlay_screen("GAME COMPLETE!", GREEN, "Press R for Title")
        elif game_over_rise_progress is not None:
            self._draw_game_over_rising(game_over_rise_progress)

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
            player_tank: The player's tank (used for lives).
            score: Current player score.
        """
        if self._cached_lives != player_tank.lives:
            self._cached_lives = player_tank.lives
            self._cached_lives_text = self.small_font.render(
                f"Lives: {player_tank.lives}", True, WHITE
            )
        self.game_surface.blit(self._cached_lives_text, (10, 10))

        if self._cached_score != score:
            self._cached_score = score
            self._cached_score_text = self.small_font.render(
                f"Score: {score:>6}", True, WHITE
            )
        score_rect = self._cached_score_text.get_rect(
            topright=(self.logical_width - 10, 10)
        )
        self.game_surface.blit(self._cached_score_text, score_rect)

    def _draw_game_over_rising(self, progress: float) -> None:
        """Draw 'GAME OVER' text rising from bottom to center.

        Args:
            progress: 0.0 (text at bottom) to 1.0 (text at center).
        """
        if self._game_over_text is None:
            self._game_over_text = self.font.render("GAME OVER", True, RED)
        text = self._game_over_text
        center_y = self.logical_height // 2
        bottom_y = self.logical_height + text.get_height()
        y = bottom_y + (center_y - bottom_y) * progress
        text_rect = text.get_rect(center=(self.logical_width // 2, int(y)))
        self.game_surface.blit(text, text_rect)

    def _draw_game_over(self) -> None:
        """Draw the game over screen."""
        self._draw_overlay_screen("GAME OVER", RED, "Press R for Title")

    def _draw_victory(self) -> None:
        """Draw the victory screen."""
        self._draw_overlay_screen("VICTORY!", GREEN, "Next Stage...")

    def render_curtain(self, progress: float, stage: int) -> None:
        """Render the stage curtain animation.

        Args:
            progress: 0.0 (open) to 1.0 (fully closed).
            stage: Current stage number to display when closed.
        """
        self.game_surface.fill(self.background_color)

        half_height = self.logical_height // 2
        curtain_height = int(progress * half_height)

        if curtain_height > 0:
            top_rect = pygame.Rect(0, 0, self.logical_width, curtain_height)
            pygame.draw.rect(self.game_surface, self.border_color, top_rect)
            bottom_rect = pygame.Rect(
                0,
                self.logical_height - curtain_height,
                self.logical_width,
                curtain_height,
            )
            pygame.draw.rect(self.game_surface, self.border_color, bottom_rect)

        if progress >= 1.0:
            stage_text = self.font.render(f"STAGE {stage}", True, WHITE)
            stage_rect = stage_text.get_rect(
                center=(self.logical_width // 2, self.logical_height // 2)
            )
            self.game_surface.blit(stage_text, stage_rect)

        self._present_surface()

    def _draw_overlay_screen(
        self,
        title: str,
        title_color: Tuple[int, int, int],
        subtitle: str,
    ) -> None:
        """Draw a semi-transparent overlay with centered title and subtitle."""
        self.game_surface.blit(self._dark_overlay, (0, 0))

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
            menu_selection: Currently selected menu item (0-4).
        """
        self.game_surface.fill(BLACK)

        cx = self.logical_width // 2
        cy = self.logical_height // 2

        # Title
        title = self.font.render("BATTLE CITY", True, WHITE)
        title_rect = title.get_rect(center=(cx, cy - 80))
        self.game_surface.blit(title, title_rect)

        # Menu options
        options = ["1 PLAYER", "2 PLAYERS", "OPTIONS", "DEMO", "QUIT"]
        colors = [WHITE, GRAY, WHITE, WHITE, WHITE]
        for i, (label, color) in enumerate(zip(options, colors)):
            text = self.small_font.render(label, True, color)
            text_rect = text.get_rect(center=(cx, cy + i * 30))
            self.game_surface.blit(text, text_rect)

        # Tank cursor next to selected option
        cursor_y = cy + menu_selection * 30
        cursor_text = self.small_font.render(">", True, WHITE)
        cursor_rect = cursor_text.get_rect(midright=(cx - 60, cursor_y))
        self.game_surface.blit(cursor_text, cursor_rect)

        self._present_surface()

    def render_pause_menu(self, menu_selection: int) -> None:
        """Render pause menu overlay on top of frozen game frame.

        Does NOT clear the game surface — draws on top of the
        last rendered game frame to show the paused game behind.
        """
        self.game_surface.blit(self._pause_overlay, (0, 0))

        cx = self.logical_width // 2
        cy = self.logical_height // 2

        title = self.font.render("PAUSED", True, WHITE)
        title_rect = title.get_rect(center=(cx, cy - 60))
        self.game_surface.blit(title, title_rect)

        options = ["RESUME", "OPTIONS", "TITLE SCREEN", "QUIT"]
        for i, label in enumerate(options):
            text = self.small_font.render(label, True, WHITE)
            text_rect = text.get_rect(center=(cx, cy + i * 30))
            self.game_surface.blit(text, text_rect)

        cursor_y = cy + menu_selection * 30
        cursor_text = self.small_font.render(">", True, WHITE)
        cursor_rect = cursor_text.get_rect(midright=(cx - 80, cursor_y))
        self.game_surface.blit(cursor_text, cursor_rect)

        self._present_surface()

    def _draw_lr_hints(self, rect: "pygame.Rect", y: int) -> None:
        """Draw < > arrow hints around a menu item."""
        left_hint = self.small_font.render("<", True, GRAY)
        self.game_surface.blit(left_hint, (rect.left - 20, y - 6))
        right_hint = self.small_font.render(">", True, GRAY)
        self.game_surface.blit(right_hint, (rect.right + 8, y - 6))

    def render_options_menu(
        self, master_volume: float, difficulty: str, selection: int
    ) -> None:
        """Render options menu with difficulty toggle and volume slider."""
        self.game_surface.fill(BLACK)

        cx = self.logical_width // 2
        cy = self.logical_height // 2
        row_spacing = 40

        title = self.font.render("OPTIONS", True, WHITE)
        title_rect = title.get_rect(center=(cx, cy - 80))
        self.game_surface.blit(title, title_rect)

        # Row 0: Difficulty
        diff_y = cy - row_spacing
        diff_label = f"DIFFICULTY  {difficulty.upper()}"
        diff_text = self.small_font.render(diff_label, True, WHITE)
        diff_rect = diff_text.get_rect(center=(cx, diff_y))
        self.game_surface.blit(diff_text, diff_rect)

        if selection == 0:
            self._draw_lr_hints(diff_rect, diff_y)

        # Row 1: Volume
        vol_y = cy
        filled = round(master_volume * 10)
        bar = "#" * filled + "-" * (10 - filled)
        pct = f"{round(master_volume * 100)}%"
        vol_label = f"VOLUME  [{bar}] {pct}"
        vol_text = self.small_font.render(vol_label, True, WHITE)
        vol_rect = vol_text.get_rect(center=(cx, vol_y))
        self.game_surface.blit(vol_text, vol_rect)

        if selection == 1:
            self._draw_lr_hints(vol_rect, vol_y)

        # Row 2: Back
        back_y = cy + row_spacing
        back_text = self.small_font.render("BACK", True, WHITE)
        back_rect = back_text.get_rect(center=(cx, back_y))
        self.game_surface.blit(back_text, back_rect)

        # Cursor
        rects = [diff_rect, vol_rect, back_rect]
        ys = [diff_y, vol_y, back_y]
        target_rect = rects[selection]
        cursor_y = ys[selection]
        cursor_text = self.small_font.render(">", True, WHITE)
        cursor_rect = cursor_text.get_rect(midright=(target_rect.left - 10, cursor_y))
        self.game_surface.blit(cursor_text, cursor_rect)

        self._present_surface()
