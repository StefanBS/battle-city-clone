"""Integration tests for Frozen tanks under a Clock.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pygame
import pytest
from src.battle.outcomes import PowerUpCollected
from src.battle.player_input import KEY_TO_DIRECTION
from src.shell.sound_manager import SoundManager
from src.utils.constants import (
    CLOCK_FREEZE_DURATION,
    FPS,
    ICE_SLIDE_DISTANCE,
    Direction,
    PowerUpType,
    TankType,
)
from tests.integration.conftest import (
    clear_enemies,
    clear_tiles,
    first_player,
    let_spawning_enemies_appear,
    place_ice_patch,
    place_player_at,
    spawn_enemy_at,
    start_game,
    tick,
    use_roster,
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


def _open_field(gm):
    """No Enemies to come and an open field across rows 4-13."""
    clear_enemies(gm)
    clear_tiles(gm.battle.map, [(x, y) for x in range(26) for y in range(4, 14)])


@pytest.fixture
def game(game_manager_fixture):
    """A Battle with no Enemies to come and an open field across rows 4-13."""
    _open_field(game_manager_fixture)
    return game_manager_fixture


def _clock(game):
    game.battle.apply_outcomes(
        [PowerUpCollected(PowerUpType.CLOCK, first_player(game))]
    )


def _hold(game, direction):
    game.battle.handle_event(
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


class TestClockFreezesEnemies:
    def test_engine_sound_stops_and_the_enemy_is_not_moving(self):
        recorder = _EngineRecorder()
        game = start_game(sound_manager=recorder)
        _open_field(game)
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
        _clock(game)
        tick(game, FPS)
        # A one-Enemy Roster: no more spawns while the Clock runs out.
        use_roster(game, {TankType.BASIC: 1})
        assert game.battle.start_spawning()
        let_spawning_enemies_appear(game)
        (enemy,) = game.battle.scene().enemies
        appeared_at = (enemy.x, enemy.y)

        assert enemy.is_frozen is True
        # Frozen, where it Appeared, until the Clock runs out.
        for _ in range(int(CLOCK_FREEZE_DURATION * FPS)):
            if not enemy.is_frozen:
                break
            assert (enemy.x, enemy.y) == appeared_at
            tick(game)

        assert enemy.is_frozen is False


class TestFrozenOnIce:
    @pytest.fixture
    def ice(self, game):
        place_ice_patch(game, 2, 6, width=22, height=2)
        return game

    def test_a_sliding_enemy_finishes_its_slide_then_stands_still(self, ice):
        enemy = _driving_enemy(ice, 4, 6, Direction.RIGHT)
        assert enemy.start_slide()
        slide_from = enemy.x
        tick(ice, 3)
        assert enemy.is_sliding

        _clock(ice)
        for _ in range(FPS):
            if not enemy.is_sliding:
                break
            tick(ice)
        slide_end = enemy.x
        tick(ice, 10)

        assert slide_end == pytest.approx(slide_from + ICE_SLIDE_DISTANCE)
        assert enemy.is_moving is False
        assert enemy.x == slide_end
