"""Unit tests for Battle: one Stage's frame pipeline and outcomes, no window."""

import pytest
import pygame
from unittest.mock import MagicMock, call, patch

from src.core.enemy_ai import EnemyAI
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.managers.battle import Battle, BattleResult
from src.managers.enemy_manager import EnemyManager
from src.managers.outcomes import (
    CarrierHit,
    EnemyDestroyed,
    PlayerDestroyed,
    PowerUpCollected,
)
from src.managers.power_up_manager import PowerUpManager
from src.managers.sound_manager import SoundManager
from src.managers.texture_manager import TextureManager
from src.states.game_mode import GameMode
from src.utils.constants import (
    FPS,
    POWERUP_COLLECT_POINTS,
    TILE_SIZE,
    Difficulty,
    EffectType,
    PowerUpType,
    TankType,
)
from src.utils.paths import resource_path

DT = 1.0 / FPS
LEVEL_01 = resource_path("assets/maps/level_01.tmx")


@pytest.fixture
def texture_manager():
    """Mock TextureManager whose sprites are blank surfaces.

    EffectManager colour-keys its frames, so a MagicMock surface won't do.
    """
    tm = MagicMock(spec=TextureManager)
    tm.get_sprite.side_effect = lambda *args, **kwargs: pygame.Surface(
        (TILE_SIZE, TILE_SIZE)
    )
    return tm


@pytest.fixture
def sound():
    return MagicMock(spec=SoundManager)


@pytest.fixture
def make_battle(texture_manager, sound):
    """Build a Battle on level 01 with the given mode and carried progress."""

    def _make(
        mode=GameMode.ONE_PLAYER,
        carried=None,
        difficulty=Difficulty.NORMAL,
        game_map=None,
    ):
        return Battle(
            game_map or Map(LEVEL_01, texture_manager),
            mode=mode,
            carried=carried or {},
            difficulty=difficulty,
            controller_instance_ids=[],
            texture_manager=texture_manager,
            sound=sound,
        )

    return _make


@pytest.fixture
def battle(make_battle):
    return make_battle()


@pytest.fixture
def make_enemy(battle, texture_manager):
    """Build a real Enemy in the Battle's top-left corner, not yet on the field."""

    def _make(is_carrier=False):
        return EnemyTank(
            0,
            0,
            TILE_SIZE,
            texture_manager,
            tank_type=TankType.BASIC,
            map_width_px=battle.map.width_px,
            map_height_px=battle.map.height_px,
            is_carrier=is_carrier,
        )

    return _make


class TestBattleSetup:
    def test_players_start_invincible(self, battle):
        assert all(p.is_invincible for p in battle.player_manager.players)

    def test_settings_difficulty_is_used_without_a_map_override(
        self, make_battle, texture_manager
    ):
        game_map = Map(LEVEL_01, texture_manager)
        game_map.difficulty_override = None
        with patch("src.managers.battle.EnemyManager", wraps=EnemyManager) as enemies:
            make_battle(difficulty=Difficulty.EASY, game_map=game_map)
        assert enemies.call_args.kwargs["difficulty"] is Difficulty.EASY

    def test_map_difficulty_override_wins_over_settings(
        self, make_battle, texture_manager
    ):
        game_map = Map(LEVEL_01, texture_manager)
        game_map.difficulty_override = Difficulty.NORMAL
        with patch("src.managers.battle.EnemyManager", wraps=EnemyManager) as enemies:
            make_battle(difficulty=Difficulty.EASY, game_map=game_map)
        assert enemies.call_args.kwargs["difficulty"] is Difficulty.NORMAL

    def test_enemies_steer_toward_the_stage_base(self, battle):
        base_rect = battle.map.get_base().rect
        assert battle.enemy_manager.base_position == (
            float(base_rect.centerx),
            float(base_rect.centery),
        )


class TestBattleSpawning:
    """Enemies the SpawnManager materializes enter the EnemyManager's battlefield."""

    @staticmethod
    def _materialize(battle, *enemies):
        battle.spawn_manager = MagicMock()
        battle.spawn_manager.update.return_value = list(enemies)
        battle.spawn_manager.is_exhausted = False

    def test_spawning_is_blocked_by_every_tank_on_the_battlefield(
        self, battle, make_enemy
    ):
        enemy = make_enemy()
        battle.enemy_manager.add(enemy)
        self._materialize(battle)

        battle.step(DT)

        _, tanks, _ = battle.spawn_manager.update.call_args.args
        assert tanks == [*battle.player_manager.get_active_players(), enemy]

    def test_an_ordinary_enemy_appearing_keeps_the_power_ups(self, battle, make_enemy):
        battle.power_up_manager = MagicMock(spec=PowerUpManager, active_power_ups=[])
        self._materialize(battle, make_enemy())

        battle.step(DT)

        battle.power_up_manager.clear.assert_not_called()


class TestBattleResult:
    @staticmethod
    def _roster_spent(battle):
        battle.spawn_manager = MagicMock()
        battle.spawn_manager.update.return_value = []
        battle.spawn_manager.is_exhausted = True

    def test_no_victory_while_an_enemy_is_on_the_battlefield(self, battle, make_enemy):
        self._roster_spent(battle)
        battle.enemy_manager.add(make_enemy())

        assert battle.step(DT) is None

    def test_stepping_an_ended_battle_does_nothing(self, battle):
        self._roster_spent(battle)
        battle.enemy_manager.enemies.clear()
        battle.step(DT)
        battle.player_manager.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        )
        player = battle.player_manager.players[0]
        y_before = player.y

        assert battle.step(DT) is BattleResult.VICTORY
        assert player.y == y_before


