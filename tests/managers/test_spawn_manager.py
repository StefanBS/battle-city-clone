import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.managers.spawn_manager import SpawnManager
from src.core.enemy_tank import EnemyTank
from src.utils.constants import TILE_SIZE, GRID_WIDTH


class TestSpawnManager:
    """Unit test cases for the SpawnManager class."""

    SPAWN_POINTS = [
        (3, 1),
        (GRID_WIDTH // 2, 1),
        (GRID_WIDTH - 4, 1),
    ]

    @pytest.fixture
    def mock_texture_manager(self):
        """Create a mock TextureManager."""
        mock_tm = MagicMock()
        mock_tm.get_sprite.return_value = MagicMock(spec=pygame.Surface)
        return mock_tm

    @pytest.fixture
    def mock_player_tank(self):
        """Create a mock player tank positioned away from spawn points."""
        player = MagicMock()
        # Place player at the bottom of the map, far from spawn points
        player.rect = pygame.Rect(
            (GRID_WIDTH // 2 - 1) * TILE_SIZE,
            (16 - 2) * TILE_SIZE,
            TILE_SIZE,
            TILE_SIZE,
        )
        return player

    @pytest.fixture
    def mock_game_map(self):
        """Create a mock game map with no collidable tiles."""
        game_map = MagicMock()
        game_map.get_collidable_tiles.return_value = []
        return game_map

    @pytest.fixture
    def spawn_manager(self, mock_texture_manager, mock_player_tank, mock_game_map):
        """Create a SpawnManager instance for testing."""
        pygame.init()
        manager = SpawnManager(
            tile_size=TILE_SIZE,
            texture_manager=mock_texture_manager,
            spawn_points=self.SPAWN_POINTS,
            max_spawns=5,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
            game_map=mock_game_map,
        )
        yield manager
        pygame.quit()

    def test_initial_spawn(self, spawn_manager):
        """Test that the constructor spawns one enemy."""
        assert len(spawn_manager.enemy_tanks) == 1
        assert spawn_manager.total_enemy_spawns == 1

    @patch("random.choice")
    def test_spawn_enemy_adds_enemy(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn_enemy adds an enemy tank when the spot is clear."""
        mock_random_choice.return_value = self.SPAWN_POINTS[0]
        mock_game_map.get_collidable_tiles.return_value = []
        # Clear state from initial spawn
        spawn_manager.enemy_tanks = []
        spawn_manager.total_enemy_spawns = 0

        result = spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)

        assert result is True
        assert len(spawn_manager.enemy_tanks) == 1
        assert spawn_manager.total_enemy_spawns == 1

    @patch("random.choice")
    def test_spawn_enemy_respects_max(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn_enemy respects the maximum spawn limit."""
        mock_random_choice.return_value = self.SPAWN_POINTS[0]
        mock_game_map.get_collidable_tiles.return_value = []
        spawn_manager.total_enemy_spawns = spawn_manager.max_enemy_spawns

        initial_enemies = len(spawn_manager.enemy_tanks)
        result = spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)

        assert result is False
        assert len(spawn_manager.enemy_tanks) == initial_enemies

    @patch("random.choice")
    def test_spawn_enemy_avoids_map_collision(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn_enemy avoids spawning on map collision tiles."""
        spawn_point_grid = self.SPAWN_POINTS[0]
        mock_random_choice.return_value = spawn_point_grid
        spawn_x = spawn_point_grid[0] * TILE_SIZE
        spawn_y = spawn_point_grid[1] * TILE_SIZE
        colliding_tile = pygame.Rect(spawn_x, spawn_y, TILE_SIZE, TILE_SIZE)
        mock_game_map.get_collidable_tiles.return_value = [colliding_tile]

        initial_enemies = len(spawn_manager.enemy_tanks)
        initial_spawns = spawn_manager.total_enemy_spawns
        result = spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)

        assert result is False
        assert len(spawn_manager.enemy_tanks) == initial_enemies
        assert spawn_manager.total_enemy_spawns == initial_spawns

    @patch("random.choice")
    def test_spawn_enemy_avoids_tank_collision(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn_enemy avoids spawning on other tanks."""
        spawn_point_grid = self.SPAWN_POINTS[0]
        mock_random_choice.return_value = spawn_point_grid
        spawn_x = spawn_point_grid[0] * TILE_SIZE
        spawn_y = spawn_point_grid[1] * TILE_SIZE
        mock_game_map.get_collidable_tiles.return_value = []

        existing_enemy = MagicMock(spec=EnemyTank)
        existing_enemy.rect = pygame.Rect(spawn_x, spawn_y, TILE_SIZE, TILE_SIZE)
        existing_enemy.tank_type = "basic"
        spawn_manager.enemy_tanks = [existing_enemy]
        spawn_manager.total_enemy_spawns = 1

        result = spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)

        assert result is False
        assert len(spawn_manager.enemy_tanks) == 1
        assert spawn_manager.total_enemy_spawns == 1

    def test_update_spawns_on_interval(
        self, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that update triggers spawn when timer reaches the interval."""
        spawn_manager.spawn_timer = spawn_manager.spawn_interval

        with patch.object(
            spawn_manager, "spawn_enemy", return_value=True
        ) as mock_spawn:
            spawn_manager.update(0.1, mock_player_tank, mock_game_map)
            mock_spawn.assert_called_once_with(mock_player_tank, mock_game_map)

        # Timer should be reset after successful spawn
        # (We patched spawn_enemy so we check timer logic directly)

    @patch("random.choice")
    def test_update_resets_timer_on_success(
        self,
        mock_random_choice,
        spawn_manager,
        mock_player_tank,
        mock_game_map,
    ):
        """Test that update resets timer when spawn succeeds."""
        # Use a different spawn point than the initial spawn to avoid collision
        mock_random_choice.return_value = self.SPAWN_POINTS[2]
        spawn_manager.spawn_timer = spawn_manager.spawn_interval
        mock_game_map.get_collidable_tiles.return_value = []
        # Clear existing enemies so spawn point is clear
        spawn_manager.enemy_tanks = []
        spawn_manager.total_enemy_spawns = 0

        spawn_manager.update(0.0, mock_player_tank, mock_game_map)

        assert spawn_manager.spawn_timer == pytest.approx(0.0)

    def test_update_no_reset_on_failed_spawn(
        self, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that update does not reset timer if spawn fails."""
        initial_timer = spawn_manager.spawn_interval
        spawn_manager.spawn_timer = initial_timer

        with patch.object(
            spawn_manager, "spawn_enemy", return_value=False
        ) as mock_spawn:
            dt = 0.1
            spawn_manager.update(dt, mock_player_tank, mock_game_map)
            mock_spawn.assert_called_once()

        # Timer should have been incremented by dt, but NOT reset
        expected = initial_timer + dt
        assert spawn_manager.spawn_timer == pytest.approx(expected)

    def test_update_no_spawn_before_interval(
        self, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that update doesn't call spawn_enemy before the interval."""
        spawn_manager.spawn_timer = 0.0

        with patch.object(spawn_manager, "spawn_enemy") as mock_spawn:
            spawn_manager.update(0.1, mock_player_tank, mock_game_map)
            mock_spawn.assert_not_called()

    def test_reset(self, spawn_manager, mock_player_tank, mock_game_map):
        """Test that reset clears state and does an initial spawn."""
        # Simulate some state accumulation
        spawn_manager.total_enemy_spawns = 3
        spawn_manager.spawn_timer = 4.5
        spawn_manager.enemy_tanks = [MagicMock(), MagicMock()]

        spawn_manager.reset(mock_player_tank, mock_game_map)

        assert spawn_manager.spawn_timer == 0.0
        # reset does initial spawn, so should have 1 enemy and 1 spawn count
        assert len(spawn_manager.enemy_tanks) == 1
        assert spawn_manager.total_enemy_spawns == 1
