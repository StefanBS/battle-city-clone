import pytest
from unittest.mock import patch
from src.core.enemy_ai import EnemyAI
from src.utils.constants import FPS, TankType, Direction, Difficulty

BASE_POSITION = (256.0, 480.0)

EXPECTED_INTERVALS = {
    TankType.BASIC: (2.0, 2.5),
    TankType.FAST: (1.8, 1.5),
    TankType.POWER: (1.0, 2.0),
    TankType.ARMOR: (1.5, 2.0),
}


@pytest.fixture
def create_enemy_ai(create_enemy_tank):
    """Factory for an EnemyAI paired with a fresh EnemyTank."""

    def _create(
        tank_type=TankType.BASIC,
        difficulty=Difficulty.NORMAL,
        base_position=None,
        **tank_kwargs,
    ):
        tank = create_enemy_tank(tank_type=tank_type, **tank_kwargs)
        return EnemyAI(tank, difficulty=difficulty, base_position=base_position)

    return _create


class TestIntent:
    """Where the AI wants to go and when it wants to fire."""

    @pytest.mark.parametrize("tank_type, intervals", EXPECTED_INTERVALS.items())
    def test_intervals_come_from_the_tank_type(
        self, create_enemy_ai, tank_type, intervals
    ):
        ai = create_enemy_ai(tank_type=tank_type)

        assert ai.shoot_interval == pytest.approx(intervals[0])
        assert ai.direction_change_interval == pytest.approx(intervals[1])

    def test_wants_to_keep_going_the_way_the_tank_faces(self, create_enemy_ai):
        """Until the AI turns, an Enemy wants to drive the way it spawned facing."""
        ai = create_enemy_ai(x=128, y=128)

        assert ai.get_movement_direction() == Direction.DOWN.delta

    def test_consume_shoot_after_timer(self, create_enemy_ai):
        ai = create_enemy_ai()
        assert not ai.consume_shoot()

        ai.shoot_timer = ai.shoot_interval + 0.1
        ai.update(0.01)

        assert ai.consume_shoot() is True
        assert ai.consume_shoot() is False

    def test_update_does_not_move_or_turn_the_tank(self, create_enemy_ai):
        """The AI only records intent; turning and moving are left to TankStepper."""
        ai = create_enemy_ai(x=128, y=128, difficulty=Difficulty.EASY)
        tank = ai.tank
        tank.direction = Direction.RIGHT
        ai.direction_timer = ai.direction_change_interval

        with (
            patch("src.core.enemy_ai.random.uniform", return_value=0.0),
            patch("src.core.enemy_ai.random.choice", return_value=Direction.UP),
        ):
            ai.update(1.0 / FPS)

        assert ai.get_movement_direction() == Direction.UP.delta
        assert tank.direction == Direction.RIGHT
        assert (tank.x, tank.y) == (128, 128)
        assert ai.direction_timer == 0.0


class TestMovementBlocked:
    @patch("src.core.enemy_ai.random.choice", return_value=Direction.RIGHT)
    def test_blocked_tank_makes_the_ai_pick_a_new_direction(
        self, mock_choice, create_enemy_ai
    ):
        """Blocking the tank reaches its AI, which turns and resets its timer."""
        ai = create_enemy_ai(difficulty=Difficulty.EASY)
        tank = ai.tank
        tank.direction = Direction.UP
        ai.direction_timer = 1.5

        tank.on_movement_blocked()

        assert ai.get_movement_direction() == Direction.RIGHT.delta
        assert tank.direction == Direction.UP
        assert ai.direction_timer == 0
        assert Direction.UP in ai._blocked_directions

    @patch("src.core.enemy_ai.random.choice", return_value=Direction.DOWN)
    def test_blocked_avoids_blocked_dirs(self, mock_choice, create_enemy_ai):
        """Consecutive wall hits accumulate blocked directions."""
        ai = create_enemy_ai(difficulty=Difficulty.EASY)
        ai._blocked_directions.add(Direction.UP)
        ai.tank.direction = Direction.RIGHT

        ai.tank.on_movement_blocked()

        assert ai._blocked_directions == {Direction.UP, Direction.RIGHT}
        candidates = mock_choice.call_args[0][0]
        assert set(candidates) == {Direction.DOWN}
        assert ai.get_movement_direction() == Direction.DOWN.delta

    def test_blocked_directions_persist_until_movement(self, create_enemy_ai):
        ai = create_enemy_ai(difficulty=Difficulty.EASY)
        ai._blocked_directions.update({Direction.UP, Direction.LEFT})
        ai.tank.prev_x, ai.tank.prev_y = ai.tank.x, ai.tank.y

        ai.update(1.0 / 60)

        assert ai._blocked_directions == {Direction.UP, Direction.LEFT}

    def test_blocked_directions_cleared_on_successful_move(self, create_enemy_ai):
        ai = create_enemy_ai(difficulty=Difficulty.EASY)
        ai._blocked_directions.add(Direction.UP)
        ai.tank.prev_x = ai.tank.x + 32.0

        ai.update(1.0 / 60)

        assert ai._blocked_directions == set()


