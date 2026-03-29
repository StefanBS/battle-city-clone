import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.managers.game_manager import GameManager
from src.states.game_state import GameState
from src.core.enemy_tank import EnemyTank
from src.utils.constants import (
    WINDOW_TITLE,
    FPS,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
)


class TestGameManager:
    """Unit test cases for the GameManager class."""

    @pytest.fixture
    def game_manager(self):
        """Create a game manager instance for testing."""
        pygame.init()
        # Mock display, font, and TextureManager *before* GameManager is created
        with (
            patch("pygame.display.set_mode"),
            patch("pygame.font.SysFont"),
            patch("src.managers.game_manager.TextureManager") as MockTextureManager,
            patch("src.managers.game_manager.Renderer"),
            patch("src.managers.game_manager.SpawnManager"),
            patch("src.managers.game_manager.Map") as MockMap,
        ):
            # Configure the mock TextureManager instance that GameManager will create
            mock_tm_instance = MockTextureManager.return_value
            mock_tm_instance.get_sprite.return_value = MagicMock(spec=pygame.Surface)

            # Configure the mock Map instance
            mock_map_instance = MockMap.return_value
            mock_map_instance.width = 16
            mock_map_instance.height = 16
            mock_map_instance.player_spawn = (4, 12)
            mock_map_instance.spawn_points = [(3, 1), (8, 1), (12, 1)]

            manager = GameManager()
        yield manager
        pygame.quit()

    def test_initialization(self, game_manager):
        """Test that the game manager initializes correctly."""
        assert game_manager.state == GameState.RUNNING
        assert game_manager.fps == FPS
        # Assert against constants used in GameManager init
        assert game_manager.screen_width == WINDOW_WIDTH
        assert game_manager.screen_height == WINDOW_HEIGHT
        assert pygame.display.get_caption()[0] == WINDOW_TITLE
        assert game_manager.spawn_manager is not None
        assert game_manager.renderer is not None

    def test_handle_events_quit(self, game_manager):
        """Test handling quit event sets state to EXIT."""
        # with pytest.raises(SystemExit): # Should not raise SystemExit anymore
        event = pygame.event.Event(pygame.QUIT)
        pygame.event.post(event)
        game_manager.handle_events()
        # Check if state is set to EXIT
        assert game_manager.state == GameState.EXIT

    def test_handle_events_escape(self, game_manager):
        """Test handling escape key event sets state to EXIT."""
        # with pytest.raises(SystemExit): # Should not raise SystemExit anymore
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        pygame.event.post(event)
        game_manager.handle_events()
        # Check if state is set to EXIT
        assert game_manager.state == GameState.EXIT

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

    # --- Game State Tests --- #

    def test_current_stage_initialized(self, game_manager):
        """Test that current_stage starts at 1."""
        assert game_manager.current_stage == 1

    def test_update_stops_when_not_running(self, game_manager):
        """Test that update method does nothing if state is not RUNNING."""
        game_manager.state = GameState.GAME_OVER
        # Mock methods that should not be called during the update phase
        # if game is not running. Collision processing happens before this check.
        game_manager.player_tank.update = MagicMock()
        # Use a real list for enemy_tanks for the update loop check
        mock_enemy = MagicMock(spec=EnemyTank)
        mock_enemy.tank_type = "basic"
        game_manager.spawn_manager.enemy_tanks = [mock_enemy]
        game_manager.spawn_manager = MagicMock()
        game_manager.collision_response_handler = MagicMock()

        game_manager.update()

        game_manager.player_tank.update.assert_not_called()
        mock_enemy.update.assert_not_called()
        game_manager.spawn_manager.update.assert_not_called()
        game_manager.collision_response_handler.process_collisions.assert_not_called()