class TestBattleInput:
    def test_events_reach_the_players_inputs(self, battle):
        player = battle.player_manager.players[0]
        y_before = player.y

        battle.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        battle.step(DT)

        assert player.y < y_before

    def test_clear_pending_shoot_drops_a_buffered_shot(self, battle):
        battle.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        battle.clear_pending_shoot()

        battle.step(DT)

        assert battle.tank_stepper.bullets == []


class TestBattleSounds:
    @pytest.mark.parametrize("enemy_fired", [True, False])
    def test_enemy_shot_plays_the_shoot_sound(self, battle, sound, enemy_fired):
        with patch.object(
            battle.enemy_manager, "step_enemies", return_value=enemy_fired
        ) as step_enemies:
            battle.step(DT)

        step_enemies.assert_called_once_with(
            DT, battle.tank_stepper, battle.player_manager.get_active_players()
        )
        assert (call("shoot") in sound.play.call_args_list) is enemy_fired

    def test_blink_starts_in_the_frame_a_power_up_drops(self, battle, sound):
        carrier = MagicMock(spec=EnemyTank, is_carrier=True)
        battle.collision_response_handler = MagicMock()
        battle.collision_response_handler.process_collisions.return_value = [
            CarrierHit(carrier)
        ]

        battle.step(DT)

        sound.update_powerup_blink.assert_called_with(True)


class TestBattleApplyOutcomes:
    """Battle.apply_outcomes is the one place outcomes take effect."""

    @pytest.fixture
    def game(self, battle):
        battle.power_up_manager = MagicMock(spec=PowerUpManager)
        battle.power_up_manager.apply.return_value = []
        battle.effect_manager = MagicMock()
        battle.player_manager = MagicMock()
        battle.enemy_manager = EnemyManager()
        return battle

    @pytest.fixture
    def players(self, game):
        p1, p2 = MagicMock(player_id=1), MagicMock(player_id=2)
        game.player_manager.get_active_players.return_value = [p1, p2]
        return p1, p2

    @staticmethod
    def _enemy(game, tank_type=TankType.BASIC, is_carrier=False):
        enemy = MagicMock(spec=EnemyTank, tank_type=tank_type, is_carrier=is_carrier)
        enemy.stop_carrying.side_effect = lambda: setattr(enemy, "is_carrier", False)
        enemy.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        enemy.enemy_id = id(enemy)
        game.enemy_manager.add(enemy, MagicMock(spec=EnemyAI))
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
    def test_enemy_destroyed_by_player(self, game, players, sound, tank_type, points):
        enemy = self._enemy(game, tank_type)
        game.apply_outcomes([EnemyDestroyed(enemy, by=players[1])])
        assert enemy not in game.enemy_manager.enemies
        game.player_manager.add_score.assert_called_once_with(points, player_id=2)
        game.effect_manager.spawn_at_rect.assert_called_once_with(
            EffectType.LARGE_EXPLOSION, enemy.rect
        )
        sound.play.assert_called_once_with("explosion")

    def test_enemy_destroyed_twice_applies_once(self, game, players):
        enemy = self._enemy(game)
        game.apply_outcomes(
            [EnemyDestroyed(enemy, by=players[0]), EnemyDestroyed(enemy, by=None)]
        )
        game.player_manager.add_score.assert_called_once_with(100, player_id=1)
        game.effect_manager.spawn_at_rect.assert_called_once()

    def test_carrier_drop_avoids_every_player(self, game, players):
        carrier = self._enemy(game, is_carrier=True)
        other = self._enemy(game)
        game.apply_outcomes([EnemyDestroyed(carrier, by=players[0])])
        game.power_up_manager.spawn_power_up.assert_called_once_with([*players, other])

    def test_carrier_hit_drops_once(self, game, players):
        carrier = self._enemy(game, is_carrier=True)
        game.apply_outcomes(
            [
                CarrierHit(carrier),
                CarrierHit(carrier),
                EnemyDestroyed(carrier, by=players[0]),
            ]
        )
        game.power_up_manager.spawn_power_up.assert_called_once()
        carrier.stop_carrying.assert_called_once_with()

    def test_player_destroyed(self, game, players, sound):
        p1 = players[0]
        p1.rect = pygame.Rect(64, 64, TILE_SIZE, TILE_SIZE)
        explosion_at = []
        game.player_manager.handle_player_death.side_effect = lambda p: (
            explosion_at.append(
                game.effect_manager.spawn_at_rect.call_args.args[1].copy()
            )
        )
        game.apply_outcomes([PlayerDestroyed(p1)])
        game.player_manager.handle_player_death.assert_called_once_with(p1)
        sound.play.assert_called_once_with("explosion")
        # The explosion is placed before the respawn moves the tank.
        assert explosion_at == [pygame.Rect(64, 64, TILE_SIZE, TILE_SIZE)]

    def test_power_up_collected(self, game, players, sound):
        game.apply_outcomes([PowerUpCollected(PowerUpType.STAR, players[1])])
        game.player_manager.add_score.assert_called_once_with(
            POWERUP_COLLECT_POINTS, player_id=2
        )
        sound.play.assert_called_once_with("powerup")
        game.power_up_manager.apply.assert_called_once_with(
            PowerUpType.STAR, players[1], game.enemy_manager
        )
