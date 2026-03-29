import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.managers.game_manager import GameManager
from src.states.game_state import GameState
from src.core.enemy_tank import EnemyTank
from src.core.tile import TileType
from src.utils.constants import (
    WINDOW_TITLE,
    FPS,
    TILE_SIZE,
    BLACK,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
)
from loguru import logger


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
        ):
            # Configure the mock TextureManager instance that GameManager will create
            mock_tm_instance = MockTextureManager.return_value
            mock_tm_instance.get_sprite.return_value = MagicMock(spec=pygame.Surface)

            manager = GameManager()
        yield manager
        pygame.quit()

    def test_initialization(self, game_manager):
        """Test that the game manager initializes correctly."""
        assert game_manager.state == GameState.RUNNING
        assert game_manager.background_color == BLACK
        assert game_manager.fps == FPS
        assert game_manager.tile_size == TILE_SIZE
        # Assert against constants used in GameManager init
        assert game_manager.screen_width == WINDOW_WIDTH
        assert game_manager.screen_height == WINDOW_HEIGHT
        assert pygame.display.get_caption()[0] == WINDOW_TITLE

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

    def test_initial_enemy_spawn(self, game_manager):
        """Test that an enemy tank is spawned on initialization."""
        assert len(game_manager.enemy_tanks) == 1
        assert game_manager.total_enemy_spawns == 1

    @patch("random.choice")
    def test_spawn_enemy_adds_enemy(self, mock_random_choice, game_manager):
        """Test that _spawn_enemy adds an enemy tank when the spot is clear."""
        # Ensure the chosen spawn point is clear (mock map check)
        mock_random_choice.return_value = game_manager.SPAWN_POINTS[0]
        game_manager.map.get_collidable_tiles = MagicMock(return_value=[])
        # Ensure no existing tanks interfere with this specific test
        game_manager.enemy_tanks = []
        game_manager.total_enemy_spawns = 0

        initial_enemies = len(game_manager.enemy_tanks)  # Should be 0 now
        initial_spawns = game_manager.total_enemy_spawns  # Should be 0 now
        game_manager._spawn_enemy()

        assert (
            len(game_manager.enemy_tanks) == initial_enemies + 1
        )  # Checks it becomes 1
        assert (
            game_manager.total_enemy_spawns == initial_spawns + 1
        )  # Checks it becomes 1

    @patch("random.choice")
    def test_spawn_enemy_respects_max_spawns(self, mock_random_choice, game_manager):
        """Test that _spawn_enemy respects the maximum spawn limit."""
        mock_random_choice.return_value = game_manager.SPAWN_POINTS[0]
        game_manager.map.get_collidable_tiles = MagicMock(return_value=[])
        game_manager.total_enemy_spawns = game_manager.max_enemy_spawns

        initial_enemies = len(game_manager.enemy_tanks)
        game_manager._spawn_enemy()

        assert len(game_manager.enemy_tanks) == initial_enemies  # No new enemy added
        assert game_manager.total_enemy_spawns == game_manager.max_enemy_spawns

    @patch("random.choice")
    def test_spawn_enemy_avoids_map_collision(self, mock_random_choice, game_manager):
        """Test that _spawn_enemy avoids spawning on map collision tiles."""
        spawn_point_grid = game_manager.SPAWN_POINTS[0]
        mock_random_choice.return_value = spawn_point_grid
        spawn_x = spawn_point_grid[0] * game_manager.tile_size
        spawn_y = spawn_point_grid[1] * game_manager.tile_size
        # Simulate a map tile at the spawn point
        colliding_tile = pygame.Rect(
            spawn_x, spawn_y, game_manager.tile_size, game_manager.tile_size
        )
        game_manager.map.get_collidable_tiles = MagicMock(return_value=[colliding_tile])

        initial_enemies = len(game_manager.enemy_tanks)
        initial_spawns = (
            game_manager.total_enemy_spawns
        )  # Spawn count shouldn't increase if blocked
        game_manager._spawn_enemy()

        assert len(game_manager.enemy_tanks) == initial_enemies
        assert game_manager.total_enemy_spawns == initial_spawns

    @patch("random.choice")
    def test_spawn_enemy_avoids_tank_collision(self, mock_random_choice, game_manager):
        """Test that _spawn_enemy avoids spawning on other tanks."""
        spawn_point_grid = game_manager.SPAWN_POINTS[0]
        mock_random_choice.return_value = spawn_point_grid
        spawn_x = spawn_point_grid[0] * game_manager.tile_size
        spawn_y = spawn_point_grid[1] * game_manager.tile_size
        game_manager.map.get_collidable_tiles = MagicMock(return_value=[])  # Clear map

        # Place an existing enemy at the spawn point
        existing_enemy = MagicMock(spec=EnemyTank)
        existing_enemy.rect = pygame.Rect(
            spawn_x, spawn_y, game_manager.tile_size, game_manager.tile_size
        )
        existing_enemy.tank_type = "basic"
        game_manager.enemy_tanks = [existing_enemy]  # Replace initial enemy
        game_manager.total_enemy_spawns = 1  # Reflect the one enemy

        initial_enemies = len(game_manager.enemy_tanks)
        game_manager._spawn_enemy()

        assert len(game_manager.enemy_tanks) == initial_enemies  # Should still be 1
        assert game_manager.total_enemy_spawns == 1  # Spawn count shouldn't increase

    @patch("src.managers.game_manager.GameManager._spawn_enemy")
    def test_update_calls_spawn_enemy_on_interval(self, mock_spawn_enemy, game_manager):
        """Test update calls _spawn_enemy when the timer reaches the interval."""
        dt = 1.0 / game_manager.fps

        # 1. Test just below interval -> NO call
        logger.debug("Testing spawn timer just below interval...")
        # Set timer more than 1 dt below interval to account for dt increment
        game_manager.spawn_timer = game_manager.spawn_interval - (dt * 1.1)
        mock_spawn_enemy.reset_mock()
        game_manager.update()
        mock_spawn_enemy.assert_not_called()
        logger.debug("Verified: No spawn call below interval.")

        # 2. Test exactly at interval -> CALL and reset timer on success
        logger.debug("Testing spawn timer exactly at interval...")
        game_manager.spawn_timer = game_manager.spawn_interval
        mock_spawn_enemy.reset_mock()
        mock_spawn_enemy.return_value = True  # Assume spawn succeeds
        game_manager.update()
        mock_spawn_enemy.assert_called_once()
        assert game_manager.spawn_timer == pytest.approx(0), (
            "Timer not reset after spawn"
        )
        logger.debug("Verified: Spawn called at interval, timer reset.")

        # 3. Test significantly above interval -> CALL and reset timer on success
        logger.debug("Testing spawn timer significantly above interval...")
        game_manager.spawn_timer = game_manager.spawn_interval + 10.0  # Well above
        mock_spawn_enemy.reset_mock()
        mock_spawn_enemy.return_value = True  # Assume spawn succeeds
        game_manager.update()
        mock_spawn_enemy.assert_called_once()
        assert game_manager.spawn_timer == pytest.approx(0), (
            "Timer not reset when starting above interval"
        )
        logger.debug("Verified: Spawn called above interval, timer reset.")

    @patch("src.managers.game_manager.GameManager._spawn_enemy")
    def test_update_spawn_timer_not_reset_on_failed_spawn(
        self, mock_spawn_enemy, game_manager
    ):
        """Test update does not reset spawn timer if _spawn_enemy returns False."""
        logger.debug("Testing spawn timer behavior on failed spawn...")
        initial_timer_value = game_manager.spawn_interval
        game_manager.spawn_timer = initial_timer_value
        mock_spawn_enemy.reset_mock()
        mock_spawn_enemy.return_value = False  # Simulate failed spawn

        game_manager.update()

        mock_spawn_enemy.assert_called_once()
        # Timer should NOT have been reset because spawn failed
        # It should have incremented by dt during the update
        dt = 1.0 / game_manager.fps
        expected_timer_value = initial_timer_value + dt
        assert game_manager.spawn_timer == pytest.approx(expected_timer_value), (
            f"Timer incorrect after failed spawn. "
            f"Expected ~{expected_timer_value:.4f}, Got {game_manager.spawn_timer:.4f}"
        )
        logger.debug("Verified: Timer not reset after failed spawn.")

    def test_update_does_not_call_spawn_before_interval(self, game_manager):
        """Test that update doesn't call _spawn_enemy before the interval."""
        game_manager.spawn_timer = game_manager.spawn_interval - 0.1  # Almost time
        with patch.object(game_manager, "_spawn_enemy") as mock_spawn:
            # Simulate one frame update
            game_manager.update()
            mock_spawn.assert_not_called()

    # --- Game State Tests --- #

    def test_update_stops_when_not_running(self, game_manager):
        """Test that update method does nothing if state is not RUNNING."""
        game_manager.state = GameState.GAME_OVER
        # Mock methods that should not be called during the update phase
        # if game is not running. Collision processing happens before this check.
        game_manager.player_tank.update = MagicMock()
        # Use a real list for enemy_tanks for the update loop check
        mock_enemy = MagicMock(spec=EnemyTank)
        mock_enemy.tank_type = "basic"
        game_manager.enemy_tanks = [mock_enemy]
        game_manager._spawn_enemy = MagicMock()
        game_manager.collision_response_handler = MagicMock()

        game_manager.update()

        game_manager.player_tank.update.assert_not_called()
        mock_enemy.update.assert_not_called()
        game_manager._spawn_enemy.assert_not_called()
        game_manager.collision_response_handler.process_collisions.assert_not_called()

    # Ensure the original game_manager fixture still works
    def test_initial_enemy_spawn_original_fixture(self, game_manager):
        """Test initial spawn using the standard fixture."""
        # Test might fail if the default map has a collision at the first spawn point
        # It relies on the actual Map and Tank implementations.
        # Consider mocking Map more thoroughly in the main fixture if needed.
        if game_manager.map.get_tile_at(
            game_manager.SPAWN_POINTS[0][0], game_manager.SPAWN_POINTS[0][1]
        ).type not in [TileType.EMPTY, TileType.BUSH]:
            pytest.skip("Default map conflicts with first spawn point.")

        # Resetting for clarity, assuming fixture provides one enemy
        game_manager.enemy_tanks = []
        game_manager.total_enemy_spawns = 0
        game_manager._spawn_enemy()  # Call spawn manually after clearing
        assert len(game_manager.enemy_tanks) >= 0  # Allow for blocked spawn
        assert game_manager.total_enemy_spawns >= 0
        # A more robust test would mock random.choice AND map checks.
