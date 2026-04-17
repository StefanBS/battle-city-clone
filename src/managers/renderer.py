import pygame
from typing import Dict, List, Optional, Sequence, Tuple
from src.states.game_state import GameState
from src.utils.constants import (
    WHITE,
    BLACK,
    RED,
    GREEN,
    GRAY,
    Difficulty,
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    PAUSE_OVERLAY_ALPHA,
    DARK_OVERLAY_ALPHA,
)
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
        self._center_x: int = logical_width // 2
        self._center_y: int = logical_height // 2
        self.game_surface: pygame.Surface = pygame.Surface(
            (logical_width, logical_height)
        )
        font_path = resource_path("assets/fonts/PressStart2P-Regular.ttf")
        self.font: pygame.font.Font = pygame.font.Font(font_path, FONT_SIZE_LARGE)
        self.small_font: pygame.font.Font = pygame.font.Font(font_path, FONT_SIZE_SMALL)

        self.map_offset_x: int = (logical_width - map_width_px) // 2
        self.map_offset_y: int = (logical_height - map_height_px) // 2

        self.map_surface: pygame.Surface = pygame.Surface((map_width_px, map_height_px))

        # Cached text surface for game over animation (set on first use)
        self._game_over_text: Optional[pygame.Surface] = None

        # HUD text cache: {slot -> (label_str, score_str, label_surf, score_surf)}
        self._cached_hud: Dict[str, tuple] = {}

        # Reusable overlay surfaces for pause/game-over screens
        self._pause_overlay: pygame.Surface = pygame.Surface(
            (logical_width, logical_height), pygame.SRCALPHA
        )
        self._pause_overlay.fill((0, 0, 0, PAUSE_OVERLAY_ALPHA))
        self._dark_overlay: pygame.Surface = pygame.Surface(
            (logical_width, logical_height), pygame.SRCALPHA
        )
        self._dark_overlay.fill((0, 0, 0, DARK_OVERLAY_ALPHA))

    def render(
        self,
        game_map,
        player_tanks: List,
        enemy_tanks: List,
        bullets: List,
        effect_manager,
        state: GameState,
        scores: Optional[Dict[int, int]] = None,
        power_ups: Sequence = (),
        game_over_rise_progress: Optional[float] = None,
    ) -> None:
        """Render the complete game frame.

        Args:
            game_map: The game map to draw.
            player_tanks: List of player tanks.
            enemy_tanks: List of enemy tanks.
            bullets: List of bullets.
            state: Current game state.
            scores: Per-player scores dict {player_id: score}.
            power_ups: Active power-ups to draw.
        """
        self.game_surface.fill(GRAY)
        self.map_surface.fill(BLACK)

        game_map.draw(self.map_surface)

        for player_tank in player_tanks:
            player_tank.draw(self.map_surface)
        for enemy in enemy_tanks:
            enemy.draw(self.map_surface)
        for power_up in power_ups:
            power_up.draw(self.map_surface)
        for bullet in bullets:
            if bullet.active:
                bullet.draw(self.map_surface)

        game_map.draw_overlay(self.map_surface)
        effect_manager.draw(self.map_surface)

        self.game_surface.blit(self.map_surface, (self.map_offset_x, self.map_offset_y))

        self._draw_hud(player_tanks, scores)

        if state == GameState.VICTORY:
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
            self.screen,
        )
        pygame.display.flip()

    def _draw_centered_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: Tuple[int, int, int],
        y: int,
    ) -> None:
        """Render text centered horizontally at the given y position."""
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(self._center_x, y))
        self.game_surface.blit(surface, rect)

    def _draw_hud(
        self, player_tanks: List, scores: Optional[Dict[int, int]] = None
    ) -> None:
        """Draw the heads-up display.

        Args:
            player_tanks: List of player tanks.
            scores: Per-player scores dict {player_id: score}.
        """
        if scores is None:
            scores = {}

        is_2p = len(player_tanks) > 1

        if is_2p:
            for i, player in enumerate(player_tanks):
                pid = player.player_id
                player_score = scores.get(pid, 0)
                eliminated = player.health <= 0 and player.lives <= 0
                if eliminated:
                    label = f"P{pid}: OUT"
                    color = GRAY
                else:
                    label = f"P{pid}: {player.lives}"
                    color = WHITE
                align = "left" if i == 0 else "right"
                self._draw_hud_slot(
                    f"p{pid}", label, f"{player_score:>6}", color, align
                )
        else:
            lives = player_tanks[0].lives if player_tanks else 0
            total_score = sum(scores.values())
            self._draw_hud_slot("lives", f"Lives: {lives}", None, WHITE, "left")
            self._draw_hud_slot(
                "score", f"Score: {total_score:>6}", None, WHITE, "right"
            )

    def _draw_hud_slot(
        self,
        slot: str,
        label: str,
        score_text: Optional[str],
        color: Tuple[int, int, int],
        align: str,
    ) -> None:
        """Render and blit a cached HUD slot (label + optional score line).

        Re-renders only when the text changes.
        """
        cached = self._cached_hud.get(slot)
        if cached is None or cached[0] != label or cached[1] != score_text:
            label_surf = self.small_font.render(label, True, color)
            score_surf = (
                self.small_font.render(score_text, True, WHITE) if score_text else None
            )
            self._cached_hud[slot] = (label, score_text, label_surf, score_surf)
        else:
            label_surf = cached[2]
            score_surf = cached[3]

        if align == "left":
            self.game_surface.blit(label_surf, (10, 10))
            if score_surf:
                self.game_surface.blit(score_surf, (10, 24))
        else:
            label_rect = label_surf.get_rect(topright=(self.logical_width - 10, 10))
            self.game_surface.blit(label_surf, label_rect)
            if score_surf:
                score_rect = score_surf.get_rect(topright=(self.logical_width - 10, 24))
                self.game_surface.blit(score_surf, score_rect)

    def _draw_game_over_rising(self, progress: float) -> None:
        """Draw 'GAME OVER' text rising from bottom to center.

        Args:
            progress: 0.0 (text at bottom) to 1.0 (text at center).
        """
        if self._game_over_text is None:
            self._game_over_text = self.font.render("GAME OVER", True, RED)
        text = self._game_over_text
        bottom_y = self.logical_height + text.get_height()
        y = bottom_y + (self._center_y - bottom_y) * progress
        text_rect = text.get_rect(center=(self._center_x, int(y)))
        self.game_surface.blit(text, text_rect)

    def _draw_victory(self) -> None:
        """Draw the victory screen."""
        self._draw_overlay_screen("VICTORY!", GREEN, "Next Stage...")

    def render_curtain(self, progress: float, stage: Optional[int]) -> None:
        """Render the stage curtain animation.

        Args:
            progress: 0.0 (open) to 1.0 (fully closed).
            stage: Stage number to display when fully closed, or None to
                draw the wipe without any label (e.g. game-over → title).
        """
        self.game_surface.fill(BLACK)

        half_height = self._center_y
        curtain_height = int(progress * half_height)

        if curtain_height > 0:
            top_rect = pygame.Rect(0, 0, self.logical_width, curtain_height)
            pygame.draw.rect(self.game_surface, GRAY, top_rect)
            bottom_rect = pygame.Rect(
                0,
                self.logical_height - curtain_height,
                self.logical_width,
                curtain_height,
            )
            pygame.draw.rect(self.game_surface, GRAY, bottom_rect)

        if progress >= 1.0 and stage is not None:
            self._draw_centered_text(f"STAGE {stage}", self.font, WHITE, self._center_y)

        self._present_surface()

    def _draw_overlay_screen(
        self,
        title: str,
        title_color: Tuple[int, int, int],
        subtitle: str,
    ) -> None:
        """Draw a semi-transparent overlay with centered title and subtitle."""
        self.game_surface.blit(self._dark_overlay, (0, 0))
        self._draw_centered_text(title, self.font, title_color, self._center_y)
        self._draw_centered_text(subtitle, self.font, WHITE, self._center_y + 50)

    def _draw_menu(
        self,
        options: List[str],
        selection: int,
        start_y: int,
        spacing: int = 30,
        colors: Optional[List[Tuple[int, int, int]]] = None,
    ) -> List[pygame.Rect]:
        """Draw a vertical list of options with a cursor. Returns option rects."""
        rects = []
        for i, label in enumerate(options):
            color = colors[i] if colors else WHITE
            text = self.small_font.render(label, True, color)
            text_rect = text.get_rect(center=(self._center_x, start_y + i * spacing))
            self.game_surface.blit(text, text_rect)
            rects.append(text_rect)

        cursor_y = start_y + selection * spacing
        cursor_text = self.small_font.render(">", True, WHITE)
        cursor_rect = cursor_text.get_rect(
            midright=(rects[selection].left - 10, cursor_y)
        )
        self.game_surface.blit(cursor_text, cursor_rect)
        return rects

    def render_title_screen(self, labels: Sequence[str], menu_selection: int) -> None:
        """Render the title screen with menu options."""
        self.game_surface.fill(BLACK)

        self._draw_centered_text("BATTLE CITY", self.font, WHITE, self._center_y - 80)

        self._draw_menu(
            [label.upper() for label in labels], menu_selection, self._center_y
        )

        self._present_surface()

    def render_pause_menu(self, labels: Sequence[str], menu_selection: int) -> None:
        """Render pause menu overlay on top of frozen game frame.

        Does NOT clear the game surface — draws on top of the
        last rendered game frame to show the paused game behind.
        """
        self.game_surface.blit(self._pause_overlay, (0, 0))

        self._draw_centered_text("PAUSED", self.font, WHITE, self._center_y - 60)

        self._draw_menu(
            [label.upper() for label in labels], menu_selection, self._center_y
        )

        self._present_surface()

    def render_options_menu(
        self, master_volume: float, difficulty: Difficulty, selection: int
    ) -> None:
        """Render options menu with difficulty toggle and volume slider."""
        self.game_surface.fill(BLACK)

        row_spacing = 40

        self._draw_centered_text("OPTIONS", self.font, WHITE, self._center_y - 80)

        diff_label = f"DIFFICULTY  < {difficulty.value.upper()} >"
        filled = round(master_volume * 10)
        bar = "#" * filled + "-" * (10 - filled)
        pct = f"{round(master_volume * 100)}%"
        vol_label = f"VOLUME  [{bar}] {pct}"

        options = [diff_label, vol_label, "BACK"]
        self._draw_menu(
            options,
            selection,
            self._center_y - row_spacing,
            spacing=row_spacing,
        )

        self._present_surface()
