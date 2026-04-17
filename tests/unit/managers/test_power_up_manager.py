import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.power_up_manager import PowerUpManager
from src.core.tile import BrickVariant, TileType
from src.utils.constants import (
    POWERUP_TIMEOUT,
    PowerUpType,
    SHOVEL_DURATION,
    SHOVEL_FLASH_INTERVAL,
    SHOVEL_WARNING_DURATION,
    TILE_SIZE,
)


class TestPowerUpManager:
    @pytest.fixture
    def mock_game_map(self):
        game_map = MagicMock()
        game_map.width = 32
        game_map.height = 32
        game_map.tile_size = 16
        game_map.grid_to_pixels.side_effect = lambda gx, gy: (gx * 16, gy * 16)
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
        assert manager.active_power_ups == []

    def test_spawn_creates_power_up(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        assert len(manager.active_power_ups) == 1

    def test_spawn_multiple_allowed(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        manager.spawn_power_up(mock_player_tank, [])
        assert len(manager.active_power_ups) == 2

    def test_spawn_with_specific_type(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [], power_up_type=PowerUpType.BOMB)
        assert manager.active_power_ups[0].power_up_type == PowerUpType.BOMB

    def test_spawn_at_explicit_position(self, manager):
        manager.spawn_power_up(position=(64, 96), power_up_type=PowerUpType.STAR)
        pu = manager.active_power_ups[0]
        assert pu.x == 64
        assert pu.y == 96
        assert pu.power_up_type == PowerUpType.STAR

    def test_get_power_ups_returns_list(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        result = manager.get_power_ups()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_get_power_ups_returns_empty_when_none(self, manager):
        assert manager.get_power_ups() == []

    def test_collect_specific_power_up(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [], power_up_type=PowerUpType.CLOCK)
        pu = manager.active_power_ups[0]
        result = manager.collect_power_up(pu)
        assert result == PowerUpType.CLOCK
        assert pu not in manager.active_power_ups

    def test_collect_returns_none_for_missing(self, manager):
        from src.core.power_up import PowerUp

        fake_pu = MagicMock(spec=PowerUp)
        result = manager.collect_power_up(fake_pu)
        assert result is None

    def test_collect_removes_only_specified(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [], power_up_type=PowerUpType.CLOCK)
        manager.spawn_power_up(mock_player_tank, [], power_up_type=PowerUpType.BOMB)
        pu_clock = manager.active_power_ups[0]
        manager.collect_power_up(pu_clock)
        assert len(manager.active_power_ups) == 1
        assert manager.active_power_ups[0].power_up_type == PowerUpType.BOMB

    def test_update_clears_timed_out_power_up(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        manager.update(POWERUP_TIMEOUT + 0.1)
        assert len(manager.active_power_ups) == 0

    def test_update_keeps_active_power_up(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [])
        manager.update(1.0)
        assert len(manager.active_power_ups) == 1

    def test_update_removes_only_timed_out(self, manager, mock_player_tank):
        manager.spawn_power_up(mock_player_tank, [], power_up_type=PowerUpType.CLOCK)
        manager.spawn_power_up(mock_player_tank, [], power_up_type=PowerUpType.BOMB)
        # advance past timeout for one
        manager.active_power_ups[0].update(POWERUP_TIMEOUT + 0.1)
        manager.update(0.0)
        assert len(manager.active_power_ups) == 1

    def test_spawn_avoids_occupied_positions(self, manager, mock_player_tank):
        mock_player_tank.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        manager.spawn_power_up(mock_player_tank, [])
        assert len(manager.active_power_ups) == 1
        pu_rect = manager.active_power_ups[0].rect
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
        assert len(manager.active_power_ups) == 0


class TestShovelEffect:
    @pytest.fixture
    def manager(self, mock_texture_manager):
        game_map = MagicMock()
        mock_tiles = []
        for _ in range(4):
            t = MagicMock()
            t.type = TileType.BRICK
            t.brick_variant = BrickVariant.FULL
            mock_tiles.append(t)
        game_map.get_base_surrounding_tiles.return_value = mock_tiles
        return PowerUpManager(mock_texture_manager, game_map)

    def test_initial_shovel_state(self, manager):
        assert manager.shovel_timer == 0.0

    def test_shovel_fortifies_base(self, manager):
        manager.apply_shovel()
        assert manager.shovel_timer == SHOVEL_DURATION
        for call in manager._game_map.set_tile_type.call_args_list:
            assert call.args[1] == TileType.STEEL

    def test_shovel_stores_originals(self, manager):
        manager.apply_shovel()
        assert len(manager._shovel_original_tiles) == 4
        for _, orig_type in manager._shovel_original_tiles:
            assert orig_type == TileType.BRICK

    def test_shovel_reverts_after_duration(self, manager):
        manager.apply_shovel()
        manager._game_map.set_tile_type.reset_mock()
        manager.update(SHOVEL_DURATION + 0.1)
        assert manager.shovel_timer <= 0
        for call in manager._game_map.set_tile_type.call_args_list:
            assert call.args[1] == TileType.BRICK

    def test_shovel_recollection_resets_timer(self, manager):
        manager.apply_shovel()
        original_tiles = manager._shovel_original_tiles
        manager.shovel_timer = 5.0
        manager._game_map.set_tile_type.reset_mock()
        manager.apply_shovel()
        assert manager.shovel_timer == SHOVEL_DURATION
        assert manager._shovel_original_tiles is original_tiles
        manager._game_map.set_tile_type.assert_not_called()

    def test_shovel_flashes_during_warning(self, manager):
        manager.apply_shovel()
        manager._game_map.set_tile_type.reset_mock()
        manager.update(SHOVEL_DURATION - SHOVEL_WARNING_DURATION + 0.5)
        manager.update(SHOVEL_FLASH_INTERVAL + 0.01)
        assert manager._shovel_flash_showing_steel is False
        last_call = manager._game_map.set_tile_type.call_args_list[-1]
        assert last_call.args[1] == TileType.BRICK
