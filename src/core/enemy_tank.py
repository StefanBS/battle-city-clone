import json
import random
from loguru import logger
from .tank import Tank
from typing import TypedDict
from src.utils.constants import (
    Direction,
    OwnerType,
    TankType,
    CARRIER_BLINK_INTERVAL,
)
from src.managers.texture_manager import TextureManager


# Define the structure for the properties dictionary
class TankPropertyDict(TypedDict):
    speed: float
    bullet_speed: float
    health: int
    shoot_interval: float
    direction_change_interval: float
    power_bullets: bool
    sprite_prefix: str
    base_bias_multiplier: float
    player_bias_multiplier: float


_ENEMY_CONFIG_PATH = "assets/config/enemy_types.json"
_enemy_config: dict | None = None


def _get_enemy_config() -> dict:
    """Load and cache enemy type configuration from JSON."""
    global _enemy_config
    if _enemy_config is None:
        from src.utils.paths import resource_path

        with open(resource_path(_ENEMY_CONFIG_PATH)) as f:
            _enemy_config = json.load(f)
    return _enemy_config


def _reset_enemy_config() -> None:
    """Reset cached config (for testing)."""
    global _enemy_config
    _enemy_config = None


class EnemyTank(Tank):
    """Enemy tank entity with basic AI and type variations."""

    def __init__(
        self,
        x: int,
        y: int,
        tile_size: int,
        texture_manager: TextureManager,
        tank_type: TankType,
        *,
        map_width_px: int,
        map_height_px: int,
        is_carrier: bool = False,
    ) -> None:
        """
        Initialize the enemy tank based on its type.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            texture_manager: Instance of TextureManager
            tank_type: The type of enemy tank ('basic', 'fast', 'power', 'armor')
            map_width_px: Map width in pixels (for boundary clamping)
            map_height_px: Map height in pixels (for boundary clamping)
        """
        config = _get_enemy_config()
        props = config[tank_type.value]

        super().__init__(
            x,
            y,
            texture_manager,
            tile_size,
            None,
            health=props["health"],
            lives=1,
            speed=props["speed"],
            bullet_speed=props["bullet_speed"],
            owner_type=OwnerType.ENEMY,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )
        self.tank_type = tank_type
        self._sprite_prefix: str = props.get("sprite_prefix", "enemy_tank")
        self.power_bullets = props["power_bullets"]
        self.direction = random.choice(list(Direction))
        self.direction_timer: float = 0
        self.direction_change_interval: float = props["direction_change_interval"]
        self.shoot_timer: float = 0
        self.shoot_interval: float = props["shoot_interval"]
        self._wants_to_shoot: bool = False
        self._blocked_directions: set[Direction] = set()
        self.is_carrier: bool = is_carrier
        self.carrier_blink_timer: float = 0.0
        self._update_sprite()
        logger.debug(
            f"EnemyTank ({tank_type}) properties: speed={self.speed:.2f}, "
            f"bullet_speed={self.bullet_speed:.2f}, health={self.health}, "
            f"dir_interval={self.direction_change_interval:.2f}, "
            f"shoot_interval={self.shoot_interval:.2f}"
        )

    _ALL_DIRECTIONS = list(Direction)

    def _update_sprite(self) -> None:
        """Update sprite using type-specific prefix and carrier red variant."""
        if (
            self.is_carrier
            and self.carrier_blink_timer % (CARRIER_BLINK_INTERVAL * 2)
            >= CARRIER_BLINK_INTERVAL
        ):
            sprite_name = (
                f"{self._sprite_prefix}_red"
                f"_{self.direction}_{self.animation_frame}"
            )
            try:
                self.sprite = self.texture_manager.get_sprite(sprite_name)
                return
            except KeyError:
                pass
        sprite_name = (
            f"{self._sprite_prefix}_{self.direction}_{self.animation_frame}"
        )
        try:
            self.sprite = self.texture_manager.get_sprite(sprite_name)
        except KeyError:
            logger.error(f"Sprite '{sprite_name}' not found for enemy tank.")

    def _change_direction(self, allow_slide: bool = True) -> None:
        """Randomly change the tank's direction, avoiding blocked ones."""
        old_direction = self.direction

        # Prefer unblocked directions, excluding opposite to avoid reversing
        opposite = old_direction.opposite
        candidates = [
            d
            for d in self._ALL_DIRECTIONS
            if d not in self._blocked_directions and d != opposite
        ]
        # Fall back to unblocked only (allow opposite)
        if not candidates:
            candidates = [
                d for d in self._ALL_DIRECTIONS if d not in self._blocked_directions
            ]
        # All directions blocked — stay put and wait for one to open
        if not candidates:
            return

        new_direction = random.choice(candidates)

        # Trigger ice slide in old direction before changing
        if allow_slide and new_direction != old_direction and self._on_ice:
            self.start_slide()

        if new_direction != old_direction:
            self.direction = new_direction
            logger.trace(
                f"EnemyTank ({self.tank_type}) changing direction "
                f"from {old_direction} to {self.direction}"
            )
            self._update_sprite()
        else:
            logger.trace(
                f"EnemyTank ({self.tank_type}) direction remained {old_direction}."
            )

    def consume_shoot(self) -> bool:
        """Check if the tank wants to shoot and clear the flag."""
        if self._wants_to_shoot:
            self._wants_to_shoot = False
            return True
        return False

    def on_movement_blocked(self) -> None:
        """Handle collision with a wall by changing direction."""
        super().on_movement_blocked()
        self._blocked_directions.add(self.direction)
        self._change_direction(allow_slide=False)
        self.direction_timer = 0

    def update(self, dt: float) -> None:
        """
        Update the tank's position and behavior.

        Args:
            dt: Time elapsed since last update in seconds
        """
        # Clear blocked directions once the tank successfully moved,
        # meaning the path is no longer obstructed. Check before
        # super().update() overwrites prev_x/prev_y.
        if self.x != self.prev_x or self.y != self.prev_y:
            self._blocked_directions.clear()

        # Update base tank state (this now stores prev_x/y)
        super().update(dt)

        if self.is_carrier:
            self.carrier_blink_timer += dt
            self._update_sprite()

        # Update timers
        self.direction_timer += dt
        self.shoot_timer += dt

        # Change direction periodically
        if self.direction_timer >= self.direction_change_interval:
            logger.trace(f"EnemyTank ({self.tank_type}) direction timer triggered.")
            self._change_direction()
            self.direction_timer = random.uniform(0, 0.5)  # Add small random offset

        # Shoot periodically
        if self.shoot_timer >= self.shoot_interval:
            logger.trace(f"EnemyTank ({self.tank_type}) shoot timer triggered.")
            self._wants_to_shoot = True
            self.shoot_timer = random.uniform(0, 0.3)  # Add small random offset

        if not self._sliding:
            dx, dy = self.direction.delta
            self._move(dx, dy, dt)
