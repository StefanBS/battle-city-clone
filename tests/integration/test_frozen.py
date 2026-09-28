"""Integration tests for Frozen tanks under a Clock.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pygame
import pytest
from src.battle.outcomes import PowerUpCollected
from src.battle.player_input import KEY_TO_DIRECTION
from src.utils.constants import (
    CLOCK_FREEZE_DURATION,
    FPS,
    ICE_SLIDE_DISTANCE,
    Direction,
    PowerUpType,
    TankType,
)
from tests.integration.conftest import (
    SoundRecorder,
    clear_enemies,
    clear_tiles,
    first_player,
    let_spawning_enemies_appear,
    make_battle,
    place_ice_patch,
    place_player_at,
    spawn_enemy_at,
    tick,
    use_roster,
)

_DIRECTION_TO_KEY = {direction: key for key, direction in KEY_TO_DIRECTION.items()}


def _open_field(battle):
    """No Enemies to come and an open field across rows 4-13."""
    clear_enemies(battle)
    clear_tiles(battle.map, [(x, y) for x in range(26) for y in range(4, 14)])


@pytest.fixture
def battle(battle):
    """A Battle with no Enemies to come and an open field across rows 4-13."""
    _open_field(battle)
    return battle


def _clock(battle):
    battle.apply_outcomes([PowerUpCollected(PowerUpType.CLOCK, first_player(battle))])


def _hold(battle, direction):
    battle.handle_event(
        pygame.event.Event(pygame.KEYDOWN, key=_DIRECTION_TO_KEY[direction])
    )


def _driving_enemy(battle, grid_x, grid_y, direction):
    """An Enemy that has been driving ``direction`` for a few frames."""
    enemy = spawn_enemy_at(
        battle, grid_x, grid_y, direction=direction, fires=False, turns=False
    )
    tick(battle, 5)
    assert enemy.is_moving
    return enemy


class TestClockFreezesEnemies:
    def test_engine_sound_stops_and_the_enemy_is_not_moving(self):
        recorder = SoundRecorder()
        battle = make_battle(sound=recorder)
        _open_field(battle)
        enemy = _driving_enemy(battle, 4, 6, Direction.RIGHT)
        assert recorder.engine_running is True

        _clock(battle)
        tick(battle)

        assert enemy.is_moving is False
        assert recorder.engine_running is False

    def test_a_player_driving_into_a_frozen_enemy_does_not_push_it_back(self, battle):
        enemy = _driving_enemy(battle, 16, 6, Direction.LEFT)
        _clock(battle)
        tick(battle)
        frozen_at = (enemy.x, enemy.y)
        player = first_player(battle)
        place_player_at(battle, enemy.x - player.width - 1, enemy.y)
        player.direction = Direction.RIGHT
        _hold(battle, Direction.RIGHT)

        tick(battle, 10)

        assert (enemy.x, enemy.y) == frozen_at
        assert player.rect.right <= enemy.rect.left

    def test_an_enemy_that_appears_during_a_clock_is_frozen_for_the_time_left(
        self, battle
    ):
        _clock(battle)
        tick(battle, FPS)
        # A one-Enemy Roster: no more spawns while the Clock runs out.
        use_roster(battle, {TankType.BASIC: 1})
        assert battle.start_spawning()
        let_spawning_enemies_appear(battle)
        (enemy,) = battle.scene().enemies
        appeared_at = (enemy.x, enemy.y)

        assert enemy.is_frozen is True
        # Frozen, where it Appeared, until the Clock runs out.
        for _ in range(int(CLOCK_FREEZE_DURATION * FPS)):
            if not enemy.is_frozen:
                break
            assert (enemy.x, enemy.y) == appeared_at
            tick(battle)

        assert enemy.is_frozen is False


class TestFrozenOnIce:
    @pytest.fixture(autouse=True)
    def ice(self, battle):
        place_ice_patch(battle, 2, 6, width=22, height=2)

    def test_a_sliding_enemy_finishes_its_slide_then_stands_still(self, battle):
        enemy = _driving_enemy(battle, 4, 6, Direction.RIGHT)
        assert enemy.start_slide()
        slide_from = enemy.x
        tick(battle, 3)
        assert enemy.is_sliding

        _clock(battle)
        for _ in range(FPS):
            if not enemy.is_sliding:
                break
            tick(battle)
        slide_end = enemy.x
        tick(battle, 10)

        assert slide_end == pytest.approx(slide_from + ICE_SLIDE_DISTANCE)
        assert enemy.is_moving is False
        assert enemy.x == slide_end
