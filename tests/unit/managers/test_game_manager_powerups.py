import pytest
import pygame
from unittest.mock import MagicMock
from src.core.map import Map
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
    def manager(self, mock_texture_manager):
        """Real PowerUpManager with mocked deps.

        ``apply_shovel`` is stubbed because the SHOVEL test only verifies
        that ``apply()`` delegates — the shovel side-effects on the map
        are covered elsewhere.
        """
        m = PowerUpManager(mock_texture_manager, MagicMock(spec=Map))
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
        effect_manager.spawn_at_rect.assert_called_once_with(
            EffectType.LARGE_EXPLOSION, enemy.rect
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
    def game(self, game_manager):
        """Real GameManager from the shared fixture with power_up_manager
        swapped for a mock we can assert on. State is forced to RUNNING
        because `_reset_game` leaves the manager mid-transition."""
        game_manager.state = GameState.RUNNING
        game_manager.power_up_manager = MagicMock()
        return game_manager

    @pytest.fixture
    def player(self, game):
        p = MagicMock()
        p.lives = 3
        game.player_manager.get_active_players.return_value = [p]
        return p

    def test_delegates_to_power_up_manager(self, game, player):
        game._apply_power_up(PowerUpType.EXTRA_LIFE)
        game.power_up_manager.apply.assert_called_once_with(
            PowerUpType.EXTRA_LIFE,
            player,
            game.spawn_manager,
            game.effect_manager,
        )

    def test_skipped_when_not_running(self, game, player):
        game.state = GameState.GAME_OVER
        game._apply_power_up(PowerUpType.EXTRA_LIFE)
        game.power_up_manager.apply.assert_not_called()

    def test_falls_back_to_first_active_player(self, game, player):
        game._apply_power_up(PowerUpType.HELMET)
        args = game.power_up_manager.apply.call_args.args
        assert args[1] is player

    def test_noop_when_no_active_players(self, game):
        game.player_manager.get_active_players.return_value = []
        game._apply_power_up(PowerUpType.HELMET)
        game.power_up_manager.apply.assert_not_called()
