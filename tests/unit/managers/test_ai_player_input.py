from unittest.mock import MagicMock

import pygame
import pytest

from src.core.player_tank import PlayerTank
from src.managers.ai_player_input import (
    AIPlayerInput,
    _reset_ai_teammate_config,
)
from src.utils.constants import TILE_SIZE, Direction


@pytest.fixture(autouse=True)
def reset_config():
    _reset_ai_teammate_config()
    yield
    _reset_ai_teammate_config()


@pytest.fixture
def mock_player_tank():
    tank = MagicMock(spec=PlayerTank)
    tank.x = 0.0
    tank.y = 0.0
    tank.prev_x = 0.0
    tank.prev_y = 0.0
    tank.is_frozen = False
    tank.tile_size = TILE_SIZE
    tank.direction = Direction.UP
    return tank


class TestProtocolMethods:
    def test_handle_event_is_noop(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        ai.handle_event(event)

    def test_get_movement_direction_starts_zero(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        assert ai.get_movement_direction() == (0, 0)

    def test_consume_shoot_starts_false(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        assert ai.consume_shoot() is False

    def test_consume_shoot_drains_flag(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._wants_shoot = True
        assert ai.consume_shoot() is True
        assert ai.consume_shoot() is False

    def test_clear_pending_shoot(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._wants_shoot = True
        ai.clear_pending_shoot()
        assert ai.consume_shoot() is False


class TestConfigLoader:
    def test_loads_config_fields(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        assert ai._direction_change_interval == 0.5
        assert ai._shoot_interval == 0.8
        assert ai._aligned_shoot_multiplier == 0.3

    def test_config_cached(self, mock_player_tank):
        AIPlayerInput(tank=mock_player_tank)
        from src.managers import ai_player_input as mod

        assert mod._ai_teammate_config is not None


class TestBlockMemory:
    def test_cleared_when_tank_moved(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._blocked_directions.add(Direction.UP)
        mock_player_tank.prev_x = 0.0
        mock_player_tank.prev_y = 0.0
        mock_player_tank.x = 10.0
        mock_player_tank.y = 0.0
        ai.update(dt=1 / 60, enemies=[], teammate=None)
        assert Direction.UP not in ai._blocked_directions

    def test_added_when_tank_did_not_move_with_nonzero_intent(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._dx, ai._dy = 0, -1
        mock_player_tank.direction = Direction.UP
        mock_player_tank.prev_x = 0.0
        mock_player_tank.prev_y = 0.0
        mock_player_tank.x = 0.0
        mock_player_tank.y = 0.0
        ai.update(dt=1 / 60, enemies=[], teammate=None)
        assert Direction.UP in ai._blocked_directions
        assert ai._direction_timer == 0.0

    def test_not_added_when_frozen(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._dx, ai._dy = 0, -1
        mock_player_tank.direction = Direction.UP
        mock_player_tank.prev_x = 0.0
        mock_player_tank.prev_y = 0.0
        mock_player_tank.x = 0.0
        mock_player_tank.y = 0.0
        mock_player_tank.is_frozen = True
        ai.update(dt=1 / 60, enemies=[], teammate=None)
        assert ai._blocked_directions == set()

    def test_not_added_when_intent_is_zero(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._dx, ai._dy = 0, 0
        mock_player_tank.direction = Direction.UP
        mock_player_tank.prev_x = mock_player_tank.x = 0.0
        mock_player_tank.prev_y = mock_player_tank.y = 0.0
        ai.update(dt=1 / 60, enemies=[], teammate=None)
        assert ai._blocked_directions == set()


class TestTimerAdvancement:
    def test_direction_timer_advances(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai.update(dt=0.1, enemies=[], teammate=None)
        assert ai._direction_timer == pytest.approx(0.1)

    def test_shoot_timer_advances(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai.update(dt=0.1, enemies=[], teammate=None)
        assert ai._shoot_timer == pytest.approx(0.1)
