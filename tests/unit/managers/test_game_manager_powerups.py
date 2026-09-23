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
    POWERUP_COLLECT_POINTS,
    TILE_SIZE,
)
from src.managers.outcomes import EnemyDestroyed, PlayerDestroyed, PowerUpCollected
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
    def manager(self, mock_texture_manager):
        """Real PowerUpManager with mocked deps.

        ``apply_shovel`` is stubbed because the SHOVEL test only verifies
        that ``apply()`` delegates — the shovel side-effects on the map
        are covered elsewhere.
        """
        m = PowerUpManager(mock_texture_manager, MagicMock(spec=Map))
        m.apply_shovel = MagicMock()
        return m

    def test_helmet_grants_invincibility(self, manager, player, spawn_manager):
        manager.apply(PowerUpType.HELMET, player, spawn_manager)
        player.activate_invincibility.assert_called_once_with(
            HELMET_INVINCIBILITY_DURATION
        )

    def test_extra_life_increments_lives(self, manager, player, spawn_manager):
        manager.apply(PowerUpType.EXTRA_LIFE, player, spawn_manager)
        assert player.lives == 4

    def test_bomb_destroys_every_enemy(self, manager, player, spawn_manager):
        enemies = [MagicMock(), MagicMock(), MagicMock()]
        spawn_manager.enemy_tanks = list(enemies)
        outcomes = manager.apply(PowerUpType.BOMB, player, spawn_manager)
        assert outcomes == [EnemyDestroyed(e, by=None) for e in enemies]
        spawn_manager.remove_enemy.assert_not_called()

    def test_other_power_ups_cause_no_outcomes(self, manager, player, spawn_manager):
        assert manager.apply(PowerUpType.STAR, player, spawn_manager) == []

    def test_clock_freezes_enemies(self, manager, player, spawn_manager):
        manager.apply(PowerUpType.CLOCK, player, spawn_manager)
        spawn_manager.freeze.assert_called_once_with(CLOCK_FREEZE_DURATION)

    def test_shovel_delegates_to_apply_shovel(self, manager, player, spawn_manager):
        manager.apply(PowerUpType.SHOVEL, player, spawn_manager)
        manager.apply_shovel.assert_called_once_with()

    def test_star_applies_to_player(self, manager, player, spawn_manager):
        manager.apply(PowerUpType.STAR, player, spawn_manager)
        player.apply_star.assert_called_once_with()

    def test_helmet_overrides_respawn_invincibility(
        self, manager, player, spawn_manager
    ):
        player.is_invincible = True
        manager.apply(PowerUpType.HELMET, player, spawn_manager)
        player.activate_invincibility.assert_called_once_with(
            HELMET_INVINCIBILITY_DURATION
        )


