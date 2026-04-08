import pytest
from unittest.mock import patch
from src.core.enemy_tank import EnemyTank, _get_enemy_config, _reset_enemy_config
from src.utils.constants import (
    TILE_SIZE,
    FPS,
    TankType,
    Direction,
    CARRIER_BLINK_INTERVAL,
)

# Define expected properties with resolved values matching enemy_types.json
EXPECTED_PROPERTIES = {
    "basic": {
        "speed": 80,
        "bullet_speed": 180,
        "health": 1,
        "shoot_interval": 2.0,
        "direction_change_interval": 2.5,
    },
    "fast": {
        "speed": 120,
        "bullet_speed": 180,
        "health": 1,
        "shoot_interval": 1.8,
        "direction_change_interval": 1.5,
    },
    "power": {
        "speed": 92,
        "bullet_speed": 360,
        "health": 1,
        "shoot_interval": 1.0,
        "direction_change_interval": 2.0,
    },
    "armor": {
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
        tank_type="basic",
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )

    assert tank.x == expected_x
    assert tank.y == expected_y
    assert tank.rect.x == expected_x
    assert tank.rect.y == expected_y


@patch("src.core.enemy_tank.random.choice")
def test_on_movement_blocked(mock_random_choice, mock_texture_manager):
    """Test that on_movement_blocked changes direction and resets direction_timer."""
    mock_random_choice.return_value = Direction.DOWN
    tank = EnemyTank(
        0,
        0,
        TILE_SIZE,
        mock_texture_manager,
        tank_type="basic",
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


@patch("src.core.enemy_tank.random.choice")
def test_blocked_avoids_blocked_dirs(mock_random_choice, mock_texture_manager):
    """Test that consecutive wall hits accumulate blocked directions."""
    mock_random_choice.return_value = Direction.DOWN
    tank = EnemyTank(
        0,
        0,
        TILE_SIZE,
        mock_texture_manager,
        tank_type="basic",
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
        tank_type="basic",
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
        tank_type="basic",
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
        tank_type="basic",
        map_width_px=16 * TILE_SIZE,
        map_height_px=16 * TILE_SIZE,
    )
    assert not tank.consume_shoot()

    tank.shoot_timer = tank.shoot_interval + 0.1
    tank.update(0.01)

    assert tank.consume_shoot() is True
    assert tank.consume_shoot() is False


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
        tank_type="basic",
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
                100, 100, TILE_SIZE, mock_texture_manager,
                tank_type=TankType.BASIC,
                map_width_px=512, map_height_px=512,
                is_carrier=True,
            )
        tank.direction = Direction.DOWN
        return tank

    @pytest.fixture
    def normal_tank(self, mock_texture_manager):
        with patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN):
            tank = EnemyTank(
                100, 100, TILE_SIZE, mock_texture_manager,
                tank_type=TankType.BASIC,
                map_width_px=512, map_height_px=512,
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


class TestEnemyIceSlide:
    """Tests for enemy tank sliding on ice."""

    @pytest.fixture
    def enemy(self, mock_texture_manager):
        return EnemyTank(
            128, 128, TILE_SIZE, mock_texture_manager, "basic",
            map_width_px=16 * TILE_SIZE, map_height_px=16 * TILE_SIZE,
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
