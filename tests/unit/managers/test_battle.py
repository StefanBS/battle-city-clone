"""Unit tests for Battle: one Stage's frame pipeline and outcomes, no window."""

import pytest
import pygame
from unittest.mock import MagicMock, call, patch

from src.core.bullet import Bullet
from src.core.enemy_ai import EnemyAI
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.managers.battle import Battle, BattleResult
from src.managers.enemy_manager import EnemyManager
from src.managers.player_manager import CarriedProgress
from src.managers.outcomes import (
    CarrierHit,
    EnemyDestroyed,
    PlayerDestroyed,
    PowerUpCollected,
)
from src.managers.sound_manager import SoundManager
from src.managers.texture_manager import TextureManager
from src.states.game_mode import GameMode
from src.utils.constants import (
    FPS,
    POWERUP_COLLECT_POINTS,
    TILE_SIZE,
    Difficulty,
    Direction,
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

    def _make(tank_type=TankType.BASIC, is_carrier=False):
        return EnemyTank(
            0,
            0,
            TILE_SIZE,
            texture_manager,
            tank_type=tank_type,
            map_width_px=battle.map.width_px,
            map_height_px=battle.map.height_px,
            is_carrier=is_carrier,
        )

    return _make


def _idle_ai(fires=False):
    """An Enemy AI that stands still, and fires every frame if ``fires``."""
    ai = MagicMock(spec=EnemyAI)
    ai.get_movement_direction.return_value = (0, 0)
    ai.consume_shoot.return_value = fires
    return ai


def _hold_roster(battle):
    """One Enemy still to come that never comes on its own."""
    battle.replace_roster({TankType.BASIC: 1}, spawn_interval=float("inf"))


def _let_appear(battle, max_frames=5 * FPS):
    """Step the Battle until an Enemy is on the battlefield."""
    for _ in range(max_frames):
        if battle.scene().enemies:
            return
        battle.step(DT)
    raise AssertionError("No Enemy appeared")


class TestBattleSetup:
    def test_players_start_invincible(self, battle):
        assert all(p.is_invincible for p in battle.scene().players)

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

    def test_enemies_steer_toward_the_stage_base(self, make_battle, texture_manager):
        game_map = Map(LEVEL_01, texture_manager)
        base_rect = game_map.get_base().rect
        with patch("src.managers.battle.EnemyManager", wraps=EnemyManager) as enemies:
            make_battle(game_map=game_map)
        assert enemies.call_args.kwargs["base_position"] == (
            float(base_rect.centerx),
            float(base_rect.centery),
        )


class TestBattleSpawning:
    """Enemies that Appear are brought onto the battlefield."""

    def test_an_enemy_that_appears_is_brought_onto_the_battlefield(self, battle):
        battle.replace_roster({TankType.FAST: 1}, spawn_interval=float("inf"))
        assert battle.start_spawning()

        _let_appear(battle)

        (enemy,) = battle.scene().enemies
        assert enemy.tank_type is TankType.FAST

    def test_an_ordinary_enemy_appearing_keeps_the_power_ups(self, battle):
        battle.replace_roster({TankType.BASIC: 1}, spawn_interval=float("inf"))
        assert battle.start_spawning()
        battle.drop_power_up(PowerUpType.STAR)
        (power_up,) = battle.scene().power_ups

        _let_appear(battle)

        assert battle.scene().power_ups == (power_up,)

    def test_a_carrier_appearing_clears_the_power_ups(self, battle):
        battle.replace_roster(
            {TankType.BASIC: 1}, carrier_indices=(0,), spawn_interval=float("inf")
        )
        assert battle.start_spawning()
        battle.drop_power_up(PowerUpType.STAR)

        _let_appear(battle)

        assert battle.scene().power_ups == ()

    def test_an_enemy_that_just_appeared_blocks_its_spawn_point(
        self, make_battle, texture_manager
    ):
        # One Enemy Spawn Point, and the next Enemy due every frame: only a
        # tank on that point holds it back.
        game_map = Map(LEVEL_01, texture_manager)
        game_map.spawn_points = game_map.spawn_points[:1]
        game_map.enemy_composition = {TankType.BASIC: 2}
        game_map.spawn_interval = 0.0
        battle = make_battle(game_map=game_map)

        _let_appear(battle)

        # No spawn animation started in the frame the first Enemy Appeared.
        assert battle.scene().effects == ()


class TestBattleResult:
    def test_no_victory_while_an_enemy_is_on_the_battlefield(self, battle, make_enemy):
        battle.replace_roster({})
        battle.add_enemy(make_enemy(), _idle_ai())

        assert battle.step(DT) is None

    def test_stepping_an_ended_battle_does_nothing(self, battle):
        battle.replace_roster({})
        battle.step(DT)
        battle.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        player = battle.scene().players[0]
        y_before = player.y

        assert battle.step(DT) is BattleResult.VICTORY
        assert player.y == y_before


class TestBattleWorldView:
    def test_shows_every_live_player(self, make_battle):
        battle = make_battle(mode=GameMode.TWO_PLAYERS)

        view = battle.world_view()

        assert [p.player_id for p in view.players] == [1, 2]

    def test_leaves_out_an_eliminated_player(self, make_battle):
        battle = make_battle(
            mode=GameMode.TWO_PLAYERS,
            carried={2: CarriedProgress(lives=0, star_level=0, eliminated=True)},
        )

        view = battle.world_view()

        assert [p.player_id for p in view.players] == [1]


class TestBattleScene:
    """What the Renderer draws comes from one read-only scene."""

    def test_shows_the_stage_map_and_every_live_player(self, make_battle):
        battle = make_battle(mode=GameMode.TWO_PLAYERS)

        scene = battle.scene()

        assert scene.map is battle.map
        assert [p.player_id for p in scene.players] == [1, 2]

    def test_shows_what_the_hud_needs_for_each_player(self, make_battle):
        battle = make_battle(
            mode=GameMode.TWO_PLAYERS,
            carried={2: CarriedProgress(lives=0, star_level=0, eliminated=True)},
        )

        entries = battle.scene().hud_entries

        assert [(e.label, e.eliminated) for e in entries] == [
            ("P1", False),
            ("P2", True),
        ]

    def test_shows_the_spawn_animation_of_the_first_enemy(self, battle):
        # The first Enemy starts Spawning as the Battle begins.
        assert len(battle.scene().effects) == 1

    def test_shows_a_bullet_in_flight(self, battle):
        battle.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))

        battle.step(DT)

        (bullet,) = battle.scene().bullets
        assert bullet.owner is battle.scene().players[0]

    def test_starts_with_no_enemies_or_power_ups(self, battle):
        scene = battle.scene()

        assert scene.enemies == ()
        assert scene.power_ups == ()


