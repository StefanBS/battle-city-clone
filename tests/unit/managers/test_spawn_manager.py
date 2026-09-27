from collections import Counter

import pytest
import pygame
from unittest.mock import ANY, patch, MagicMock
from src.managers.spawn_manager import SpawnManager
from src.managers.effect_manager import EffectManager
from src.core.effect import Effect
from src.core.enemy_tank import EnemyTank
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.utils.constants import (
    EffectType,
    TILE_SIZE,
    SUB_TILE_SIZE,
    TankType,
)

_DEFAULT_COMPOSITION = {
    TankType.BASIC: 18,
    TankType.FAST: 2,
    TankType.POWER: 0,
    TankType.ARMOR: 0,
}


SPAWN_POINTS = [(3, 1), (8, 1), (12, 1)]


@pytest.fixture
def mock_player_tank():
    """Create a mock player tank positioned away from spawn points."""
    player = MagicMock(spec=PlayerTank)
    # Place player at the bottom of the map, far from spawn points
    player.rect = pygame.Rect(7 * TILE_SIZE, 14 * TILE_SIZE, TILE_SIZE, TILE_SIZE)
    return player


@pytest.fixture
def mock_game_map():
    """Create a mock game map with no collidable tiles."""
    game_map = MagicMock(spec=Map)
    game_map.get_collidable_tiles.return_value = []
    game_map.spawn_points = SPAWN_POINTS
    game_map.width_px = 16 * TILE_SIZE
    game_map.height_px = 16 * TILE_SIZE
    game_map.tile_size = SUB_TILE_SIZE
    game_map.grid_to_pixels.side_effect = lambda gx, gy: (
        gx * SUB_TILE_SIZE,
        gy * SUB_TILE_SIZE,
    )
    return game_map


@pytest.fixture
def make_spawn_manager(mock_texture_manager, mock_game_map):
    """Build a SpawnManager over the mock map; no animations unless given."""

    def make(composition=None, **kwargs):
        return SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=(
                composition if composition is not None else _DEFAULT_COMPOSITION
            ),
            spawn_interval=5.0,
            **kwargs,
        )

    return make


@pytest.fixture
def spawn_manager(make_spawn_manager):
    """A SpawnManager with the default Roster and no animations."""
    return make_spawn_manager()


def _enemy_at(spawn_point):
    """A tank standing right on ``spawn_point``."""
    enemy = MagicMock(spec=EnemyTank)
    enemy.rect = pygame.Rect(
        spawn_point[0] * SUB_TILE_SIZE,
        spawn_point[1] * SUB_TILE_SIZE,
        TILE_SIZE,
        TILE_SIZE,
    )
    return enemy


