import random
from loguru import logger
from .tank import Tank
from typing import Dict, TypedDict
from src.utils.constants import Direction, OwnerType, TankType, TANK_SPEED, BULLET_SPEED
from src.managers.texture_manager import TextureManager


# Define the structure for the properties dictionary
class TankPropertyDict(TypedDict):
    speed: float
    bullet_speed: float
    health: int
    shoot_interval: float
    direction_change_interval: float


class EnemyTank(Tank):
    """Enemy tank entity with basic AI and type variations."""

    TANK_PROPERTIES: Dict[TankType, TankPropertyDict] = {
        TankType.BASIC: {
            "speed": TANK_SPEED * 0.75,
            "bullet_speed": BULLET_SPEED,
            "health": 1,
            "shoot_interval": 2.0,
            "direction_change_interval": 2.5,
        },
        TankType.FAST: {
            "speed": TANK_SPEED * 1.5,
            "bullet_speed": BULLET_SPEED,
            "health": 1,
            "shoot_interval": 1.8,
            "direction_change_interval": 1.5,
        },
        TankType.POWER: {
            "speed": TANK_SPEED,
            "bullet_speed": BULLET_SPEED * 1.5,
            "health": 1,
            "shoot_interval": 1.0,
            "direction_change_interval": 2.0,
        },
        TankType.ARMOR: {
            "speed": TANK_SPEED,
            "bullet_speed": BULLET_SPEED,
            "health": 4,
            "shoot_interval": 1.5,
            "direction_change_interval": 2.0,
        },
    }

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
        props = self.TANK_PROPERTIES[tank_type]

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
        self.direction = random.choice(list(Direction))
        self.direction_timer: float = 0
        self.direction_change_interval: float = props["direction_change_interval"]
        self.shoot_timer: float = 0
        self.shoot_interval: float = props["shoot_interval"]
        self._wants_to_shoot: bool = False
        self._update_sprite()
        logger.debug(
            f"EnemyTank ({tank_type}) properties: speed={self.speed:.2f}, "
            f"bullet_speed={self.bullet_speed:.2f}, health={self.health}, "
            f"dir_interval={self.direction_change_interval:.2f}, "
            f"shoot_interval={self.shoot_interval:.2f}"
        )

    _ALL_DIRECTIONS = list(Direction)

    def _change_direction(self) -> None:
        """Randomly change the tank's direction and update its sprite."""
        old_direction = self.direction
        new_direction = old_direction

        # Try to avoid reversing first
        possible_directions = [
            d for d in self._ALL_DIRECTIONS if d != old_direction.opposite
        ]
        if possible_directions:
            new_direction = random.choice(possible_directions)

        # If direction didn't change, pick any different direction (fallback)
        if new_direction == old_direction:
            possible_directions = [
                d for d in self._ALL_DIRECTIONS if d != old_direction
            ]
            if possible_directions:
                new_direction = random.choice(possible_directions)

        # Only update sprite if the direction actually changed
        if new_direction != old_direction:
            self.direction = new_direction
            logger.trace(
                (
                    f"EnemyTank ({self.tank_type}) changing direction "
                    f"from {old_direction} to {self.direction}"
                )
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

    def on_wall_hit(self) -> None:
        """Handle collision with a wall by changing direction."""
        self._change_direction()
        self.direction_timer = 0

    def update(self, dt: float) -> None:
        """
        Update the tank's position and behavior.

        Args:
            dt: Time elapsed since last update in seconds
        """
        # Update base tank state (this now stores prev_x/y)
        super().update(dt)

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

        dx, dy = self.direction.delta
        self._move(dx, dy, dt)