class TestGameManagerApplyOutcomes:
    """GameManager._apply_outcomes is the one place outcomes take effect."""

    @pytest.fixture
    def game(self, game_manager):
        game_manager.state = GameState.RUNNING
        game_manager.power_up_manager = MagicMock(spec=PowerUpManager)
        game_manager.power_up_manager.apply.return_value = []
        game_manager.sound_manager = MagicMock()
        game_manager.effect_manager = MagicMock()
        game_manager.player_manager = MagicMock()
        game_manager.spawn_manager = MagicMock()
        enemies = game_manager.spawn_manager.enemy_tanks = []
        game_manager.spawn_manager.remove_enemy.side_effect = enemies.remove
        return game_manager

    @pytest.fixture
    def players(self, game):
        p1, p2 = MagicMock(player_id=1), MagicMock(player_id=2)
        game.player_manager.get_active_players.return_value = [p1, p2]
        return p1, p2

    @staticmethod
    def _enemy(game, tank_type=TankType.BASIC, is_carrier=False):
        enemy = MagicMock(tank_type=tank_type, is_carrier=is_carrier)
        enemy.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        game.spawn_manager.enemy_tanks.append(enemy)
        return enemy

    @pytest.mark.parametrize(
        "tank_type,points",
        [
            (TankType.BASIC, 100),
            (TankType.FAST, 200),
            (TankType.POWER, 300),
            (TankType.ARMOR, 400),
        ],
    )
    def test_enemy_destroyed_by_player(self, game, players, tank_type, points):
        enemy = self._enemy(game, tank_type)
        game._apply_outcomes([EnemyDestroyed(enemy, by=players[1])])
        assert enemy not in game.spawn_manager.enemy_tanks
        game.player_manager.add_score.assert_called_once_with(points, player_id=2)
        game.effect_manager.spawn_at_rect.assert_called_once_with(
            EffectType.LARGE_EXPLOSION, enemy.rect
        )
        game.sound_manager.play.assert_called_once_with("explosion")

    def test_enemy_destroyed_by_grenade_scores_nothing(self, game):
        enemy = self._enemy(game)
        game._apply_outcomes([EnemyDestroyed(enemy, by=None)])
        assert enemy not in game.spawn_manager.enemy_tanks
        game.player_manager.add_score.assert_not_called()
        game.sound_manager.play.assert_called_once_with("explosion")

    def test_enemy_destroyed_twice_applies_once(self, game, players):
        enemy = self._enemy(game)
        game._apply_outcomes(
            [EnemyDestroyed(enemy, by=players[0]), EnemyDestroyed(enemy, by=None)]
        )
        game.player_manager.add_score.assert_called_once_with(100, player_id=1)
        game.effect_manager.spawn_at_rect.assert_called_once()

    @pytest.mark.parametrize("by_player", [True, False])
    def test_carrier_drop_avoids_every_player(self, game, players, by_player):
        carrier = self._enemy(game, is_carrier=True)
        other = self._enemy(game)
        by = players[0] if by_player else None
        game._apply_outcomes([EnemyDestroyed(carrier, by=by)])
        game.power_up_manager.spawn_power_up.assert_called_once_with([*players, other])

    def test_player_destroyed(self, game, players):
        p1 = players[0]
        p1.rect = pygame.Rect(64, 64, TILE_SIZE, TILE_SIZE)
        explosion_at = []
        game.player_manager.handle_player_death.side_effect = lambda p: (
            explosion_at.append(
                game.effect_manager.spawn_at_rect.call_args.args[1].copy()
            )
        )
        game._apply_outcomes([PlayerDestroyed(p1)])
        game.player_manager.handle_player_death.assert_called_once_with(p1)
        game.sound_manager.play.assert_called_once_with("explosion")
        # The explosion is placed before the respawn moves the tank.
        assert explosion_at == [pygame.Rect(64, 64, TILE_SIZE, TILE_SIZE)]

    def test_power_up_collected(self, game, players):
        game._apply_outcomes([PowerUpCollected(PowerUpType.STAR, players[1])])
        game.player_manager.add_score.assert_called_once_with(
            POWERUP_COLLECT_POINTS, player_id=2
        )
        game.sound_manager.play.assert_called_once_with("powerup")
        game.power_up_manager.apply.assert_called_once_with(
            PowerUpType.STAR, players[1], game.spawn_manager
        )

    def test_two_power_ups_in_one_frame_both_applied(self, game, players):
        p1, p2 = players
        game._apply_outcomes(
            [
                PowerUpCollected(PowerUpType.STAR, p1),
                PowerUpCollected(PowerUpType.HELMET, p2),
            ]
        )
        assert [c.args[:2] for c in game.power_up_manager.apply.call_args_list] == [
            (PowerUpType.STAR, p1),
            (PowerUpType.HELMET, p2),
        ]

    def test_outcomes_caused_by_a_power_up_are_applied(self, game, players):
        enemy = self._enemy(game, is_carrier=True)
        game.power_up_manager.apply.return_value = [EnemyDestroyed(enemy, by=None)]
        game._apply_outcomes([PowerUpCollected(PowerUpType.BOMB, players[0])])
        assert enemy not in game.spawn_manager.enemy_tanks
        game.power_up_manager.spawn_power_up.assert_called_once()
        # Only the Power-Up's own points; the Grenade kill scores nothing.
        game.player_manager.add_score.assert_called_once_with(
            POWERUP_COLLECT_POINTS, player_id=1
        )
