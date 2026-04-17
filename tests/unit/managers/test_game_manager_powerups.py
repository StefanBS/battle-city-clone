import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.game_manager import GameManager
from src.managers.power_up_manager import PowerUpManager
from src.utils.constants import (
    PowerUpType,
    HELMET_INVINCIBILITY_DURATION,
    CLOCK_FREEZE_DURATION,
    TankType,
    EffectType,
    TILE_SIZE,
)
from src.states.game_state import GameState


class TestPowerUpManagerApply:
    """Power-up effect dispatch lives on PowerUpManager.apply()."""

    @pytest.fixture
    def player(self):
        p = MagicMock()
        p.lives = 3
        p.is_invincible = False
        return p

    @pytest.fixture
    def spawn_manager(self):
        sm = MagicMock()
        sm.enemy_tanks = []
        return sm

    @pytest.fixture
    def effect_manager(self):
        return MagicMock()

    @pytest.fixture
    def manager(self):
        # apply() does not read any PowerUpManager state except apply_shovel(),
        # which is tested separately; a plain MagicMock-backed method is fine.
        m = MagicMock(spec=PowerUpManager)
        m.apply = PowerUpManager.apply.__get__(m)
        m._detonate_bomb = PowerUpManager._detonate_bomb
        m.apply_shovel = MagicMock()
        return m

    def test_helmet_grants_invincibility(
        self, manager, player, spawn_manager, effect_manager
    ):
        manager.apply(PowerUpType.HELMET, player, spawn_manager, effect_manager)
        player.activate_invincibility.assert_called_once_with(
            HELMET_INVINCIBILITY_DURATION
        )

    def test_extra_life_increments_lives(
        self, manager, player, spawn_manager, effect_manager
    ):
        manager.apply(PowerUpType.EXTRA_LIFE, player, spawn_manager, effect_manager)
        assert player.lives == 4

    def test_bomb_destroys_all_enemies(
        self, manager, player, spawn_manager, effect_manager
    ):
        enemies = []
        for tt in [TankType.BASIC, TankType.FAST, TankType.POWER]:
            e = MagicMock()
            e.tank_type = tt
            e.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
            enemies.append(e)
        spawn_manager.enemy_tanks = list(enemies)
        manager.apply(PowerUpType.BOMB, player, spawn_manager, effect_manager)
        assert spawn_manager.remove_enemy.call_count == 3

    def test_bomb_spawns_explosions(
        self, manager, player, spawn_manager, effect_manager
    ):
        enemy = MagicMock()
        enemy.tank_type = TankType.BASIC
        enemy.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
        spawn_manager.enemy_tanks = [enemy]
        manager.apply(PowerUpType.BOMB, player, spawn_manager, effect_manager)
        effect_manager.spawn.assert_called_once_with(
            EffectType.LARGE_EXPLOSION,
            float(enemy.rect.centerx),
            float(enemy.rect.centery),
        )

    def test_bomb_does_not_trigger_carrier_powerup(
        self, manager, player, spawn_manager, effect_manager
    ):
        carrier = MagicMock()
        carrier.tank_type = TankType.BASIC
        carrier.is_carrier = True
        carrier.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
        spawn_manager.enemy_tanks = [carrier]
        manager.apply(PowerUpType.BOMB, player, spawn_manager, effect_manager)
        spawn_manager.remove_enemy.assert_called_once_with(carrier)
        # The bomb path goes through spawn_manager.remove_enemy directly,
        # bypassing the carrier-drops-powerup behaviour (which lives in
        # GameManager's collision-response path, not in apply()).

    def test_clock_freezes_enemies(
        self, manager, player, spawn_manager, effect_manager
    ):
        manager.apply(PowerUpType.CLOCK, player, spawn_manager, effect_manager)
        spawn_manager.freeze.assert_called_once_with(CLOCK_FREEZE_DURATION)

    def test_shovel_delegates_to_apply_shovel(
        self, manager, player, spawn_manager, effect_manager
    ):
        manager.apply(PowerUpType.SHOVEL, player, spawn_manager, effect_manager)
        manager.apply_shovel.assert_called_once_with()

    def test_star_applies_to_player(
        self, manager, player, spawn_manager, effect_manager
    ):
        manager.apply(PowerUpType.STAR, player, spawn_manager, effect_manager)
        player.apply_star.assert_called_once_with()

    def test_helmet_overrides_respawn_invincibility(
        self, manager, player, spawn_manager, effect_manager
    ):
        player.is_invincible = True
        manager.apply(PowerUpType.HELMET, player, spawn_manager, effect_manager)
        player.activate_invincibility.assert_called_once_with(
            HELMET_INVINCIBILITY_DURATION
        )


class TestGameManagerApplyPowerUpDelegation:
    """GameManager._apply_power_up resolves the recipient and delegates."""

    @pytest.fixture
    def game(self):
        gm = MagicMock(spec=GameManager)
        gm._apply_power_up = GameManager._apply_power_up.__get__(gm)
        gm.state = GameState.RUNNING
        mock_player = MagicMock()
        mock_player.lives = 3
        gm._test_player = mock_player
        gm.player_manager = MagicMock()
        gm.player_manager.get_active_players.return_value = [mock_player]
        gm.spawn_manager = MagicMock()
        gm.effect_manager = MagicMock()
        gm.power_up_manager = MagicMock()
        return gm

    def test_delegates_to_power_up_manager(self, game):
        game._apply_power_up(PowerUpType.EXTRA_LIFE)
        game.power_up_manager.apply.assert_called_once_with(
            PowerUpType.EXTRA_LIFE,
            game._test_player,
            game.spawn_manager,
            game.effect_manager,
        )

    def test_skipped_when_not_running(self, game):
        game.state = GameState.GAME_OVER
        game._apply_power_up(PowerUpType.EXTRA_LIFE)
        game.power_up_manager.apply.assert_not_called()

    def test_falls_back_to_first_active_player(self, game):
        game._apply_power_up(PowerUpType.HELMET)
        args = game.power_up_manager.apply.call_args.args
        assert args[1] is game._test_player

    def test_noop_when_no_active_players(self, game):
        game.player_manager.get_active_players.return_value = []
        game._apply_power_up(PowerUpType.HELMET)
        game.power_up_manager.apply.assert_not_called()
