import pytest
import pygame
from managers.game_manager import GameManager
from states.game_state import GameState
from utils.constants import (
    WINDOW_TITLE,
    FPS,
    TILE_SIZE,
    GRID_WIDTH,
    GRID_HEIGHT,
    BLACK,
)


class TestGameManager:
    """Unit test cases for the GameManager class."""

    @pytest.fixture
    def game_manager(self):
        """Create a game manager instance for testing."""
        pygame.init()
        manager = GameManager()
        yield manager
        pygame.quit()

    def test_initialization(self, game_manager):
        """Test that the game manager initializes correctly."""
        assert game_manager.state == GameState.RUNNING
        assert game_manager.background_color == BLACK
        assert game_manager.fps == FPS
        assert game_manager.tile_size == TILE_SIZE
        assert game_manager.screen_width == GRID_WIDTH * TILE_SIZE
        assert game_manager.screen_height == GRID_HEIGHT * TILE_SIZE
        assert pygame.display.get_caption()[0] == WINDOW_TITLE

    def test_handle_events_quit(self, game_manager):
        """Test handling quit event."""
        with pytest.raises(SystemExit):
            event = pygame.event.Event(pygame.QUIT)
            pygame.event.post(event)
            game_manager.handle_events()

    def test_handle_events_escape(self, game_manager):
        """Test handling escape key event."""
        with pytest.raises(SystemExit):
            event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
            pygame.event.post(event)
            game_manager.handle_events()

    def test_handle_events_restart(self, game_manager):
        """Test handling restart key event."""
        # Set game to game over state
        game_manager.state = GameState.GAME_OVER

        # Simulate R key press
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        pygame.event.post(event)
        game_manager.handle_events()

        # Game should be reset
        assert game_manager.state == GameState.RUNNING

    def test_handle_events_restart_not_game_over(self, game_manager):
        """Test that restart key does nothing when game is running."""
        initial_state = game_manager.state

        # Simulate R key press
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        pygame.event.post(event)
        game_manager.handle_events()

        # Game state should not change
        assert game_manager.state == initial_state
