from unittest.mock import MagicMock

import pygame
import pytest

from src.core.enemy_tank import EnemyTank
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


class TestReset:
    def test_reset_clears_transient_state(self, mock_player_tank):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._dx, ai._dy = 1, 0
        ai._wants_shoot = True
        ai._direction_timer = 0.42
        ai._shoot_timer = 0.7
        ai._blocked_directions = {Direction.UP, Direction.LEFT}
        ai.reset()
        assert (ai._dx, ai._dy) == (0, 0)
        assert ai.consume_shoot() is False
        assert ai._direction_timer == 0.0
        assert ai._shoot_timer == 0.0
        assert ai._blocked_directions == set()


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


@pytest.fixture
def mock_enemy_factory():
    def _make(x: float, y: float) -> MagicMock:
        e = MagicMock(spec=EnemyTank)
        e.x = x
        e.y = y
        return e

    return _make


class TestRoleSelection:
    def test_hunter_when_no_enemies(self, mock_player_tank, monkeypatch):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._direction_timer = ai._direction_change_interval
        captured = {}

        def fake_choices(candidates, weights):
            captured["weights"] = weights
            return [candidates[0]]

        monkeypatch.setattr("src.managers.ai_player_input.random.choices", fake_choices)
        monkeypatch.setattr(EnemyTank, "base_position", (100.0, 100.0))
        ai.update(dt=0.01, enemies=[], teammate=None)
        assert all(w == 1.0 for w in captured["weights"])

    def test_defender_when_enemy_near_base(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._direction_timer = ai._direction_change_interval
        # Base at origin, tank 5 tiles to the right, enemy 1 tile from base.
        monkeypatch.setattr(EnemyTank, "base_position", (0.0, 0.0))
        mock_player_tank.x = 5 * TILE_SIZE
        mock_player_tank.y = 0.0
        # Face UP so LEFT (toward base) is not the excluded opposite.
        mock_player_tank.direction = Direction.UP

        close_enemy = mock_enemy_factory(TILE_SIZE, 0.0)

        captured = {}

        def fake_choices(candidates, weights):
            captured["candidates"] = candidates
            captured["weights"] = weights
            return [candidates[0]]

        monkeypatch.setattr("src.managers.ai_player_input.random.choices", fake_choices)
        ai.update(dt=0.01, enemies=[close_enemy], teammate=None)
        assert max(captured["weights"]) >= 1.0 + ai._defender_base_bias

    def test_hunter_when_base_position_is_none(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._direction_timer = ai._direction_change_interval
        monkeypatch.setattr(EnemyTank, "base_position", None)
        # Face UP so RIGHT (toward enemy) is not the excluded opposite.
        mock_player_tank.direction = Direction.UP
        enemy = mock_enemy_factory(100.0, 0.0)

        captured = {}

        def fake_choices(candidates, weights):
            captured["weights"] = weights
            return [candidates[0]]

        monkeypatch.setattr("src.managers.ai_player_input.random.choices", fake_choices)
        ai.update(dt=0.01, enemies=[enemy], teammate=None)
        assert max(captured["weights"]) == pytest.approx(1.0 + ai._hunter_target_bias)


class TestDirectionCandidates:
    def test_blocked_directions_excluded(self, mock_player_tank, monkeypatch):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._blocked_directions = {Direction.UP}
        ai._direction_timer = ai._direction_change_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)

        captured = {}

        def fake_choices(candidates, weights):
            captured["candidates"] = list(candidates)
            return [candidates[0]]

        monkeypatch.setattr("src.managers.ai_player_input.random.choices", fake_choices)
        ai.update(dt=0.01, enemies=[], teammate=None)
        assert Direction.UP not in captured["candidates"]

    def test_opposite_direction_excluded_when_others_available(
        self, mock_player_tank, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._direction_timer = ai._direction_change_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)

        captured = {}

        def fake_choices(candidates, weights):
            captured["candidates"] = list(candidates)
            return [candidates[0]]

        monkeypatch.setattr("src.managers.ai_player_input.random.choices", fake_choices)
        ai.update(dt=0.01, enemies=[], teammate=None)
        assert Direction.LEFT not in captured["candidates"]

    def test_opposite_allowed_when_only_option(self, mock_player_tank, monkeypatch):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._blocked_directions = {Direction.UP, Direction.DOWN, Direction.RIGHT}
        ai._direction_timer = ai._direction_change_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)

        captured = {}

        def fake_choices(candidates, weights):
            captured["candidates"] = list(candidates)
            return [candidates[0]]

        monkeypatch.setattr("src.managers.ai_player_input.random.choices", fake_choices)
        ai.update(dt=0.01, enemies=[], teammate=None)
        assert Direction.LEFT in captured["candidates"]