class TestBiases:
    """Difficulty-based bias computation and weighting."""

    def test_normal_difficulty_basic_tank_biases(self, create_enemy_ai):
        """Basic tank on Normal: 0.3*0.5=0.15 base, 0.2*0.5=0.1 player."""
        ai = create_enemy_ai()
        assert ai.effective_base_bias == pytest.approx(0.15)
        assert ai.effective_player_bias == pytest.approx(0.1)

    def test_normal_difficulty_armor_tank_biases(self, create_enemy_ai):
        """Armor tank on Normal: 0.3*1.5=0.45 base, 0.2*0.5=0.1 player."""
        ai = create_enemy_ai(tank_type=TankType.ARMOR)
        assert ai.effective_base_bias == pytest.approx(0.45)
        assert ai.effective_player_bias == pytest.approx(0.1)

    def test_easy_difficulty_all_biases_zero(self, create_enemy_ai):
        ai = create_enemy_ai(tank_type=TankType.POWER, difficulty=Difficulty.EASY)
        assert ai.effective_base_bias == pytest.approx(0.0)
        assert ai.effective_player_bias == pytest.approx(0.0)

    def test_aligned_shoot_multiplier_stored(self, create_enemy_ai):
        ai = create_enemy_ai()
        assert ai.aligned_shoot_multiplier == pytest.approx(0.5)

    @patch("src.core.enemy_ai.random.choices", return_value=[Direction.DOWN])
    def test_change_direction_weights_toward_base(self, mock_choices, create_enemy_ai):
        """With the base below, DOWN gets the armor tank's 0.45 base bias."""
        ai = create_enemy_ai(tank_type=TankType.ARMOR, base_position=BASE_POSITION)
        ai.tank.direction = Direction.LEFT
        ai.direction_timer = ai.direction_change_interval + 1

        ai.update(0.01)

        candidates, weights = mock_choices.call_args[0]
        assert weights[candidates.index(Direction.DOWN)] == pytest.approx(1.45)

    @patch("src.core.enemy_ai.random.choices", return_value=[Direction.RIGHT])
    def test_change_direction_weights_toward_player(
        self, mock_choices, create_enemy_ai
    ):
        """With the player to the right, RIGHT gets the fast tank's 0.3 bias."""
        ai = create_enemy_ai(tank_type=TankType.FAST, base_position=BASE_POSITION)
        ai.tank.direction = Direction.UP
        ai.direction_timer = ai.direction_change_interval + 1
        ai.target_position = (400.0, 0.0)

        ai.update(0.01)

        candidates, weights = mock_choices.call_args[0]
        assert weights[candidates.index(Direction.RIGHT)] >= 1.0 + 0.3

    @patch("src.core.enemy_ai.random.choices")
    def test_easy_difficulty_equal_weights(self, mock_choices, create_enemy_ai):
        """On Easy, biases are zero so random.choice is used, not choices."""
        ai = create_enemy_ai(difficulty=Difficulty.EASY, base_position=BASE_POSITION)
        ai.tank.direction = Direction.LEFT
        ai.direction_timer = ai.direction_change_interval + 1
        ai.target_position = (400.0, 400.0)

        ai.update(0.01)

        mock_choices.assert_not_called()

    def test_no_target_position_uses_base_only(self, create_enemy_ai):
        ai = create_enemy_ai(tank_type=TankType.ARMOR, base_position=BASE_POSITION)
        ai.tank.direction = Direction.LEFT
        ai.direction_timer = ai.direction_change_interval + 1

        with patch(
            "src.core.enemy_ai.random.choices", return_value=[Direction.DOWN]
        ) as mock_choices:
            ai.update(0.01)

        candidates, weights = mock_choices.call_args[0]
        assert weights[candidates.index(Direction.DOWN)] == pytest.approx(1.45)


class TestAlignedShooting:
    def test_aligned_shooting_reduces_interval(self, create_enemy_ai):
        """Facing the player and aligned, the shoot interval is halved."""
        ai = create_enemy_ai(x=100)
        ai.tank.direction = Direction.DOWN
        ai.shoot_timer = ai.shoot_interval * 0.5 + 0.01
        ai.target_position = (100.0, 300.0)

        ai.update(0.01)

        assert ai.consume_shoot() is True

    def test_not_aligned_uses_normal_interval(self, create_enemy_ai):
        ai = create_enemy_ai(x=100)
        ai.tank.direction = Direction.LEFT
        ai.shoot_timer = ai.shoot_interval * 0.5 + 0.01
        ai.target_position = (100.0, 300.0)

        ai.update(0.01)

        assert ai.consume_shoot() is False

    @pytest.mark.parametrize(
        "direction, tank_pos, target_pos, expected_aligned",
        [
            (Direction.DOWN, (100, 0), (100, 300), True),
            (Direction.UP, (100, 300), (100, 0), True),
            (Direction.RIGHT, (0, 100), (300, 100), True),
            (Direction.LEFT, (300, 100), (0, 100), True),
            (Direction.UP, (100, 0), (100, 300), False),  # target behind
            (Direction.DOWN, (100, 300), (100, 0), False),  # target behind
            (Direction.DOWN, (100, 0), (300, 300), False),  # different X
        ],
    )
    def test_alignment_detection(
        self, direction, tank_pos, target_pos, expected_aligned, create_enemy_ai
    ):
        ai = create_enemy_ai(
            x=tank_pos[0], y=tank_pos[1], map_width_px=512, map_height_px=512
        )
        ai.tank.direction = direction
        assert ai._is_aligned_with(target_pos) == expected_aligned
