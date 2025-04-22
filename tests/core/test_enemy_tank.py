import pytest
from src.core.enemy_tank import EnemyTank, TankType
from src.utils.constants import TILE_SIZE, TANK_SPEED, BULLET_SPEED

# Define expected properties based on EnemyTank.TANK_PROPERTIES for easier assertion
EXPECTED_PROPERTIES = {
    "basic": {
        "speed": TANK_SPEED * 0.75,
        "bullet_speed": BULLET_SPEED,
        "health": 1,
        "color": (128, 128, 128),
        "shoot_interval": 2.0,
        "direction_change_interval": 2.5,
    },
    "fast": {
        "speed": TANK_SPEED * 1.5,
        "bullet_speed": BULLET_SPEED,
        "health": 1,
        "color": (100, 100, 255),
        "shoot_interval": 1.8,
        "direction_change_interval": 1.5,
    },
    "power": {
        "speed": TANK_SPEED,
        "bullet_speed": BULLET_SPEED * 1.5,
        "health": 1,
        "color": (255, 165, 0),
        "shoot_interval": 1.0,
        "direction_change_interval": 2.0,
    },
    "armor": {
        "speed": TANK_SPEED,
        "bullet_speed": BULLET_SPEED,
        "health": 4,
        "color": (0, 128, 0),
        "shoot_interval": 1.5,
        "direction_change_interval": 2.0,
    },
}

# Test cases covering all tank types
TEST_CASES = [
    (tank_type, props) for tank_type, props in EXPECTED_PROPERTIES.items()
]


@pytest.mark.parametrize("tank_type, expected", TEST_CASES)
def test_enemy_tank_initialization_properties(tank_type: TankType, expected: dict):
    """Test that EnemyTank initializes with correct properties for each type."""
    # Minimal required positional args for EnemyTank
    x, y = 0, 0
    tile_size = TILE_SIZE

    tank = EnemyTank(x, y, tile_size, tank_type)

    # Assert core properties set by the type
    assert tank.tank_type == tank_type
    assert tank.speed == pytest.approx(expected["speed"])
    assert tank.bullet_speed == pytest.approx(expected["bullet_speed"])
    assert tank.health == expected["health"]
    assert tank.max_health == expected["health"] # Should also be set
    assert tank.color == expected["color"]
    assert tank.shoot_interval == pytest.approx(expected["shoot_interval"])
    assert tank.direction_change_interval == pytest.approx(expected["direction_change_interval"])

    # Assert other relevant properties
    assert tank.owner_type == "enemy"
    assert tank.lives == 1 # Enemies should have 1 life
    assert tank.x == x # Check grid alignment effect is handled if needed (0 should be fine)
    assert tank.y == y

def test_enemy_tank_grid_alignment():
    """Test that initial position is aligned to the grid."""
    tile_size = 32
    # Non-aligned positions
    initial_x, initial_y = 15, 40
    expected_x, expected_y = 0 * tile_size, 1 * tile_size # round(15/32)*32=0, round(40/32)*32=32

    tank = EnemyTank(initial_x, initial_y, tile_size, tank_type='basic')

    assert tank.x == expected_x
    assert tank.y == expected_y
    assert tank.rect.x == expected_x
    assert tank.rect.y == expected_y

# Potential further tests:
# - Test _change_direction logic (e.g., doesn't immediately reverse)
# - Test update method behavior (timers increment, shooting/direction changes occur)
#   (These would likely require mocking time/dt and random) 