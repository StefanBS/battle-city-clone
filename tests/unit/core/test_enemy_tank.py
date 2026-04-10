import pytest
from unittest.mock import patch
from src.core.enemy_tank import EnemyTank, _get_enemy_config, _reset_enemy_config
from src.utils.constants import (
    TILE_SIZE,
    FPS,
    TankType,
    Direction,
    Difficulty,
    CARRIER_BLINK_INTERVAL,
)

# Define expected properties with resolved values matching enemy_types.json
EXPECTED_PROPERTIES = {
    TankType.BASIC: {
        "speed": 80,
        "bullet_speed": 180,
        "health": 1,
        "shoot_interval": 2.0,
        "direction_change_interval": 2.5,
    },
    TankType.FAST: {
        "speed": 120,
        "bullet_speed": 180,
        "health": 1,
        "shoot_interval": 1.8,
        "direction_change_interval": 1.5,
    },
    TankType.POWER: {
        "speed": 92,
        "bullet_speed": 360,
        "health": 1,
        "shoot_interval": 1.0,
        "direction_change_interval": 2.0,
    },
    TankType.ARMOR: {
        "speed": 60,
        "bullet_speed": 360,
        "health": 4,
        "shoot_interval": 1.5,
        "direction_change_interval": 2.0,
    },
}

# Test cases covering all tank types
TEST_CASES = [(tank_type, props) for tank_type, props in EXPECTED_PROPERTIES.items()]


@pytest.mark.parametrize("tank_type, expected", TEST_CASES)
def test_enemy_tank_initialization_properties(
    mock_texture_manager, tank_type: TankType, expected: dict
):
    """Test that EnemyTank initializes with correct properties for each type."""
    # Minimal required positional args for EnemyTank
    x, y = 0, 0
    tile_size = TILE_SIZE

    tank = EnemyTank(
        x,
        y,
        tile_size,
        mock_texture_manager,
        tank_type,
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )

    # Assert core properties set by the type
    assert tank.tank_type == tank_type
    assert tank.speed == pytest.approx(expected["speed"])
    assert tank.bullet_speed == pytest.approx(expected["bullet_speed"])
    assert tank.health == expected["health"]
    assert tank.max_health == expected["health"]  # Should also be set
    assert tank.shoot_interval == pytest.approx(expected["shoot_interval"])
    assert tank.direction_change_interval == pytest.approx(
        expected["direction_change_interval"]
    )

    # Assert other relevant properties
    assert tank.owner_type == "enemy"
    assert tank.lives == 1  # Enemies should have 1 life
    assert (
        tank.x == x
    )  # Check grid alignment effect is handled if needed (0 should be fine)
    assert tank.y == y


class TestEnemyConfigLoading:
    """Tests for enemy config JSON loading and caching."""

    def test_config_loads_all_types(self):
        config = _get_enemy_config()
        assert "basic" in config
        assert "fast" in config
        assert "power" in config
        assert "armor" in config

    def test_reset_clears_cache(self):
        _get_enemy_config()  # ensure loaded
        _reset_enemy_config()
        # After reset, next call reloads from file
        config = _get_enemy_config()
        assert config is not None
        assert "basic" in config

    def test_config_contains_difficulty_section(self):
        config = _get_enemy_config()
        assert "difficulty" in config
        assert "easy" in config["difficulty"]
        assert "normal" in config["difficulty"]

    def test_difficulty_config_has_required_keys(self):
        config = _get_enemy_config()
        for level in ("easy", "normal"):
            diff = config["difficulty"][level]
            assert "base_bias" in diff
            assert "player_bias" in diff
            assert "aligned_shoot_multiplier" in diff

    def test_type_configs_have_bias_multipliers(self):
        config = _get_enemy_config()
        for tank_type in ("basic", "fast", "power", "armor"):
            assert "base_bias_multiplier" in config[tank_type]
            assert "player_bias_multiplier" in config[tank_type]


