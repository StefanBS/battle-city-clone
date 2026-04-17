import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.game_manager import GameManager
from src.utils.constants import (
    PowerUpType,
    HELMET_INVINCIBILITY_DURATION,
    CLOCK_FREEZE_DURATION,
    TankType,
    EffectType,
    TILE_SIZE,
)
from src.states.game_state import GameState


class TestPowerUpEffects:
    @pytest.fixture
    def game(self):
        gm = MagicMock(spec=GameManager)
        gm._apply_power_up = GameManager._apply_power_up.__get__(gm)
        gm._apply_helmet = GameManager._apply_helmet.__get__(gm)
        gm._apply_extra_life = GameManager._apply_extra_life.__get__(gm)
        gm._apply_bomb = GameManager._apply_bomb.__get__(gm)
        gm.state = GameState.RUNNING
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.is_invincible = False
        gm._test_player = mock_player
        gm.player_manager = MagicMock()
        gm.player_manager.get_active_players.return_value = [mock_player]
        gm.spawn_manager = MagicMock()
        gm.spawn_manager.enemy_tanks = []
        gm.effect_manager = MagicMock()
        gm.power_up_manager = MagicMock()
        return gm

    def test_helmet_grants_invincibility(self, game):
        game._apply_power_up(PowerUpType.HELMET)
        game._test_player.activate_invincibility.assert_called_once_with(
            HELMET_INVINCIBILITY_DURATION
        )

    def test_extra_life_increments_lives(self, game):
        game._apply_power_up(PowerUpType.EXTRA_LIFE)
        assert game._test_player.lives == 4

    def test_bomb_destroys_all_enemies(self, game):
        enemies = []
        for tt in [TankType.BASIC, TankType.FAST, TankType.POWER]:
            e = MagicMock()
            e.tank_type = tt
            e.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
            enemies.append(e)
        game.spawn_manager.enemy_tanks = list(enemies)
        game._apply_power_up(PowerUpType.BOMB)
        assert game.spawn_manager.remove_enemy.call_count == 3

    def test_bomb_spawns_explosions(self, game):
        enemy = MagicMock()
        enemy.tank_type = TankType.BASIC
        enemy.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
        game.spawn_manager.enemy_tanks = [enemy]
        game._apply_power_up(PowerUpType.BOMB)
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
        game._apply_power_up(PowerUpType.BOMB)
        game.spawn_manager.remove_enemy.assert_called_once_with(carrier)
        game.power_up_manager.spawn_power_up.assert_not_called()

    def test_power_up_not_applied_on_game_over(self, game):
        game.state = GameState.GAME_OVER
        game._apply_power_up(PowerUpType.EXTRA_LIFE)
        assert game._test_player.lives == 3

    def test_unknown_power_up_type_is_noop(self, game):
        game._apply_power_up(PowerUpType.STAR)
        assert game._test_player.lives == 3

    def test_helmet_overrides_respawn_invincibility(self, game):
        game._test_player.is_invincible = True
        game._apply_power_up(PowerUpType.HELMET)
        game._test_player.activate_invincibility.assert_called_once_with(
            HELMET_INVINCIBILITY_DURATION
        )


class TestClockEffect:
    @pytest.fixture
    def game(self):
        gm = MagicMock(spec=GameManager)
        gm._apply_power_up = GameManager._apply_power_up.__get__(gm)
        gm._apply_clock = GameManager._apply_clock.__get__(gm)
        gm.state = GameState.RUNNING
        gm.freeze_timer = 0.0
        mock_player = MagicMock()
        mock_player.lives = 3
        gm.player_manager = MagicMock()
        gm.player_manager.get_active_players.return_value = [mock_player]
        return gm

    def test_clock_sets_freeze_timer(self, game):
        game._apply_power_up(PowerUpType.CLOCK)
        assert game.freeze_timer == CLOCK_FREEZE_DURATION

    def test_clock_recollection_resets_timer(self, game):
        game.freeze_timer = 3.0
        game._apply_power_up(PowerUpType.CLOCK)
        assert game.freeze_timer == CLOCK_FREEZE_DURATION


class TestShovelDelegation:
    """Shovel state machine lives in PowerUpManager; GameManager just delegates."""

    @pytest.fixture
    def game(self):
        gm = MagicMock(spec=GameManager)
        gm._apply_power_up = GameManager._apply_power_up.__get__(gm)
        gm._apply_shovel = GameManager._apply_shovel.__get__(gm)
        gm.state = GameState.RUNNING
        mock_player = MagicMock()
        gm.player_manager = MagicMock()
        gm.player_manager.get_active_players.return_value = [mock_player]
        gm.power_up_manager = MagicMock()
        return gm

    def test_apply_shovel_delegates_to_power_up_manager(self, game):
        game._apply_power_up(PowerUpType.SHOVEL)
        game.power_up_manager.apply_shovel.assert_called_once_with()
