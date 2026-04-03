from src.utils.constants import (
    PowerUpType,
    POWERUP_CARRIER_INDICES,
    POWERUP_BLINK_INTERVAL,
    POWERUP_TIMEOUT,
    POWERUP_COLLECT_POINTS,
    CARRIER_BLINK_INTERVAL,
)


class TestPowerUpConstants:
    def test_power_up_type_values(self):
        assert PowerUpType.HELMET.value == "helmet"
        assert PowerUpType.STAR.value == "star"
        assert PowerUpType.BOMB.value == "bomb"
        assert PowerUpType.CLOCK.value == "clock"
        assert PowerUpType.SHOVEL.value == "shovel"
        assert PowerUpType.EXTRA_LIFE.value == "extra_life"

    def test_power_up_type_is_str_enum(self):
        assert isinstance(PowerUpType.HELMET, str)

    def test_carrier_indices(self):
        assert POWERUP_CARRIER_INDICES == (3, 10, 17)

    def test_timing_constants(self):
        assert POWERUP_BLINK_INTERVAL > 0
        assert POWERUP_TIMEOUT > 0
        assert POWERUP_COLLECT_POINTS > 0
        assert CARRIER_BLINK_INTERVAL > 0
