import pygame
import random
from loguru import logger
from .tank import Tank
from typing import Literal, Dict, TypedDict
from src.utils.constants import TANK_SPEED, BULLET_SPEED
from src.managers.texture_manager import TextureManager

TankType = Literal["basic", "fast", "power", "armor"]


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
        "basic": {
            "speed": TANK_SPEED * 0.75,
            "bullet_speed": BULLET_SPEED,
            "health": 1,
            "shoot_interval": 2.0,
            "direction_change_interval": 2.5,
        },
        "fast": {
            "speed": TANK_SPEED * 1.5,
            "bullet_speed": BULLET_SPEED,
            "health": 1,
            "shoot_interval": 1.8,
            "direction_change_interval": 1.5,
        },
        "power": {
            "speed": TANK_SPEED,
            "bullet_speed": BULLET_SPEED * 1.5,
            "health": 1,
            "shoot_interval": 1.0,
            "direction_change_interval": 2.0,
        },
        "armor": {
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
    ) -> None:
        """
        Initialize the enemy tank based on its type.

        Args:
            x: Initial x position
            y: Initial y position
            tile_size: Size of a tile in pixels
            texture_manager: Instance of TextureManager
            tank_type: The type of enemy tank ('basic', 'fast', 'power', 'armor')
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
            texture_manager,
            tile_size,
            None,
            health=props["health"],
            lives=1,
            speed=props["speed"],
            bullet_speed=props["bullet_speed"],
        )
        self.tank_type = tank_type
        self.owner_type = "enemy"
        self.direction = random.choice(["up", "down", "left", "right"])
        self.direction_timer: float = 0
        self.direction_change_interval: float = props["direction_change_interval"]
        self.shoot_timer: float = 0
        self.shoot_interval: float = props["shoot_interval"]
        self._update_sprite()
        logger.debug(
            f"EnemyTank ({tank_type}) properties: speed={self.speed:.2f}, "
            f"bullet_speed={self.bullet_speed:.2f}, health={self.health}, "
            f"dir_interval={self.direction_change_interval:.2f}, "
            f"shoot_interval={self.shoot_interval:.2f}"
        )

    def _change_direction(self) -> None:
        """Randomly change the tank's direction and update its sprite."""
        old_direction = self.direction
        new_direction = old_direction  # Start with the current direction
        directions = ["up", "down", "left", "right"]

        # Try to avoid reversing first
        opposite_direction = {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left",
        }
        if len(directions) > 1 and old_direction in opposite_direction:
            possible_directions = [
                d for d in directions if d != opposite_direction[old_direction]
            ]
            if possible_directions:
                new_direction = random.choice(possible_directions)
            # else: If only reversing is possible, let the fallback handle it

        # If direction didn't change above, or if reversing was the only option,
        # pick a different direction randomly (fallback).
        if new_direction == old_direction:
            possible_directions = [d for d in directions if d != old_direction]
            if possible_directions:
                new_direction = random.choice(possible_directions)
            # else: If tank is somehow stuck in a 1-way path, direction won't change.

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

        self._move(dx, dy)

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw the tank and its bullet on the given surface.

        Args:
            surface: Surface to draw on
        """
        if self.sprite:
            surface.blit(self.sprite, self.rect)
        else:
            # Fallback: Draw a simple gray rectangle if sprite is missing
            pygame.draw.rect(surface, (128, 128, 128), self.rect)
            logger.warning("Enemy tank sprite is missing, drawing fallback rect.")

        if self.bullet is not None and self.bullet.active:
            self.bullet.draw(surface)
