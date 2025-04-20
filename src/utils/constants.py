"""
Game constants and configuration values.
"""

from typing import Tuple

# Window settings
WINDOW_WIDTH: int = 800
WINDOW_HEIGHT: int = 600
WINDOW_TITLE: str = "Battle City Clone"
FPS: int = 60

# Grid settings
TILE_SIZE: int = 32
GRID_WIDTH: int = 26  # Number of tiles horizontally
GRID_HEIGHT: int = 26  # Number of tiles vertically

# Colors
BLACK: Tuple[int, int, int] = (0, 0, 0)
WHITE: Tuple[int, int, int] = (255, 255, 255)
RED: Tuple[int, int, int] = (255, 0, 0)
GREEN: Tuple[int, int, int] = (0, 255, 0)
BLUE: Tuple[int, int, int] = (0, 0, 255)
YELLOW: Tuple[int, int, int] = (255, 255, 0)

# Tank settings
TANK_SPEED: int = 2
TANK_WIDTH: int = TILE_SIZE
TANK_HEIGHT: int = TILE_SIZE
PLAYER_HEALTH: int = 3  # Player starts with 3 health points
ENEMY_HEALTH: int = 1  # Basic enemy tanks have 1 health point

# Bullet settings
BULLET_SPEED: int = 4
BULLET_WIDTH: int = 8
BULLET_HEIGHT: int = 8

# Tile types
EMPTY: int = 0
BRICK: int = 1
STEEL: int = 2
WATER: int = 3
TREES: int = 4
ICE: int = 5
BASE: int = 6

# Game states
STATE_MENU: str = "menu"
STATE_PLAYING: str = "playing"
STATE_PAUSED: str = "paused"
STATE_GAME_OVER: str = "game_over"
STATE_LEVEL_COMPLETE: str = "level_complete"

# Power-up types
POWER_UP_INVINCIBLE: str = "invincible"
POWER_UP_FREEZE: str = "freeze"
POWER_UP_WEAPON: str = "weapon"
POWER_UP_FORTIFY: str = "fortify"
POWER_UP_LIFE: str = "life"
POWER_UP_DESTROY_ALL: str = "destroy_all"
