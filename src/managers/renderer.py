import pygame
from typing import List, Tuple
from src.states.game_state import GameState
from src.utils.constants import WHITE, YELLOW, BLACK, RED, GREEN


class Renderer:
    """Handles all rendering logic for the game.

    Manages the logical game surface, fonts, HUD, and overlay screens.
    Receives all data per-call rather than holding entity references.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        logical_width: int,
        logical_height: int,
    ) -> None:
        """Initialize the renderer.

        Args:
            screen: The main display surface (window).
            logical_width: Width of the logical game surface in pixels.
            logical_height: Height of the logical game surface in pixels.
        """
        self.screen = screen
        self.logical_width = logical_width
        self.logical_height = logical_height
        self.game_surface: pygame.Surface = pygame.Surface(
            (logical_width, logical_height)
        )
        self.background_color: Tuple[int, int, int] = BLACK
        self.font: pygame.font.Font = pygame.font.SysFont(None, 48)
        self.small_font: pygame.font.Font = pygame.font.SysFont(None, 24)
        self._scaled_surface: pygame.Surface = pygame.Surface(
            (screen.get_width(), screen.get_height())
        )

    def render(
        self,
        game_map,
        player_tank,
        enemy_tanks: List,
        bullets: List,
        state: GameState,
    ) -> None:
        """Render the complete game frame.

        Args:
            game_map: The game map to draw.
            player_tank: The player's tank.
            enemy_tanks: List of enemy tanks.
            bullets: List of bullets.
            state: Current game state.
        """
        # Clear the logical game surface
        self.game_surface.fill(self.background_color)

        # Draw the map onto the logical surface
        game_map.draw(self.game_surface)

        # Draw the player tank onto the logical surface
        player_tank.draw(self.game_surface)

        # Draw enemy tanks onto the logical surface
        for enemy in enemy_tanks:
            enemy.draw(self.game_surface)

        # Draw all bullets
        for bullet in bullets:
            if bullet.active:
                bullet.draw(self.game_surface)

        # Draw HUD onto the logical surface
        self._draw_hud(player_tank)

        # Draw game over/victory screen if needed onto logical surface
        if state == GameState.GAME_OVER:
            self._draw_game_over()
        elif state == GameState.VICTORY:
            self._draw_victory()

        # Scale the logical surface to the main screen (reuse pre-allocated surface)
        pygame.transform.scale(
            self.game_surface,
            (self.screen.get_width(), self.screen.get_height()),
            self._scaled_surface,
        )
        self.screen.blit(self._scaled_surface, (0, 0))

        # Update the display
        pygame.display.flip()

    def _draw_hud(self, player_tank) -> None:
        """Draw the heads-up display.

        Args:
            player_tank: The player's tank (used for lives and invincibility).
        """
        # Draw lives onto the logical surface
        lives_text = self.small_font.render(f"Lives: {player_tank.lives}", True, WHITE)
        self.game_surface.blit(lives_text, (10, 10))

        # Draw invincibility timer if active onto the logical surface
        if player_tank.is_invincible:
            remaining_time = max(
                0,
                player_tank.invincibility_duration - player_tank.invincibility_timer,
            )
            invincible_text = self.small_font.render(
                f"Invincible: {remaining_time:.1f}s", True, YELLOW
            )
            self.game_surface.blit(invincible_text, (10, 40))

    def _draw_game_over(self) -> None:
        """Draw the game over screen."""
        self._draw_overlay_screen("GAME OVER", RED, "Press R to Restart")

    def _draw_victory(self) -> None:
        """Draw the victory screen."""
        self._draw_overlay_screen("VICTORY!", GREEN, "Press R to Play Again")

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