def test_enemy_tank_grid_alignment(mock_texture_manager):
    """Test that initial position is aligned to the grid."""
    tile_size = 32
    # Non-aligned positions
    initial_x, initial_y = 15, 40
    expected_x, expected_y = (
        0 * tile_size,
        1 * tile_size,
    )  # round(15/32)*32=0, round(40/32)*32=32

    tank = EnemyTank(
        initial_x,
        initial_y,
        tile_size,
        mock_texture_manager,
        tank_type=TankType.BASIC,
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )

    assert tank.x == expected_x
    assert tank.y == expected_y
    assert tank.rect.x == expected_x
    assert tank.rect.y == expected_y


@patch("src.core.enemy_tank.DIFFICULTY", Difficulty.EASY)
@patch("src.core.enemy_tank.random.choice")
def test_on_movement_blocked(mock_random_choice, mock_texture_manager):
    """Test that on_movement_blocked changes direction and resets direction_timer."""
    mock_random_choice.return_value = Direction.DOWN
    tank = EnemyTank(
        0,
        0,
        TILE_SIZE,
        mock_texture_manager,
        tank_type=TankType.BASIC,
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )
    # Now set a known direction and mock the next choice
    tank.direction = Direction.UP
    tank.direction_timer = 1.5

    mock_random_choice.return_value = Direction.RIGHT
    tank.on_movement_blocked()

    assert tank.direction == Direction.RIGHT
    assert tank.direction_timer == 0
    assert Direction.UP in tank._blocked_directions


@patch("src.core.enemy_tank.DIFFICULTY", Difficulty.EASY)
@patch("src.core.enemy_tank.random.choice")
def test_blocked_avoids_blocked_dirs(mock_random_choice, mock_texture_manager):
    """Test that consecutive wall hits accumulate blocked directions."""
    mock_random_choice.return_value = Direction.DOWN
    tank = EnemyTank(
        0,
        0,
        TILE_SIZE,
        mock_texture_manager,
        tank_type=TankType.BASIC,
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )
    # Block UP, then RIGHT — only DOWN and LEFT remain as candidates
    tank.direction = Direction.UP
    tank._blocked_directions.add(Direction.UP)
    tank.direction = Direction.RIGHT
    mock_random_choice.return_value = Direction.DOWN
    tank.on_movement_blocked()
    assert Direction.RIGHT in tank._blocked_directions
    assert Direction.UP in tank._blocked_directions
    assert tank.direction == Direction.DOWN


@patch("src.core.enemy_tank.DIFFICULTY", Difficulty.EASY)
@patch("src.core.enemy_tank.random.choice")
def test_blocked_directions_persist_until_movement(
    mock_random_choice, mock_texture_manager
):
    """Blocked directions persist while stuck, clear on successful move."""
    mock_random_choice.return_value = Direction.DOWN
    tank = EnemyTank(
        0,
        0,
        TILE_SIZE,
        mock_texture_manager,
        tank_type=TankType.BASIC,
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )
    tank._blocked_directions.add(Direction.UP)
    tank._blocked_directions.add(Direction.LEFT)
    # Simulate a frame where the tank doesn't move (stuck)
    tank.x = 0
    tank.prev_x = 0
    tank.y = 0
    tank.prev_y = 0
    tank.update(1.0 / 60)
    # Blocked directions should persist (tank didn't move)
    assert Direction.UP in tank._blocked_directions
    assert Direction.LEFT in tank._blocked_directions


@patch("src.core.enemy_tank.DIFFICULTY", Difficulty.EASY)
@patch("src.core.enemy_tank.random.choice")
def test_blocked_directions_cleared_on_successful_move(
    mock_random_choice, mock_texture_manager
):
    """Blocked directions are cleared once the tank moves successfully."""
    mock_random_choice.return_value = Direction.DOWN
    tank = EnemyTank(
        0,
        0,
        TILE_SIZE,
        mock_texture_manager,
        tank_type=TankType.BASIC,
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )
    tank._blocked_directions.add(Direction.UP)
    # Simulate prev position differing from current (tank moved last frame)
    tank.prev_x = 32.0
    tank.prev_y = 0.0
    tank.update(1.0 / 60)
    assert len(tank._blocked_directions) == 0


