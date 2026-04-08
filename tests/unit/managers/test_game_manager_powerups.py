import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.game_manager import GameManager
from src.utils.constants import (
    PowerUpType,
    HELMET_INVINCIBILITY_DURATION,
    CLOCK_FREEZE_DURATION,
    SHOVEL_DURATION,
    SHOVEL_WARNING_DURATION,
    SHOVEL_FLASH_INTERVAL,
    TankType,
    EffectType,
    TILE_SIZE,
)
from src.states.game_state import GameState
from src.core.tile import TileType


class TestPowerUpEffects:
    @pytest.fixture
    def game(self):
        gm = MagicMock(spec=GameManager)
        gm._apply_power_up = GameManager._apply_power_up.__get__(gm)
        gm._apply_helmet = GameManager._apply_helmet.__get__(gm)
        gm._apply_extra_life = GameManager._apply_extra_life.__get__(gm)
        gm._apply_bomb = GameManager._apply_bomb.__get__(gm)
        gm._add_score = GameManager._add_score.__get__(gm)
        gm.state = GameState.RUNNING
        gm.score = 0
        gm.player_tank = MagicMock()
        gm.player_tank.lives = 3
        gm.player_tank.is_invincible = False
        gm.spawn_manager = MagicMock()
        gm.spawn_manager.enemy_tanks = []
        gm.effect_manager = MagicMock()
        gm.power_up_manager = MagicMock()
        return gm

    def test_helmet_grants_invincibility(self, game):
        game._apply_power_up(PowerUpType.HELMET)
        game.player_tank.activate_invincibility.assert_called_once_with(
            HELMET_INVINCIBILITY_DURATION
        )

    def test_extra_life_increments_lives(self, game):
        game._apply_power_up(PowerUpType.EXTRA_LIFE)
        assert game.player_tank.lives == 4

    def test_bomb_destroys_all_enemies(self, game):
        enemies = []
        for tt in [TankType.BASIC, TankType.FAST, TankType.POWER]:
            e = MagicMock()
            e.tank_type = tt
            e.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
            enemies.append(e)
        game.spawn_manager.enemy_tanks = list(enemies)
        game._apply_bomb()
        assert game.spawn_manager.remove_enemy.call_count == 3
        assert game.score == 0

    def test_bomb_spawns_explosions(self, game):
        enemy = MagicMock()
        enemy.tank_type = TankType.BASIC
        enemy.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
        game.spawn_manager.enemy_tanks = [enemy]
        game._apply_bomb()
        game.effect_manager.spawn.assert_called_once_with(
            EffectType.LARGE_EXPLOSION,
            float(enemy.rect.centerx),
            float(enemy.rect.centery),
        )

    def test_bomb_does_not_trigger_carrier_powerup(self, game):
        carrier = MagicMock()
        carrier.tank_type = TankType.BASIC
        carrier.is_carrier = True
        carrier.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
        game.spawn_manager.enemy_tanks = [carrier]
        game._apply_bomb()
        game.spawn_manager.remove_enemy.assert_called_once_with(carrier)
        game.power_up_manager.spawn_power_up.assert_not_called()

    def test_power_up_not_applied_on_game_over(self, game):
        game.state = GameState.GAME_OVER
        game._apply_power_up(PowerUpType.EXTRA_LIFE)
        assert game.player_tank.lives == 3

    def test_unknown_power_up_type_is_noop(self, game):
        game._apply_power_up(PowerUpType.STAR)
        assert game.player_tank.lives == 3

    def test_helmet_overrides_respawn_invincibility(self, game):
        game.player_tank.is_invincible = True
        game._apply_power_up(PowerUpType.HELMET)
        game.player_tank.activate_invincibility.assert_called_once_with(
            HELMET_INVINCIBILITY_DURATION
        )


