"""Unit tests for TankStepper."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.bullet import Bullet
from src.core.map import Map
from src.core.tank import Tank
from src.managers.tank_stepper import StepResult, TankStepper
from src.utils.constants import TILE_SIZE, Direction

DT = 1.0 / 60


class FakeIntent:
    """An intent holding one direction and an optional queued shot."""

    def __init__(self, direction: tuple[int, int] = (0, 0), shoot: bool = False):
        self.direction = direction
        self.shoot = shoot

    def get_movement_direction(self) -> tuple[int, int]:
        return self.direction

    def consume_shoot(self) -> bool:
        fired, self.shoot = self.shoot, False
        return fired


@pytest.fixture
def game_map():
    game_map = MagicMock(spec=Map)
    game_map.is_tile_slidable.return_value = False
    return game_map


@pytest.fixture
def stepper(game_map):
    return TankStepper(game_map)


@pytest.fixture
def tank():
    tank = MagicMock(spec=Tank)
    tank.x = 0.0
    tank.y = 0.0
    tank.width = TILE_SIZE
    tank.height = TILE_SIZE
    tank.direction = Direction.UP
    tank.is_sliding = False
    tank.max_bullets = 1
    tank.start_slide.return_value = True
    tank.shoot.side_effect = lambda: _bullet(tank)
    return tank


def _bullet(owner, active: bool = True) -> Bullet:
    bullet = MagicMock(spec=Bullet)
    bullet.owner = owner
    bullet.active = active
    return bullet


class TestStepping:
    def test_runs_tank_update_first(self, stepper, tank):
        stepper.step(tank, FakeIntent(), DT)

        tank.update.assert_called_once_with(DT)

    def test_moves_in_intended_direction(self, stepper, tank):
        stepper.step(tank, FakeIntent((1, 0)), DT)

        tank.move.assert_called_once_with(1, 0, DT)

    @pytest.mark.parametrize("direction", [(0, 0), (1, -1)])
    def test_no_move_without_a_single_direction(self, stepper, tank, direction):
        stepper.step(tank, FakeIntent(direction), DT)

        tank.move.assert_not_called()

    def test_sliding_tank_does_not_move(self, stepper, tank):
        tank.is_sliding = True

        stepper.step(tank, FakeIntent((0, -1)), DT)

        tank.move.assert_not_called()

    def test_reports_nothing_on_a_plain_move(self, stepper, tank):
        assert stepper.step(tank, FakeIntent((0, -1)), DT) == StepResult()


class TestIce:
    def test_ice_flag_comes_from_where_the_tank_stands_after_update(
        self, stepper, tank, game_map
    ):
        def slide_forward(dt):
            tank.x = 64.0

        tank.update.side_effect = slide_forward

        stepper.step(tank, FakeIntent(), DT)

        game_map.is_tile_slidable.assert_called_once_with(
            64.0, 0.0, TILE_SIZE, TILE_SIZE
        )

    def test_ice_flag_set_before_slide_starts(self, stepper, tank, game_map):
        game_map.is_tile_slidable.return_value = True
        flag_at_slide = []
        tank.start_slide.side_effect = lambda: flag_at_slide.append(tank.on_ice)

        stepper.step(tank, FakeIntent(), DT)

        assert flag_at_slide == [True]

    @pytest.mark.parametrize(
        "direction", [(0, 0), (1, 0), (0, 1)], ids=["none", "turn", "reverse"]
    )
    def test_slides_on_ice_unless_holding_facing(
        self, stepper, tank, game_map, direction
    ):
        game_map.is_tile_slidable.return_value = True

        result = stepper.step(tank, FakeIntent(direction), DT)

        tank.start_slide.assert_called_once()
        assert result.slide_started is True

    def test_no_slide_holding_facing_on_ice(self, stepper, tank, game_map):
        game_map.is_tile_slidable.return_value = True

        stepper.step(tank, FakeIntent((0, -1)), DT)

        tank.start_slide.assert_not_called()
        tank.move.assert_called_once_with(0, -1, DT)

    def test_no_slide_off_ice(self, stepper, tank):
        stepper.step(tank, FakeIntent(), DT)

        tank.start_slide.assert_not_called()

    def test_no_new_slide_while_sliding(self, stepper, tank, game_map):
        game_map.is_tile_slidable.return_value = True
        tank.is_sliding = True

        stepper.step(tank, FakeIntent(), DT)

        tank.start_slide.assert_not_called()

    def test_rejected_slide_is_not_reported(self, stepper, tank, game_map):
        game_map.is_tile_slidable.return_value = True
        tank.start_slide.return_value = False

        result = stepper.step(tank, FakeIntent((1, 0)), DT)

        assert result.slide_started is False
        tank.move.assert_called_once_with(1, 0, DT)

    def test_started_slide_holds_the_turn(self, stepper, tank, game_map):
        game_map.is_tile_slidable.return_value = True

        def begin_slide():
            tank.is_sliding = True
            return True

        tank.start_slide.side_effect = begin_slide

        stepper.step(tank, FakeIntent((1, 0)), DT)

        tank.move.assert_not_called()


class TestFiring:
    def test_fires_when_intent_shoots(self, stepper, tank):
        result = stepper.step(tank, FakeIntent(shoot=True), DT)

        tank.shoot.assert_called_once()
        assert result.fired is True
        assert [b.owner for b in stepper.bullets] == [tank]

    def test_no_shot_without_intent(self, stepper, tank):
        result = stepper.step(tank, FakeIntent(), DT)

        tank.shoot.assert_not_called()
        assert result.fired is False

    def test_fires_after_moving(self, stepper, tank):
        calls = []
        tank.move.side_effect = lambda *a: calls.append("move")
        tank.shoot.side_effect = lambda: calls.append("shoot")

        stepper.step(tank, FakeIntent((0, -1), shoot=True), DT)

        assert calls == ["move", "shoot"]

    def test_bullet_cap_blocks_extra_shot(self, stepper, tank):
        stepper.step(tank, FakeIntent(shoot=True), DT)

        result = stepper.step(tank, FakeIntent(shoot=True), DT)

        assert tank.shoot.call_count == 1
        assert result.fired is False

    def test_bullet_cap_of_two(self, stepper, tank):
        tank.max_bullets = 2

        for _ in range(3):
            stepper.step(tank, FakeIntent(shoot=True), DT)

        assert len(stepper.bullets) == 2

    def test_cap_counts_only_own_bullets(self, stepper, tank):
        other = MagicMock(spec=Tank)
        other.max_bullets = 1
        other.shoot.side_effect = lambda: _bullet(other)
        other.x = other.y = 0.0
        other.width = other.height = TILE_SIZE
        other.direction = Direction.UP
        other.is_sliding = False
        stepper.step(other, FakeIntent(shoot=True), DT)

        result = stepper.step(tank, FakeIntent(shoot=True), DT)

        assert result.fired is True

    def test_inactive_bullet_frees_the_cap(self, stepper, tank):
        stepper.step(tank, FakeIntent(shoot=True), DT)
        stepper.bullets[0].active = False

        result = stepper.step(tank, FakeIntent(shoot=True), DT)

        assert result.fired is True

    def test_refused_shot_is_not_reported(self, stepper, tank):
        tank.shoot.side_effect = None
        tank.shoot.return_value = None

        result = stepper.step(tank, FakeIntent(shoot=True), DT)

        assert result.fired is False
        assert stepper.bullets == []


class TestBullets:
    def test_starts_empty(self, stepper):
        assert stepper.bullets == []

    def test_update_bullets_advances_each(self, stepper, tank):
        stepper.step(tank, FakeIntent(shoot=True), DT)

        stepper.update_bullets(DT)

        stepper.bullets[0].update.assert_called_once_with(DT)

    def test_update_bullets_prunes_inactive(self, stepper, tank):
        stepper.step(tank, FakeIntent(shoot=True), DT)
        stepper.bullets[0].active = False

        stepper.update_bullets(DT)

        assert stepper.bullets == []
