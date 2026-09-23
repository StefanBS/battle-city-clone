import pytest
from src.core.enemy_tank import get_enemy_config, _reset_enemy_config
from src.utils.constants import (
    TILE_SIZE,
    OwnerType,
    TankType,
    Direction,
    CARRIER_BLINK_INTERVAL,
)

# Define expected properties with resolved values matching enemy_types.json
EXPECTED_PROPERTIES = {
    TankType.BASIC: {
        "speed": 80,
        "bullet_speed": 180,
        "health": 1,
    },
    TankType.FAST: {
        "speed": 120,
        "bullet_speed": 180,
        "health": 1,
    },
    TankType.POWER: {
        "speed": 92,
        "bullet_speed": 360,
        "health": 1,
    },
    TankType.ARMOR: {
        "speed": 60,
        "bullet_speed": 360,
        "health": 4,
    },
}

TEST_CASES = [(tank_type, props) for tank_type, props in EXPECTED_PROPERTIES.items()]


def test_each_enemy_gets_a_unique_enemy_id(create_enemy_tank):
    """IDs are never reused, even after an earlier Enemy is discarded."""
    first = create_enemy_tank()
    first_id = first.enemy_id
    del first
    ids = {create_enemy_tank().enemy_id for _ in range(5)}
    assert len(ids) == 5
    assert first_id not in ids


@pytest.mark.parametrize("tank_type, expected", TEST_CASES)
def test_enemy_tank_initialization_properties(
    create_enemy_tank, tank_type: TankType, expected: dict
):
    """Test that EnemyTank initializes with correct properties for each type."""
    tank = create_enemy_tank(tank_type=tank_type)

    assert tank.tank_type == tank_type
    assert tank.speed == pytest.approx(expected["speed"])
    assert tank.bullet_speed == pytest.approx(expected["bullet_speed"])
    assert tank.health == expected["health"]
    assert tank.max_health == expected["health"]

    assert tank.owner_type == OwnerType.ENEMY
    assert tank.lives == 1
    assert tank.x == 0
    assert tank.y == 0


class TestEnemyConfigLoading:
    """Tests for enemy config JSON loading and caching."""

    def test_config_loads_all_types(self):
        config = get_enemy_config()
        assert "basic" in config
        assert "fast" in config
        assert "power" in config
        assert "armor" in config

    def test_reset_clears_cache(self):
        get_enemy_config()  # ensure loaded
        _reset_enemy_config()
        # After reset, next call reloads from file
        config = get_enemy_config()
        assert config is not None
        assert "basic" in config

    def test_config_contains_difficulty_section(self):
        config = get_enemy_config()
        assert "difficulty" in config
        assert "easy" in config["difficulty"]
        assert "normal" in config["difficulty"]

    def test_difficulty_config_has_required_keys(self):
        config = get_enemy_config()
        for level in ("easy", "normal"):
            diff = config["difficulty"][level]
            assert "base_bias" in diff
            assert "player_bias" in diff
            assert "aligned_shoot_multiplier" in diff

    def test_type_configs_have_bias_multipliers(self):
        config = get_enemy_config()
        for tank_type in ("basic", "fast", "power", "armor"):
            assert "base_bias_multiplier" in config[tank_type]
            assert "player_bias_multiplier" in config[tank_type]


def test_enemy_tank_grid_alignment(create_enemy_tank):
    """Test that initial position is aligned to the grid."""
    initial_x, initial_y = 15, 40
    # round(15/32)*32=0, round(40/32)*32=32
    expected_x, expected_y = (0, TILE_SIZE)

    tank = create_enemy_tank(x=initial_x, y=initial_y)

    assert tank.x == expected_x
    assert tank.y == expected_y
    assert tank.rect.x == expected_x
    assert tank.rect.y == expected_y


class TestEnemyTankCarrier:
    """Tests for the power-up carrier mechanic."""

    @pytest.fixture
    def carrier_tank(self, create_enemy_tank):
        tank = create_enemy_tank(
            x=100,
            y=100,
            map_width_px=512,
            map_height_px=512,
            is_carrier=True,
        )
        tank.direction = Direction.DOWN
        return tank

    @pytest.fixture
    def normal_tank(self, create_enemy_tank):
        tank = create_enemy_tank(
            x=100,
            y=100,
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

    def test_stop_carrying_shows_the_normal_sprite(
        self, carrier_tank, mock_texture_manager
    ):
        carrier_tank.update(CARRIER_BLINK_INTERVAL + 0.01)  # red phase
        mock_texture_manager.reset_mock()
        carrier_tank.stop_carrying()
        carrier_tank.update(CARRIER_BLINK_INTERVAL * 2)
        called_names = [
            c.args[0] for c in mock_texture_manager.get_sprite.call_args_list
        ]
        assert not carrier_tank.is_carrier
        assert called_names
        assert not any("red" in name for name in called_names)

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
    def enemy(self, create_enemy_tank):
        return create_enemy_tank(x=128, y=128)

    def test_on_movement_blocked_cancels_slide(self, enemy):
        enemy._on_ice = True
        enemy._was_moving = True
        enemy.direction = Direction.RIGHT
        enemy.start_slide()
        enemy.on_movement_blocked()
        assert enemy._sliding is False