class TestClockEffect:
    @pytest.fixture
    def game(self):
        gm = MagicMock(spec=GameManager)
        gm._apply_power_up = GameManager._apply_power_up.__get__(gm)
        gm._apply_clock = GameManager._apply_clock.__get__(gm)
        gm.state = GameState.RUNNING
        gm.score = 0
        gm.freeze_timer = 0.0
        gm.player_tank = MagicMock()
        gm.player_tank.lives = 3
        return gm

    def test_clock_sets_freeze_timer(self, game):
        game._apply_power_up(PowerUpType.CLOCK)
        assert game.freeze_timer == CLOCK_FREEZE_DURATION

    def test_clock_recollection_resets_timer(self, game):
        game.freeze_timer = 3.0
        game._apply_power_up(PowerUpType.CLOCK)
        assert game.freeze_timer == CLOCK_FREEZE_DURATION


class TestShovelEffect:
    @pytest.fixture
    def game(self):
        gm = MagicMock(spec=GameManager)
        gm._apply_power_up = GameManager._apply_power_up.__get__(gm)
        gm._apply_shovel = GameManager._apply_shovel.__get__(gm)
        gm._tick_shovel = GameManager._tick_shovel.__get__(gm)
        gm.state = GameState.RUNNING
        gm.score = 0
        gm.freeze_timer = 0.0
        gm.shovel_timer = 0.0
        gm._shovel_original_tiles = []
        gm._shovel_flash_timer = 0.0
        gm._shovel_flash_showing_steel = True
        gm.player_tank = MagicMock()
        gm.player_tank.lives = 3
        mock_tiles = []
        for _ in range(4):
            t = MagicMock()
            t.type = TileType.BRICK
            t.brick_variant = "full"
            mock_tiles.append(t)
        gm.map = MagicMock()
        gm.map.get_base_surrounding_tiles.return_value = mock_tiles
        gm.map.set_tile_type = MagicMock()
        return gm

    def test_shovel_fortifies_base(self, game):
        game._apply_power_up(PowerUpType.SHOVEL)
        assert game.shovel_timer == SHOVEL_DURATION
        calls = game.map.set_tile_type.call_args_list
        for call in calls:
            assert call.args[1] == TileType.STEEL

    def test_shovel_stores_originals(self, game):
        game._apply_power_up(PowerUpType.SHOVEL)
        assert len(game._shovel_original_tiles) == 4
        for tile, orig_type in game._shovel_original_tiles:
            assert orig_type == TileType.BRICK

    def test_shovel_reverts_after_duration(self, game):
        game._apply_power_up(PowerUpType.SHOVEL)
        game.map.set_tile_type.reset_mock()
        game._tick_shovel(SHOVEL_DURATION + 0.1)
        assert game.shovel_timer <= 0
        calls = game.map.set_tile_type.call_args_list
        for call in calls:
            assert call.args[1] == TileType.BRICK

    def test_shovel_recollection_resets_timer(self, game):
        game._apply_power_up(PowerUpType.SHOVEL)
        original_tiles = game._shovel_original_tiles
        game.shovel_timer = 5.0
        game.map.set_tile_type.reset_mock()
        game._apply_shovel()
        assert game.shovel_timer == SHOVEL_DURATION
        assert game._shovel_original_tiles is original_tiles
        game.map.set_tile_type.assert_not_called()

    def test_shovel_flashes_during_warning(self, game):
        game._apply_power_up(PowerUpType.SHOVEL)
        game.map.set_tile_type.reset_mock()
        # Advance into warning phase
        game._tick_shovel(SHOVEL_DURATION - SHOVEL_WARNING_DURATION + 0.5)
        # Advance past one flash interval to trigger toggle
        game._tick_shovel(SHOVEL_FLASH_INTERVAL + 0.01)
        # Verify toggle happened: tiles set to original type (BRICK)
        assert game._shovel_flash_showing_steel is False
        last_call = game.map.set_tile_type.call_args_list[-1]
        assert last_call.args[1] == TileType.BRICK
