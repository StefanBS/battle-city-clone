"""Integration tests for Frozen tanks under a Clock.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pygame
import pytest
from src.managers.outcomes import PowerUpCollected
from src.managers.player_input import KEY_TO_DIRECTION
from src.managers.sound_manager import SoundManager
from src.utils.constants import (
    CLOCK_FREEZE_DURATION,
    FPS,
    ICE_SLIDE_DISTANCE,
    Direction,
    PowerUpType,
    TankType,
)
from tests.integration.conftest import (
    clear_tiles,
    first_player,
    flush_pending_spawns,
    place_ice_patch,
    place_player_at,
    spawn_enemy_at,
    tick,
)

_DIRECTION_TO_KEY = {direction: key for key, direction in KEY_TO_DIRECTION.items()}


class _EngineRecorder(SoundManager):
    """A SoundManager that remembers whether the engine was last told to run."""

    def __init__(self) -> None:
        super().__init__()
        self.engine_running: bool | None = None

    def update_engine(self, any_moving: bool) -> None:
        self.engine_running = any_moving
        super().update_engine(any_moving)


@pytest.fixture
def game(game_manager_fixture):
    """A Battle with no Enemies to come and an open field across rows 4-13."""
    gm = game_manager_fixture
    gm.battle.enemy_manager.enemies.clear()
    gm.battle.spawn_manager._pending_spawns.clear()
    gm.battle.spawn_manager._spawn_queue.clear()
    clear_tiles(gm.battle.map, [(x, y) for x in range(26) for y in range(4, 14)])
    return gm


def _clock(game):
    game.battle.apply_outcomes(
        [PowerUpCollected(PowerUpType.CLOCK, first_player(game))]
    )


def _hold(game, direction):
    game.battle.player_manager.handle_event(
        pygame.event.Event(pygame.KEYDOWN, key=_DIRECTION_TO_KEY[direction])
    )


def _driving_enemy(game, grid_x, grid_y, direction):
    """An Enemy that has been driving ``direction`` for a few frames."""
    enemy = spawn_enemy_at(
        game, grid_x, grid_y, direction=direction, fires=False, turns=False
    )
    tick(game, 5)
    assert enemy.is_moving
    return enemy


class TestClockStopsEnemies:
    def test_engine_sound_stops_and_the_enemy_is_not_moving(self, game):
        recorder = _EngineRecorder()
        game.battle._sound = recorder
        enemy = _driving_enemy(game, 4, 6, Direction.RIGHT)
        assert recorder.engine_running is True

        _clock(game)
        tick(game)

        assert enemy.is_moving is False
        assert recorder.engine_running is False

    def test_a_player_driving_into_a_frozen_enemy_does_not_push_it_back(self, game):
        enemy = _driving_enemy(game, 16, 6, Direction.LEFT)
        _clock(game)
        tick(game)
        frozen_at = (enemy.x, enemy.y)
        player = first_player(game)
        place_player_at(game, enemy.x - player.width - 1, enemy.y)
        player.direction = Direction.RIGHT
        _hold(game, Direction.RIGHT)

        tick(game, 10)

        assert (enemy.x, enemy.y) == frozen_at
        assert player.rect.right <= enemy.rect.left

    def test_an_enemy_that_appears_during_a_clock_is_frozen_for_the_time_left(
        self, game
    ):
        spawn_manager = game.battle.spawn_manager
        _clock(game)
        tick(game, FPS)
        spawn_manager._spawn_queue.append(TankType.BASIC)
        spawn_manager.spawn_enemy(
            game.battle.player_manager.get_active_players(), game.battle.map
        )
        flush_pending_spawns(game)
        # The Roster is empty; no more spawns while the Clock runs out.
        spawn_manager.max_enemy_spawns = spawn_manager.total_enemy_spawns
        (enemy,) = game.battle.enemy_manager.enemies
        appeared_at = (enemy.x, enemy.y)
        enemy_manager = game.battle.enemy_manager

        for _ in range(int(CLOCK_FREEZE_DURATION * FPS)):
            if not enemy_manager.enemies_frozen:
                break
            assert enemy.is_frozen is True
            assert (enemy.x, enemy.y) == appeared_at
            tick(game)

        assert enemy_manager.enemies_frozen is False
        assert enemy.is_frozen is False


class TestFrozenOnIce:
    @pytest.fixture
    def ice(self, game):
        place_ice_patch(game, 2, 6, width=22, height=2)
        return game

    def _stops_after(self, game, enemy):
        """Tick until the Enemy stops Sliding, then check it stands still."""
        for _ in range(FPS):
            if not enemy.is_sliding:
                break
            tick(game)
        stopped_at = (enemy.x, enemy.y)
        tick(game, 10)
        assert enemy.is_moving is False
        assert (enemy.x, enemy.y) == stopped_at
        return stopped_at

    def test_a_sliding_enemy_finishes_its_slide_then_stops(self, ice):
        enemy = _driving_enemy(ice, 4, 6, Direction.RIGHT)
        assert enemy.start_slide()
        slide_from = enemy.x
        tick(ice, 3)
        assert enemy.is_sliding

        _clock(ice)
        x, _ = self._stops_after(ice, enemy)

        assert x == pytest.approx(slide_from + ICE_SLIDE_DISTANCE)

    def test_an_enemy_driving_on_ice_slides_when_frozen(self, ice):
        enemy = _driving_enemy(ice, 4, 6, Direction.RIGHT)
        frozen_at = enemy.x

        _clock(ice)
        tick(ice)
        assert enemy.is_sliding
        x, _ = self._stops_after(ice, enemy)

        assert x == pytest.approx(frozen_at + ICE_SLIDE_DISTANCE)