class TestSpawnManager:
    """Unit test cases for the SpawnManager class."""

    def test_advance_waits_an_interval_from_building_it(
        self, make_spawn_manager, mock_player_tank
    ):
        manager = make_spawn_manager({TankType.BASIC: 3})

        manager.advance(4.9, [mock_player_tank])
        assert manager.remaining == 3
        manager.advance(0.1, [mock_player_tank])
        assert manager.remaining == 2

    @patch("random.choice")
    def test_start_spawning_refuses_a_spawn_point_under_a_tile(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        mock_random_choice.return_value = SPAWN_POINTS[0]
        mock_game_map.get_collidable_tiles.return_value = [
            _enemy_at(SPAWN_POINTS[0]).rect
        ]
        remaining = spawn_manager.remaining

        assert spawn_manager.start_spawning([mock_player_tank]) is False
        assert spawn_manager.remaining == remaining

    @patch("random.choice")
    def test_start_spawning_refuses_a_spawn_point_under_a_tank(
        self, mock_random_choice, spawn_manager, mock_player_tank
    ):
        mock_random_choice.return_value = SPAWN_POINTS[0]
        remaining = spawn_manager.remaining

        result = spawn_manager.start_spawning(
            [mock_player_tank, _enemy_at(SPAWN_POINTS[0])]
        )

        assert result is False
        assert spawn_manager.remaining == remaining

    @patch("random.choice")
    def test_after_a_spawn_the_next_waits_a_whole_interval(
        self, mock_random_choice, spawn_manager, mock_player_tank
    ):
        mock_random_choice.side_effect = [SPAWN_POINTS[0], SPAWN_POINTS[1]]
        spawn_manager.advance(5.0, [mock_player_tank])
        remaining = spawn_manager.remaining

        spawn_manager.advance(4.9, [mock_player_tank])
        assert spawn_manager.remaining == remaining
        spawn_manager.advance(0.1, [mock_player_tank])
        assert spawn_manager.remaining == remaining - 1

    @patch("random.choice")
    def test_advance_tries_again_next_time_when_blocked(
        self, mock_random_choice, spawn_manager, mock_player_tank
    ):
        """A blocked spawn keeps the timer due instead of waiting a new interval."""
        mock_random_choice.return_value = SPAWN_POINTS[0]
        blocker = _enemy_at(SPAWN_POINTS[0])
        remaining = spawn_manager.remaining
        spawn_manager.advance(5.0, [mock_player_tank, blocker])
        assert spawn_manager.remaining == remaining

        spawn_manager.advance(0.0, [mock_player_tank])

        assert spawn_manager.remaining == remaining - 1

    def test_roster_matches_composition(self, make_spawn_manager, mock_player_tank):
        """Every Enemy in the composition Appears once, then spawning stops."""
        composition = {
            TankType.BASIC: 2,
            TankType.FAST: 5,
            TankType.POWER: 10,
            TankType.ARMOR: 3,
        }
        manager = make_spawn_manager(composition)

        enemies = []
        for _ in range(25):  # more than the Roster, to test that it stops
            manager.start_spawning([mock_player_tank])
            enemies += manager.take_appeared()

        assert Counter(e.tank_type for e in enemies) == composition
        assert manager.remaining == 0
        assert manager.is_exhausted

    def test_an_empty_roster_is_exhausted_from_the_start(self, make_spawn_manager):
        assert make_spawn_manager({}).is_exhausted


class TestSpawnAnimation:
    """Tests for Spawning Enemies and their animation."""

    @pytest.fixture
    def mock_effect(self):
        effect = MagicMock(spec=Effect)
        effect.active = True
        return effect

    @pytest.fixture
    def mock_effect_manager(self, mock_effect):
        em = MagicMock(spec=EffectManager)
        em.spawn.return_value = mock_effect
        return em

    @pytest.fixture
    def spawning(self, make_spawn_manager, mock_effect_manager, mock_player_tank):
        """A SpawnManager with one Enemy Spawning, its animation playing."""
        manager = make_spawn_manager(
            {TankType.BASIC: 2}, effect_manager=mock_effect_manager
        )
        manager.start_spawning([mock_player_tank])
        return manager

    def test_starting_a_spawn_plays_the_spawn_animation(
        self, spawning, mock_effect_manager
    ):
        mock_effect_manager.spawn.assert_called_once_with(EffectType.SPAWN, ANY, ANY)

    def test_an_enemy_appears_when_its_animation_ends(self, spawning, mock_effect):
        assert spawning.take_appeared() == []

        mock_effect.active = False

        assert len(spawning.take_appeared()) == 1

    def test_not_exhausted_with_enemies_left_in_the_roster(self, spawning, mock_effect):
        mock_effect.active = False
        spawning.take_appeared()

        assert not spawning.is_exhausted

    def test_not_exhausted_while_an_enemy_is_spawning(
        self, spawning, mock_effect, mock_player_tank
    ):
        mock_effect.active = False
        spawning.take_appeared()
        spawning.start_spawning([mock_player_tank])
        mock_effect.active = True

        assert spawning.remaining == 0
        assert not spawning.is_exhausted

    def test_exhausted_once_every_enemy_has_appeared(
        self, spawning, mock_effect, mock_player_tank
    ):
        mock_effect.active = False
        spawning.take_appeared()
        spawning.start_spawning([mock_player_tank])
        spawning.take_appeared()

        assert spawning.is_exhausted

    @patch("random.choice")
    def test_a_spawning_enemy_blocks_its_spawn_point(
        self,
        mock_random_choice,
        make_spawn_manager,
        mock_effect_manager,
        mock_player_tank,
    ):
        mock_random_choice.return_value = SPAWN_POINTS[0]
        manager = make_spawn_manager(
            {TankType.BASIC: 2}, effect_manager=mock_effect_manager
        )
        manager.start_spawning([mock_player_tank])

        assert manager.start_spawning([mock_player_tank]) is False
        assert manager.remaining == 1


class TestSpawnManagerCarrier:
    """Tests for which Enemies of the Roster are Carriers."""

    @staticmethod
    def _appear_all(manager, mock_player_tank, count):
        """Start and bring in ``count`` Enemies, one after another."""
        enemies = []
        for _ in range(count):
            manager.start_spawning([mock_player_tank])
            enemies += manager.take_appeared()
        return enemies

    def test_fourth_enemy_is_carrier(self, spawn_manager, mock_player_tank):
        enemies = self._appear_all(spawn_manager, mock_player_tank, 4)

        assert [t.is_carrier for t in enemies] == [False, False, False, True]

    def test_carrier_waits_for_its_spawn_animation(
        self, make_spawn_manager, mock_player_tank
    ):
        mock_effect_manager = MagicMock(spec=EffectManager)
        mock_effect = MagicMock(spec=Effect)
        mock_effect_manager.spawn.return_value = mock_effect
        manager = make_spawn_manager(effect_manager=mock_effect_manager)
        enemies = []
        for _ in range(3):
            mock_effect.active = True
            manager.start_spawning([mock_player_tank])
            mock_effect.active = False
            enemies += manager.take_appeared()
        mock_effect.active = True
        manager.start_spawning([mock_player_tank])

        assert manager.take_appeared() == []
        mock_effect.active = False
        enemies += manager.take_appeared()
        assert [t.is_carrier for t in enemies] == [False, False, False, True]

    def test_custom_carrier_indices_used(self, make_spawn_manager, mock_player_tank):
        manager = make_spawn_manager(powerup_carrier_indices=(1,))

        first, second = self._appear_all(manager, mock_player_tank, 2)

        assert not first.is_carrier
        assert second.is_carrier