class _FireInPlace:
    """A TankIntent that stands still and fires."""

    def get_movement_direction(self):
        return (0, 0)

    def consume_shoot(self):
        return True


class TestBattleSetupCalls:
    """The calls that arrange a running Battle for a test."""

    def test_an_added_enemy_is_on_the_battlefield(self, battle, make_enemy):
        enemy = make_enemy()

        battle.add_enemy(enemy)

        assert battle.scene().enemies == (enemy,)

    def test_an_added_enemy_is_driven_by_the_ai_it_is_given(self, battle, make_enemy):
        enemy = make_enemy()
        ai = MagicMock(spec=EnemyAI)
        ai.get_movement_direction.return_value = (0, 0)
        ai.consume_shoot.return_value = False

        battle.add_enemy(enemy, ai)
        battle.step(DT)

        ai.update.assert_called_once()
        assert ai.update.call_args.args[0] == DT

    def test_clearing_enemies_leaves_the_battlefield_empty(self, battle, make_enemy):
        battle.add_enemy(make_enemy())

        battle.clear_enemies()

        assert battle.scene().enemies == ()

    def test_an_empty_roster_with_a_clear_battlefield_is_a_victory(self, battle):
        battle.replace_roster({})

        assert battle.step(DT) is BattleResult.VICTORY

    def test_a_held_roster_sends_no_enemy_on_its_own(self, battle):
        battle.replace_roster({TankType.BASIC: 1}, spawn_interval=float("inf"))

        for _ in range(3 * FPS):
            battle.step(DT)

        assert battle.scene().enemies == ()
        assert battle.result is None

    def test_start_spawning_brings_in_the_roster_s_carrier(self, battle):
        battle.replace_roster(
            {TankType.BASIC: 1}, carrier_indices=(0,), spawn_interval=float("inf")
        )

        assert battle.start_spawning() is True
        while not battle.scene().enemies:
            battle.step(DT)

        (enemy,) = battle.scene().enemies
        assert enemy.is_carrier

    def test_start_spawning_fails_once_the_roster_is_used_up(self, battle):
        battle.replace_roster({TankType.BASIC: 1}, spawn_interval=float("inf"))

        assert battle.start_spawning() is True
        assert battle.start_spawning() is False

    def test_an_added_bullet_is_in_flight(self, battle):
        player = battle.scene().players[0]
        bullet = Bullet(200, 200, Direction.UP, player)

        battle.add_bullet(bullet)

        assert battle.scene().bullets == (bullet,)

    def test_a_dropped_power_up_lands_where_and_as_asked(self, battle):
        battle.drop_power_up(PowerUpType.STAR, position=(64, 96))

        (power_up,) = battle.scene().power_ups
        assert (power_up.power_up_type, power_up.x, power_up.y) == (
            PowerUpType.STAR,
            64,
            96,
        )

    def test_a_dropped_power_up_avoids_every_player(self, battle):
        battle.drop_power_up()

        (power_up,) = battle.scene().power_ups
        player = battle.scene().players[0]
        assert not power_up.rect.colliderect(player.rect)

    def test_step_tank_fires_within_the_bullet_cap(self, battle):
        player = battle.scene().players[0]

        battle.step_tank(player, _FireInPlace(), DT)
        battle.step_tank(player, _FireInPlace(), DT)

        (bullet,) = battle.scene().bullets
        assert bullet.owner is player


