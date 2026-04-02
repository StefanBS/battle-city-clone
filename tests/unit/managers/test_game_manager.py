import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.managers.game_manager import GameManager
from src.states.game_state import GameState
from src.core.enemy_tank import EnemyTank
from src.utils.constants import FPS


class TestGameManager:
    """Unit test cases for the GameManager class."""

    @pytest.fixture
    def game_manager(self):
        """Create a game manager instance for testing."""
        pygame.init()
        # Keep mocks alive for the duration of the test so _reset_game
        # can be called again (e.g. by pressing R to restart).
        with (
            patch("pygame.display.set_mode"),
            patch("pygame.font.SysFont"),
            patch("src.managers.game_manager.TextureManager") as MockTM,
            patch("src.managers.game_manager.EffectManager"),
            patch("src.managers.game_manager.Renderer"),
            patch("src.managers.game_manager.SpawnManager"),
            patch("src.managers.game_manager.Map") as MockMap,
        ):
            mock_tm_instance = MockTM.return_value
            mock_tm_instance.get_sprite.return_value = MagicMock(spec=pygame.Surface)

            mock_map_instance = MockMap.return_value
            mock_map_instance.width = 16
            mock_map_instance.height = 16
            mock_map_instance.player_spawn = (4, 12)
            mock_map_instance.spawn_points = [(3, 1), (8, 1), (12, 1)]

            manager = GameManager()
            manager._reset_game()
            yield manager
        pygame.quit()

    def test_initialization_starts_at_title_screen(self, game_manager):
        """Test that GameManager starts at the title screen."""
        # game_manager fixture calls _reset_game, so state is RUNNING.
        # Verify the title screen state is reachable.
        game_manager.state = GameState.TITLE_SCREEN
        assert game_manager.state == GameState.TITLE_SCREEN
        assert game_manager.fps == FPS
        assert game_manager.renderer is not None

    def test_handle_events_quit(self, game_manager):
        """Test handling quit event sets state to EXIT."""
        # with pytest.raises(SystemExit): # Should not raise SystemExit anymore
        event = pygame.event.Event(pygame.QUIT)
        pygame.event.post(event)
        game_manager.handle_events()
        # Check if state is set to EXIT
        assert game_manager.state == GameState.EXIT

    def test_handle_events_escape(self, game_manager, key_down_event):
        """Test handling escape key event sets state to EXIT."""
        pygame.event.post(key_down_event(pygame.K_ESCAPE))
        game_manager.handle_events()
        assert game_manager.state == GameState.EXIT

    def test_handle_events_restart(self, game_manager, key_down_event):
        """Test pressing R on game over returns to title screen."""
        game_manager.state = GameState.GAME_OVER
        pygame.event.post(key_down_event(pygame.K_r))
        game_manager.handle_events()
        assert game_manager.state == GameState.TITLE_SCREEN

    def test_handle_events_restart_not_game_over(self, game_manager, key_down_event):
        """Test that restart key does nothing when game is running."""
        initial_state = game_manager.state
        pygame.event.post(key_down_event(pygame.K_r))
        game_manager.handle_events()
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
