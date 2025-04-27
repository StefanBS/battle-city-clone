"""
Game constants and configuration values.
"""

from typing import Tuple

# Scale factor
SCALE: int = 2

# Window settings
WINDOW_WIDTH: int = 1024  # Logical width (16*32) * 2
WINDOW_HEIGHT: int = 1024  # Logical height (16*32) * 2
WINDOW_TITLE: str = "Battle City Clone"
FPS: int = 60

# Grid settings
SOURCE_TILE_SIZE: int = 16  # Original size for loading sprites
TILE_SIZE: int = SOURCE_TILE_SIZE * SCALE  # Game logic uses 32x32 tiles
GRID_WIDTH: int = 16  # Number of tiles horizontally
GRID_HEIGHT: int = 16  # Number of tiles vertically

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
TANK_SPEED: float = 12
TANK_WIDTH: int = TILE_SIZE
TANK_HEIGHT: int = TILE_SIZE
PLAYER_HEALTH: int = 3
ENEMY_HEALTH: int = 1

# Bullet settings
# Base bullet speed needs to be scaled, adjust multiplier if needed
BULLET_SPEED: float = 3 * SCALE  # Speed in pixels per second
BULLET_WIDTH: int = 4 * SCALE
BULLET_HEIGHT: int = 4 * SCALE

# Power-up types
POWER_UP_INVINCIBLE: str = "invincible"
POWER_UP_FREEZE: str = "freeze"
POWER_UP_WEAPON: str = "weapon"
POWER_UP_FORTIFY: str = "fortify"
POWER_UP_LIFE: str = "life"
POWER_UP_DESTROY_ALL: str = "destroy_all"
