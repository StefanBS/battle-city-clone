import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.power_up_manager import PowerUpManager
from src.core.tile import TileType
from src.utils.constants import PowerUpType, TILE_SIZE, POWERUP_TIMEOUT


class TestPowerUpManager:
    @pytest.fixture
    def mock_game_map(self):
        game_map = MagicMock()
        game_map.width = 32
        game_map.height = 32
        game_map.tile_size = 16
        # All tiles are EMPTY (None mimics "no blocking tile")
        game_map.tiles = [[None for _ in range(32)] for _ in range(32)]
        return game_map

    @pytest.fixture
    def mock_player_tank(self):
        tank = MagicMock()
        tank.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        return tank

    @pytest.fixture
    def manager(self, mock_texture_manager, mock_game_map):
        return PowerUpManager(mock_texture_manager, mock_game_map)

    def test_initial_state(self, manager):
        assert manager.active_power_up is None

    def test_spawn_creates_power_up(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        assert manager.active_power_up is not None

    def test_spawn_only_one_at_a_time(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        first = manager.active_power_up
        manager.spawn_power_up(mock_player_tank, [])
        assert manager.active_power_up is first

    def test_spawn_with_specific_type(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [], power_up_type=PowerUpType.BOMB)
        assert manager.active_power_up.power_up_type == PowerUpType.BOMB

    def test_get_power_up_returns_active(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        assert manager.get_power_up() is manager.active_power_up

    def test_get_power_up_returns_none_when_empty(self, manager):
        assert manager.get_power_up() is None

    def test_collect_returns_type(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [], power_up_type=PowerUpType.CLOCK)
        result = manager.collect_power_up()
        assert result == PowerUpType.CLOCK

    def test_collect_clears_active(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        manager.collect_power_up()
        assert manager.active_power_up is None

    def test_collect_returns_none_when_empty(self, manager):
        assert manager.collect_power_up() is None

    def test_update_clears_timed_out_power_up(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        manager.update(POWERUP_TIMEOUT + 0.1)
        assert manager.active_power_up is None

    def test_update_keeps_active_power_up(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        manager.update(1.0)
        assert manager.active_power_up is not None

    def test_spawn_avoids_occupied_positions(self, manager, mock_player_tank):
        mock_player_tank.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        manager.spawn_power_up(mock_player_tank, [])
        assert manager.active_power_up is not None
        pu_rect = manager.active_power_up.rect
        assert not pu_rect.colliderect(mock_player_tank.rect)

    def test_spawn_skips_when_no_valid_position(self, mock_texture_manager):
        """When all tiles are non-empty, spawn has nowhere to place the power-up."""
        game_map = MagicMock()
        game_map.width = 4
        game_map.height = 4
        game_map.tile_size = 16
        brick_tile = MagicMock()
        brick_tile.type = TileType.BRICK
        game_map.tiles = [[brick_tile for _ in range(4)] for _ in range(4)]

        manager = PowerUpManager(mock_texture_manager, game_map)
        player = MagicMock()
        player.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        manager.spawn_power_up(player, [])
        assert manager.active_power_up is None