def test_consume_shoot_after_timer(mock_texture_manager):
    """Test that EnemyTank signals shoot intent when timer fires."""
    tank = EnemyTank(
        0,
        0,
        TILE_SIZE,
        mock_texture_manager,
        tank_type=TankType.BASIC,
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )
    assert not tank.consume_shoot()

    tank.shoot_timer = tank.shoot_interval + 0.1
    tank.update(0.01)

    assert tank.consume_shoot() is True
    assert tank.consume_shoot() is False


@patch("src.core.enemy_tank.DIFFICULTY", Difficulty.EASY)
@patch("src.core.enemy_tank.random.choice")
@patch("src.core.enemy_tank.random.uniform", return_value=0.0)
def test_update_moves_in_current_direction(
    mock_uniform, mock_choice, mock_texture_manager
):
    """Test that update() moves the tank in its current direction."""
    mock_choice.return_value = Direction.DOWN
    tank = EnemyTank(
        0,
        0,
        TILE_SIZE,
        mock_texture_manager,
        tank_type=TankType.BASIC,
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )
    tank.direction = Direction.RIGHT
    # Set timers low so they don't trigger direction/shoot changes
    tank.direction_timer = 0
    tank.shoot_timer = 0
    initial_x = tank.x

    dt = 1.0 / FPS
    tank.update(dt)

    assert tank.x > initial_x
    assert tank.y == pytest.approx(0.0)


class TestEnemyTankCarrier:
    """Tests for the power-up carrier mechanic."""

    @pytest.fixture
    def carrier_tank(self, mock_texture_manager):
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            tank = EnemyTank(
                100,
                100,
                TILE_SIZE,
                mock_texture_manager,
                tank_type=TankType.BASIC,
                map_width_px=512,
                map_height_px=512,
                is_carrier=True,
            )
        tank.direction = Direction.DOWN
        return tank

    @pytest.fixture
    def normal_tank(self, mock_texture_manager):
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            tank = EnemyTank(
                100,
                100,
                TILE_SIZE,
                mock_texture_manager,
                tank_type=TankType.BASIC,
                map_width_px=512,
                map_height_px=512,
            )
        tank.direction = Direction.DOWN
        return tank

    def test_carrier_flag_default_false(self, normal_tank):
        assert normal_tank.is_carrier is False

    def test_carrier_flag_set_true(self, carrier_tank):
        assert carrier_tank.is_carrier is True

    def test_carrier_uses_red_sprite_during_blink(
        self, carrier_tank, mock_texture_manager
    ):
        mock_texture_manager.reset_mock()
        carrier_tank.update(CARRIER_BLINK_INTERVAL + 0.01)
        called_names = [
            c.args[0] for c in mock_texture_manager.get_sprite.call_args_list
        ]
        assert any("red" in name for name in called_names)

    def test_normal_tank_never_uses_red_sprite(self, normal_tank, mock_texture_manager):
        mock_texture_manager.reset_mock()
        normal_tank.update(1.0)
        called_names = [
            c.args[0] for c in mock_texture_manager.get_sprite.call_args_list
        ]
        assert not any("red" in name for name in called_names)

    def test_carrier_blink_timer_increments(self, carrier_tank):
        carrier_tank.update(0.1)
        assert carrier_tank.carrier_blink_timer > 0

    def test_normal_tank_carrier_blink_timer_stays_zero(self, normal_tank):
        normal_tank.update(0.1)
        assert normal_tank.carrier_blink_timer == 0.0

    def test_carrier_falls_back_on_missing_red_sprite(
        self, carrier_tank, mock_texture_manager
    ):
        """When a red sprite is missing, carrier falls back to normal sprite."""
        original_side_effect = mock_texture_manager.get_sprite.side_effect

        def reject_red(name):
            if "red" in name:
                raise KeyError(name)
            return mock_texture_manager.get_sprite.return_value

        mock_texture_manager.get_sprite.side_effect = reject_red
        try:
            carrier_tank.update(CARRIER_BLINK_INTERVAL + 0.01)
            assert carrier_tank.sprite is not None
        finally:
            mock_texture_manager.get_sprite.side_effect = original_side_effect


