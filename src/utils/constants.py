"""
Game constants and configuration values.
"""

from enum import Enum
from typing import Tuple


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

    def __str__(self) -> str:
        return self.value


# Window settings
WINDOW_WIDTH: int = 1024  # Logical width (16*32) * 2
WINDOW_HEIGHT: int = 1024  # Logical height (16*32) * 2
WINDOW_TITLE: str = "Battle City Clone"
FPS: int = 60

# Grid settings
SOURCE_TILE_SIZE: int = 8  # Original size for loading sprites
TILE_SIZE: int = 32  # Game logic uses 32x32 tiles

# Colors
BLACK: Tuple[int, int, int] = (0, 0, 0)
WHITE: Tuple[int, int, int] = (255, 255, 255)
RED: Tuple[int, int, int] = (255, 0, 0)
GREEN: Tuple[int, int, int] = (0, 255, 0)
BLUE: Tuple[int, int, int] = (0, 0, 255)
YELLOW: Tuple[int, int, int] = (255, 255, 0)

# Tile settings
TILE_ANIMATION_INTERVAL: float = 0.5  # Seconds between frames

# Tank settings
TANK_SPEED: float = 80  # pixels per second (was 12 px/step)
TANK_WIDTH: int = TILE_SIZE
TANK_HEIGHT: int = TILE_SIZE
TANK_ANIMATION_DISTANCE: float = 4  # pixels traveled between animation frame toggles

# Bullet settings
BULLET_SPEED: float = 180  # pixels per second (was 3, multiplied by FPS internally)
BULLET_WIDTH: int = 2
BULLET_HEIGHT: int = 2
