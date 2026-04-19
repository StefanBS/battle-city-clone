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