@patch("src.core.enemy_tank.DIFFICULTY", Difficulty.EASY)
class TestEnemyIceSlide:
    """Tests for enemy tank sliding on ice."""

    @pytest.fixture
    def enemy(self, mock_texture_manager):
        return EnemyTank(
            128,
            128,
            TILE_SIZE,
            mock_texture_manager,
            TankType.BASIC,
            map_width_px=16 * TILE_SIZE,
            map_height_px=16 * TILE_SIZE,
        )

    def test_direction_change_triggers_slide_on_ice(self, enemy):
        enemy._on_ice = True
        enemy._was_moving = True
        enemy.direction = Direction.RIGHT
        old_direction = enemy.direction
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.UP):
            enemy._change_direction()
        assert enemy._sliding is True
        assert enemy._slide_direction == old_direction

    def test_direction_change_no_slide_off_ice(self, enemy):
        enemy._on_ice = False
        enemy.direction = Direction.RIGHT
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.UP):
            enemy._change_direction()
        assert enemy._sliding is False

    def test_on_movement_blocked_cancels_slide(self, enemy):
        enemy._on_ice = True
        enemy._was_moving = True
        enemy.direction = Direction.RIGHT
        enemy.start_slide()
        enemy.on_movement_blocked()
        assert enemy._sliding is False