class TestBattleInput:
    def test_events_reach_the_players_inputs(self, battle):
        player = battle.scene().players[0]
        y_before = player.y

        battle.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        battle.step(DT)

        assert player.y < y_before

    def test_clear_pending_shoot_drops_a_buffered_shot(self, battle):
        battle.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        battle.clear_pending_shoot()

        battle.step(DT)

        assert battle.scene().bullets == ()


class TestBattleSounds:
    @pytest.mark.parametrize("enemy_fires", [True, False])
    def test_an_enemy_shot_plays_the_shoot_sound(
        self, battle, sound, make_enemy, enemy_fires
    ):
        _hold_roster(battle)
        battle.add_enemy(make_enemy(), _idle_ai(fires=enemy_fires))

        battle.step(DT)

        assert (call("shoot") in sound.play.call_args_list) is enemy_fires

    def test_blink_starts_in_the_frame_a_power_up_drops(
        self, battle, sound, make_enemy
    ):
        _hold_roster(battle)
        carrier = make_enemy(is_carrier=True)
        battle.add_enemy(carrier, _idle_ai())
        player = battle.scene().players[0]
        # A Player bullet already on the Carrier: it hits this frame.
        battle.add_bullet(
            Bullet(carrier.rect.centerx, carrier.rect.centery, Direction.UP, player)
        )
        sound.update_powerup_blink.reset_mock()

        battle.step(DT)

        sound.update_powerup_blink.assert_called_once_with(True)


