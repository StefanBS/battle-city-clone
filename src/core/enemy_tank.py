import pygame
import random
from loguru import logger
from .tank import Tank
from typing import Optional, Literal, Dict, Tuple, TypedDict
from src.utils.constants import TANK_SPEED, BULLET_SPEED

TankType = Literal["basic", "fast", "power", "armor"]
ColorTuple = Tuple[int, int, int]


# Define the structure for the properties dictionary
class TankPropertyDict(TypedDict):
    speed: float
    bullet_speed: float
    health: int
    color: ColorTuple
    shoot_interval: float
    direction_change_interval: float


class EnemyTank(Tank):
    """Enemy tank entity with basic AI and type variations."""

    TANK_PROPERTIES: Dict[TankType, TankPropertyDict] = {
        "basic": {
            "speed": TANK_SPEED * 0.75,
            "bullet_speed": BULLET_SPEED,
            "health": 1,
            "color": (128, 128, 128),  # Gray
            "shoot_interval": 2.0,
            "direction_change_interval": 2.5,
        },
        "fast": {
            "speed": TANK_SPEED * 1.5,
            "bullet_speed": BULLET_SPEED,
            "health": 1,
            "color": (100, 100, 255),  # Light Blue
            "shoot_interval": 1.8,
            "direction_change_interval": 1.5,
        },
        "power": {
            "speed": TANK_SPEED,
            "bullet_speed": BULLET_SPEED * 1.5,
            "health": 1,
            "color": (255, 165, 0),  # Orange
            "shoot_interval": 1.0,
            "direction_change_interval": 2.0,
        },
        "armor": {
            "speed": TANK_SPEED,
            "bullet_speed": BULLET_SPEED,
            "health": 4,
            "color": (0, 128, 0),  # Green
            "shoot_interval": 1.5,
            "direction_change_interval": 2.0,
        },
    }

    def __init__(
        self,
        x: int,
        y: int,
        tile_size: int,
        tank_type: TankType,
        sprite: Optional[pygame.Surface] = None,
    ) -> None:
        """
        Initialize the enemy tank based on its type.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            tank_type: The type of enemy tank ('basic', 'fast', 'power', 'armor')
            sprite: Optional sprite surface
        """
        props = self.TANK_PROPERTIES[tank_type]

        # Ensure x and y are aligned to the grid
        grid_x = round(x / tile_size) * tile_size
        grid_y = round(y / tile_size) * tile_size

        logger.debug(
            f"Creating EnemyTank (type: {tank_type}) at grid ({grid_x}, {grid_y})"
        )

        # Initialize with grid-aligned position and type-specific properties
        super().__init__(
            grid_x,
            grid_y,
            tile_size,
            sprite,
            health=props["health"],
            lives=1,
            speed=props["speed"],
            bullet_speed=props["bullet_speed"],
        )
        self.tank_type = tank_type
        self.owner_type = "enemy"
        self.color: ColorTuple = props["color"]
        self.direction = random.choice(["up", "down", "left", "right"])
        self.direction_timer: float = 0
        self.direction_change_interval: float = props["direction_change_interval"]
        self.shoot_timer: float = 0
        self.shoot_interval: float = props["shoot_interval"]
        logger.debug(
            f"EnemyTank ({tank_type}) properties: speed={self.speed:.2f}, "
            f"bullet_speed={self.bullet_speed:.2f}, health={self.health}, "
            f"dir_interval={self.direction_change_interval:.2f}, "
            f"shoot_interval={self.shoot_interval:.2f}"
        )

    def _change_direction(self) -> None:
        """Randomly change the tank's direction."""
        directions = ["up", "down", "left", "right"]
        # Prevent instantly reversing direction unless stuck (basic logic)
        opposite_direction = {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left",
        }
        if len(directions) > 1 and self.direction in opposite_direction:
            possible_directions = [
                d for d in directions if d != opposite_direction[self.direction]
            ]
            if possible_directions:
                self.direction = random.choice(possible_directions)
                return

        # Fallback or if not reversing
        if self.direction in directions:
            directions.remove(self.direction)
        if directions:  # Ensure directions list is not empty
            old_direction = self.direction
            self.direction = random.choice(directions)
            logger.trace(
                (
                    f"EnemyTank ({self.tank_type}) changing direction "
                    f"from {old_direction} to {self.direction}"
                )
            )

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
            self.shoot()
            self.shoot_timer = random.uniform(0, 0.3)  # Add small random offset

        # Calculate movement based on current direction
        dx, dy = 0, 0
        if self.direction == "left":
            dx = -1
        elif self.direction == "right":
            dx = 1
        elif self.direction == "up":
            dy = -1
        elif self.direction == "down":
            dy = 1

        # Attempt to move
        moved = self._move(dx, dy)

        # If movement was attempted but failed (e.g., diagonal input, timer not ready)
        # or if the move was later reverted, change direction immediately.
        # Note: Revert happens *after* this update in GameManager, so we check prev pos
        if (not moved and self.move_timer >= self.move_delay) or (
            self.x == self.prev_x and self.y == self.prev_y and (dx != 0 or dy != 0)
        ):
            logger.debug(
                (
                    f"EnemyTank ({self.tank_type}) movement blocked or reverted, "
                    f"changing direction."
                )
            )
            self._change_direction()
            self.direction_timer = random.uniform(0, 0.5)  # Reset timer too

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the tank and its bullet on the given surface.

        Args:
            surface: Surface to draw on
        """
        # Use self.color defined in __init__ based on type
        if self.sprite:
            # TODO: Implement sprite rotation based on direction if needed
            surface.blit(self.sprite, self.rect)
        else:
            pygame.draw.rect(surface, self.color, self.rect)

        if self.bullet is not None and self.bullet.active:
            self.bullet.draw(surface)