class TestEnemyAIBiases:
    """Tests for difficulty-based AI bias computation."""

    @pytest.fixture(autouse=True)
    def set_base_position(self):
        """Ensure base_position class attribute exists for AI tests."""
        EnemyTank.base_position = (256.0, 480.0)
        yield
        EnemyTank.base_position = None

    def test_normal_difficulty_basic_tank_biases(self, mock_texture_manager):
        """Basic tank on Normal: 0.3*0.5=0.15 base, 0.2*0.5=0.1 player."""
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    0,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.BASIC,
                    map_width_px=512,
                    map_height_px=512,
                )
        assert tank.effective_base_bias == pytest.approx(0.15)
        assert tank.effective_player_bias == pytest.approx(0.1)

    def test_normal_difficulty_armor_tank_biases(self, mock_texture_manager):
        """Armor tank on Normal: 0.3*1.5=0.45 base, 0.2*0.5=0.1 player."""
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    0,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.ARMOR,
                    map_width_px=512,
                    map_height_px=512,
                )
        assert tank.effective_base_bias == pytest.approx(0.45)
        assert tank.effective_player_bias == pytest.approx(0.1)

    def test_easy_difficulty_all_biases_zero(self, mock_texture_manager):
        """On Easy, all biases should be zero regardless of type."""
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.EASY):
                tank = EnemyTank(
                    0,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.POWER,
                    map_width_px=512,
                    map_height_px=512,
                )
        assert tank.effective_base_bias == pytest.approx(0.0)
        assert tank.effective_player_bias == pytest.approx(0.0)

    def test_aligned_shoot_multiplier_stored(self, mock_texture_manager):
        """Aligned shoot multiplier should be stored from difficulty config."""
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    0,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.BASIC,
                    map_width_px=512,
                    map_height_px=512,
                )
        assert tank.aligned_shoot_multiplier == pytest.approx(0.5)

    @patch("src.core.enemy_tank.random.choices")
    def test_change_direction_weights_toward_base(
        self, mock_choices, mock_texture_manager
    ):
        """When base is below, DOWN should get extra base_bias weight."""
        mock_choices.return_value = [Direction.DOWN]
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    0,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.ARMOR,
                    map_width_px=512,
                    map_height_px=512,
                )
        tank.direction = Direction.LEFT
        tank.direction_timer = tank.direction_change_interval + 1
        tank._blocked_directions.clear()

        tank.update(0.01, player_position=None)

        mock_choices.assert_called()
        candidates, weights = mock_choices.call_args[0]
        # DOWN should have highest weight (base bias for armor = 0.45)
        down_idx = candidates.index(Direction.DOWN)
        assert weights[down_idx] == pytest.approx(1.0 + 0.45)

    @patch("src.core.enemy_tank.random.choices")
    def test_change_direction_weights_toward_player(
        self, mock_choices, mock_texture_manager
    ):
        """When player is to the right, RIGHT should get extra player_bias weight."""
        mock_choices.return_value = [Direction.RIGHT]
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    0,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.FAST,
                    map_width_px=512,
                    map_height_px=512,
                )
        tank.direction = Direction.UP
        tank.direction_timer = tank.direction_change_interval + 1
        tank._blocked_directions.clear()

        tank.update(0.01, player_position=(400.0, 0.0))

        mock_choices.assert_called()
        candidates, weights = mock_choices.call_args[0]
        right_idx = candidates.index(Direction.RIGHT)
        # fast: player_bias = 0.2 * 1.5 = 0.3
        assert weights[right_idx] >= 1.0 + 0.3

    @patch("src.core.enemy_tank.random.choices")
    def test_easy_difficulty_equal_weights(self, mock_choices, mock_texture_manager):
        """On Easy, all candidate directions should have equal weight 1.0."""
        mock_choices.return_value = [Direction.DOWN]
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.EASY):
                tank = EnemyTank(
                    0,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.BASIC,
                    map_width_px=512,
                    map_height_px=512,
                )
        tank.direction = Direction.LEFT
        tank.direction_timer = tank.direction_change_interval + 1
        tank._blocked_directions.clear()

        tank.update(0.01, player_position=(400.0, 400.0))

        # On Easy, biases are zero so random.choice is used, not random.choices
        mock_choices.assert_not_called()

    def test_none_player_position_uses_base_only(self, mock_texture_manager):
        """When player_position is None, only base bias applies."""
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    0,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.ARMOR,
                    map_width_px=512,
                    map_height_px=512,
                )
        tank.direction = Direction.LEFT
        tank.direction_timer = tank.direction_change_interval + 1

        with patch(
            "src.core.enemy_tank.random.choices", return_value=[Direction.DOWN]
        ) as mock_choices:
            tank.update(0.01, player_position=None)
            candidates, weights = mock_choices.call_args[0]
            # No player bias added, only base bias
            down_idx = candidates.index(Direction.DOWN)
            assert weights[down_idx] == pytest.approx(1.0 + 0.45)  # base only

    def test_aligned_shooting_reduces_interval(self, mock_texture_manager):
        """When facing the player and aligned, shoot interval is reduced."""
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    100,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.BASIC,
                    map_width_px=512,
                    map_height_px=512,
                )
        tank.direction = Direction.DOWN
        # Player is below and at similar X (within TILE_SIZE)
        player_pos = (100.0, 300.0)
        # Set shoot_timer just above half the interval (reduced threshold)
        tank.shoot_timer = tank.shoot_interval * 0.5 + 0.01
        tank.direction_timer = 0  # don't trigger direction change

        tank.update(0.01, player_position=player_pos)

        assert tank.consume_shoot() is True

    def test_not_aligned_uses_normal_interval(self, mock_texture_manager):
        """When not aligned, normal shoot interval applies."""
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    100,
                    0,
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.BASIC,
                    map_width_px=512,
                    map_height_px=512,
                )
        tank.direction = Direction.LEFT  # facing left, player is below
        player_pos = (100.0, 300.0)
        tank.shoot_timer = tank.shoot_interval * 0.5 + 0.01
        tank.direction_timer = 0

        tank.update(0.01, player_position=player_pos)

        assert tank.consume_shoot() is False

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
        self, direction, tank_pos, target_pos, expected_aligned, mock_texture_manager
    ):
        """Test _is_aligned_with for various positions and directions."""
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            with patch("src.core.enemy_tank.DIFFICULTY", Difficulty.NORMAL):
                tank = EnemyTank(
                    tank_pos[0],
                    tank_pos[1],
                    TILE_SIZE,
                    mock_texture_manager,
                    TankType.BASIC,
                    map_width_px=512,
                    map_height_px=512,
                )
        tank.direction = direction
        assert tank._is_aligned_with(target_pos) == expected_aligned