class TestDirectionPicking:
    def test_timer_resets_with_jitter(self, mock_player_tank, monkeypatch):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._direction_timer = ai._direction_change_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)
        monkeypatch.setattr(
            "src.managers.ai_player_input.random.choices",
            lambda c, w: [c[0]],
        )
        monkeypatch.setattr(
            "src.managers.ai_player_input.random.uniform", lambda a, b: 0.03
        )
        ai.update(dt=0.01, enemies=[], teammate=None)
        assert ai._direction_timer == pytest.approx(0.03)

    def test_dx_dy_set_from_picked_direction(self, mock_player_tank, monkeypatch):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._direction_timer = ai._direction_change_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)

        monkeypatch.setattr(
            "src.managers.ai_player_input.random.choices",
            lambda c, w: [Direction.DOWN],
        )
        monkeypatch.setattr(
            "src.managers.ai_player_input.random.uniform", lambda a, b: 0.0
        )
        ai.update(dt=0.01, enemies=[], teammate=None)
        assert (ai._dx, ai._dy) == Direction.DOWN.delta


class TestShooting:
    def test_fires_when_timer_exceeds_interval(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._shoot_timer = ai._shoot_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)
        monkeypatch.setattr(
            "src.managers.ai_player_input.random.uniform", lambda a, b: 0.0
        )
        ai.update(
            dt=0.01,
            enemies=[mock_enemy_factory(100.0, 0.0)],
            teammate=None,
        )
        assert ai.consume_shoot() is True
        assert ai._shoot_timer == 0.0

    def test_does_not_fire_before_interval(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._shoot_timer = 0.0
        mock_player_tank.direction = Direction.UP
        monkeypatch.setattr(EnemyTank, "base_position", None)
        ai.update(
            dt=0.01,
            enemies=[mock_enemy_factory(0.0, -100.0)],
            teammate=None,
        )
        assert ai.consume_shoot() is False

    def test_aligned_shoot_fires_early(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._shoot_timer = ai._shoot_interval * ai._aligned_shoot_multiplier + 0.01
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)
        monkeypatch.setattr(
            "src.managers.ai_player_input.random.uniform", lambda a, b: 0.0
        )
        aligned_enemy = mock_enemy_factory(5 * TILE_SIZE, 0.0)
        ai.update(dt=0.01, enemies=[aligned_enemy], teammate=None)
        assert ai.consume_shoot() is True

    def test_aligned_shoot_misaligned_does_not_fire_early(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._shoot_timer = ai._shoot_interval * ai._aligned_shoot_multiplier + 0.01
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)
        perp_enemy = mock_enemy_factory(0.0, 5 * TILE_SIZE)
        ai.update(dt=0.01, enemies=[perp_enemy], teammate=None)
        assert ai.consume_shoot() is False


class TestFriendlyFireSuppression:
    def test_suppresses_when_teammate_in_line(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._shoot_timer = ai._shoot_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)

        teammate = MagicMock(spec=PlayerTank)
        teammate.x = 2 * TILE_SIZE
        teammate.y = 0.0
        teammate.health = 1

        pre_timer = ai._shoot_timer
        ai.update(
            dt=0.01,
            enemies=[mock_enemy_factory(10 * TILE_SIZE, 0.0)],
            teammate=teammate,
        )
        assert ai.consume_shoot() is False
        assert ai._shoot_timer >= pre_timer

    def test_fires_when_no_teammate(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._shoot_timer = ai._shoot_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)
        monkeypatch.setattr(
            "src.managers.ai_player_input.random.uniform", lambda a, b: 0.0
        )
        ai.update(
            dt=0.01,
            enemies=[mock_enemy_factory(5 * TILE_SIZE, 0.0)],
            teammate=None,
        )
        assert ai.consume_shoot() is True

    def test_fires_when_teammate_perpendicular(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._shoot_timer = ai._shoot_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)
        monkeypatch.setattr(
            "src.managers.ai_player_input.random.uniform", lambda a, b: 0.0
        )

        teammate = MagicMock(spec=PlayerTank)
        teammate.x = 0.0
        teammate.y = 5 * TILE_SIZE
        teammate.health = 1

        ai.update(
            dt=0.01,
            enemies=[mock_enemy_factory(10 * TILE_SIZE, 0.0)],
            teammate=teammate,
        )
        assert ai.consume_shoot() is True

    def test_fires_when_teammate_behind_ai(
        self, mock_player_tank, mock_enemy_factory, monkeypatch
    ):
        ai = AIPlayerInput(tank=mock_player_tank)
        ai._shoot_timer = ai._shoot_interval
        mock_player_tank.direction = Direction.RIGHT
        monkeypatch.setattr(EnemyTank, "base_position", None)
        monkeypatch.setattr(
            "src.managers.ai_player_input.random.uniform", lambda a, b: 0.0
        )

        teammate = MagicMock(spec=PlayerTank)
        teammate.x = -2 * TILE_SIZE
        teammate.y = 0.0
        teammate.health = 1

        ai.update(
            dt=0.01,
            enemies=[mock_enemy_factory(10 * TILE_SIZE, 0.0)],
            teammate=teammate,
        )
        assert ai.consume_shoot() is True
