import pytest
from unittest.mock import MagicMock, patch
from src.managers.enemy_manager import EnemyManager
from src.core.enemy_ai import EnemyAI
from src.core.enemy_tank import EnemyTank
from src.core.player_tank import PlayerTank
from src.managers.tank_stepper import StepResult, TankStepper
from src.utils.constants import Difficulty

DT = 1.0 / 60


@pytest.fixture
def stepper():
    """A TankStepper whose steps report that nothing happened."""
    stepper = MagicMock(spec=TankStepper)
    stepper.step.return_value = StepResult()
    return stepper


@pytest.fixture
def enemy_manager():
    return EnemyManager()


@pytest.fixture
def make_enemy():
    """Build a mock Enemy at (x, y), not yet on the battlefield."""
    next_id = iter(range(1000, 2000))

    def _make(x=0, y=0):
        enemy = MagicMock(spec=EnemyTank)
        enemy.x, enemy.y = x, y
        enemy.enemy_id = next(next_id)
        return enemy

    return _make


@pytest.fixture
def add_enemy(enemy_manager, make_enemy):
    """Put an Enemy at (x, y) on the battlefield and return it with its AI."""

    def _add(x, y):
        enemy = make_enemy(x, y)
        ai = MagicMock(spec=EnemyAI)
        enemy_manager.add(enemy, ai)
        return enemy, ai

    return _add


def _player(x, y):
    player = MagicMock(spec=PlayerTank)
    player.x, player.y = x, y
    return player


class TestEnemyAIPairing:
    """Each Enemy is paired with the EnemyAI that drives it."""

    @pytest.fixture
    def enemy_ai_class(self):
        """EnemyAI patched so each Enemy gets its own recognisable mock AI."""
        built: list[MagicMock] = []

        def build(*args, **kwargs):
            built.append(MagicMock(spec=EnemyAI))
            return built[-1]

        with patch("src.managers.enemy_manager.EnemyAI") as enemy_ai_class:
            enemy_ai_class.side_effect = build
            enemy_ai_class.built = built
            yield enemy_ai_class

    @pytest.fixture
    def enemy_manager(self):
        return EnemyManager(difficulty=Difficulty.EASY, base_position=(256.0, 480.0))

    def test_added_enemy_gets_an_ai_for_the_stage_base_and_difficulty(
        self, enemy_manager, enemy_ai_class, make_enemy
    ):
        enemy = make_enemy()

        enemy_manager.add(enemy)

        enemy_ai_class.assert_called_once_with(
            enemy, difficulty=Difficulty.EASY, base_position=(256.0, 480.0)
        )
        assert enemy_manager.base_position == (256.0, 480.0)

    def test_added_enemy_is_driven_by_its_own_ai(
        self, enemy_manager, enemy_ai_class, make_enemy, stepper
    ):
        enemy = make_enemy()
        enemy_manager.add(enemy)
        (ai,) = enemy_ai_class.built

        enemy_manager.step_enemies(DT, stepper, [])

        ai.update.assert_called_once_with(DT, None)
        stepper.step.assert_called_once_with(enemy, ai, DT)


class TestRemove:
    def test_removed_enemy_is_no_longer_driven(self, enemy_manager, add_enemy, stepper):
        enemy, _ = add_enemy(0, 0)
        enemy_manager.remove(enemy)

        enemy_manager.step_enemies(DT, stepper, [])

        stepper.step.assert_not_called()

    def test_removing_an_enemy_already_gone_reports_it(self, enemy_manager, add_enemy):
        enemy, _ = add_enemy(0, 0)
        enemy_manager.remove(enemy)

        assert enemy_manager.remove(enemy) is False


class TestStepEnemies:
    """Each frame, every Enemy's AI decides and TankStepper steps the Enemy."""

    def test_each_enemy_steers_toward_its_own_nearest_player(
        self, enemy_manager, stepper, add_enemy
    ):
        _, left_ai = add_enemy(0, 200)
        _, right_ai = add_enemy(480, 200)
        players = [_player(40, 200), _player(440, 200)]

        enemy_manager.step_enemies(DT, stepper, players)

        left_ai.update.assert_called_once_with(DT, (40, 200))
        right_ai.update.assert_called_once_with(DT, (440, 200))

    def test_reports_no_shot_when_no_enemy_fired(
        self, enemy_manager, stepper, add_enemy
    ):
        add_enemy(0, 0)
        add_enemy(200, 0)

        assert enemy_manager.step_enemies(DT, stepper, []) is False

    def test_reports_a_shot_when_any_enemy_fired(
        self, enemy_manager, stepper, add_enemy
    ):
        add_enemy(0, 0)
        add_enemy(200, 0)
        stepper.step.side_effect = [StepResult(fired=True), StepResult()]

        assert enemy_manager.step_enemies(DT, stepper, []) is True
        assert stepper.step.call_count == 2


class TestFrozen:
    """A Clock makes every Enemy Frozen for its duration."""

    def test_frozen_enemies_are_not_stepped(self, enemy_manager, stepper, add_enemy):
        _, ai = add_enemy(100, 100)
        enemy_manager.freeze(5.0)

        fired = enemy_manager.step_enemies(DT, stepper, [_player(0, 0)])

        assert fired is False
        ai.update.assert_not_called()
        stepper.step.assert_not_called()

    def test_a_clock_lasts_one_frame_per_dt_of_its_duration(
        self, enemy_manager, stepper, add_enemy
    ):
        dt = 0.25  # Exact in binary, so the countdown has no rounding.
        add_enemy(100, 100)
        enemy_manager.freeze(3 * dt)

        frozen_frames = 0
        while not stepper.step.called:
            enemy_manager.step_enemies(dt, stepper, [])
            frozen_frames += 0 if stepper.step.called else 1

        assert frozen_frames == 3
        assert not enemy_manager.enemies_frozen