class TestBattleApplyOutcomes:
    """Battle.apply_outcomes is the one place outcomes take effect."""

    @pytest.fixture
    def battle(self, make_battle):
        battle = make_battle(mode=GameMode.TWO_PLAYERS)
        _hold_roster(battle)
        return battle

    @pytest.fixture
    def players(self, battle):
        return battle.scene().players

    @staticmethod
    def _enemy(battle, make_enemy, tank_type=TankType.BASIC, is_carrier=False):
        enemy = make_enemy(tank_type, is_carrier=is_carrier)
        battle.add_enemy(enemy, _idle_ai())
        return enemy

    @staticmethod
    def _scores(battle):
        return {pid: p.score for pid, p in battle.carried_progress.items()}

    @pytest.mark.parametrize(
        "tank_type,points",
        [
            (TankType.BASIC, 100),
            (TankType.FAST, 200),
            (TankType.POWER, 300),
            (TankType.ARMOR, 400),
        ],
    )
    def test_enemy_destroyed_by_player(
        self, battle, make_enemy, players, sound, tank_type, points
    ):
        enemy = self._enemy(battle, make_enemy, tank_type)
        effects_before = len(battle.scene().effects)

        battle.apply_outcomes([EnemyDestroyed(enemy, by=players[1])])

        assert enemy not in battle.scene().enemies
        assert self._scores(battle) == {1: 0, 2: points}
        effects = battle.scene().effects
        assert len(effects) == effects_before + 1
        assert (effects[-1].x, effects[-1].y) == enemy.rect.center
        sound.play.assert_called_once_with("explosion")

    def test_enemy_destroyed_twice_applies_once(self, battle, make_enemy, players):
        enemy = self._enemy(battle, make_enemy)
        effects_before = len(battle.scene().effects)

        battle.apply_outcomes(
            [EnemyDestroyed(enemy, by=players[0]), EnemyDestroyed(enemy, by=None)]
        )

        assert self._scores(battle) == {1: 100, 2: 0}
        assert len(battle.scene().effects) == effects_before + 1

    def test_carrier_drop_avoids_every_tank(self, battle, make_enemy, players):
        carrier = self._enemy(battle, make_enemy, is_carrier=True)
        other = self._enemy(battle, make_enemy)
        other.set_position(3 * TILE_SIZE, 0)
        other.rect.topleft = (3 * TILE_SIZE, 0)

        battle.apply_outcomes([EnemyDestroyed(carrier, by=players[0])])

        (power_up,) = battle.scene().power_ups
        for tank in (*players, other):
            assert not power_up.rect.colliderect(tank.rect)

    def test_carrier_hit_drops_once(self, battle, make_enemy, players):
        carrier = self._enemy(battle, make_enemy, is_carrier=True)
        battle.apply_outcomes([CarrierHit(carrier)])
        (dropped,) = battle.scene().power_ups

        battle.apply_outcomes(
            [CarrierHit(carrier), EnemyDestroyed(carrier, by=players[0])]
        )

        assert battle.scene().power_ups == (dropped,)
        assert not carrier.is_carrier

    def test_player_destroyed(self, battle, players, sound):
        p1 = players[0]
        p1.set_position(64, 64)
        p1.rect.topleft = (64, 64)

        battle.apply_outcomes([PlayerDestroyed(p1)])

        sound.play.assert_called_once_with("explosion")
        # The explosion is placed before the respawn moves the tank.
        explosion = battle.scene().effects[-1]
        assert (explosion.x, explosion.y) == (64 + TILE_SIZE / 2, 64 + TILE_SIZE / 2)
        assert (p1.x, p1.y) == p1.initial_position

    def test_power_up_collected(self, battle, players, sound):
        battle.apply_outcomes([PowerUpCollected(PowerUpType.STAR, players[1])])

        assert self._scores(battle) == {1: 0, 2: POWERUP_COLLECT_POINTS}
        sound.play.assert_called_once_with("powerup")
        assert players[1].star_level == 1
