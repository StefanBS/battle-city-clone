"""
Game constants and configuration values.
"""

from enum import Enum, auto
from typing import Tuple


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

    def __str__(self) -> str:
        return self.value

    @property
    def opposite(self) -> "Direction":
        """Return the opposite direction."""
        return _OPPOSITE_DIRECTIONS[self]

    @property
    def delta(self) -> Tuple[int, int]:
        """Return the (dx, dy) unit vector for this direction."""
        return _DIRECTION_DELTAS[self]


# Lookup tables defined after the enum class
_OPPOSITE_DIRECTIONS: dict["Direction", "Direction"] = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}

_DIRECTION_DELTAS: dict["Direction", Tuple[int, int]] = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


class OwnerType(str, Enum):
    PLAYER = "player"
    ENEMY = "enemy"

    def __str__(self) -> str:
        return self.value


class TankType(str, Enum):
    BASIC = "basic"
    FAST = "fast"
    POWER = "power"
    ARMOR = "armor"

    def __str__(self) -> str:
        return self.value


# Points awarded per enemy tank type
ENEMY_POINTS: dict[TankType, int] = {
    TankType.BASIC: 100,
    TankType.FAST: 200,
    TankType.POWER: 300,
    TankType.ARMOR: 400,
}


class EffectType(Enum):
    SMALL_EXPLOSION = auto()
    LARGE_EXPLOSION = auto()
    SPAWN = auto()


class PowerUpType(str, Enum):
    HELMET = "helmet"
    STAR = "star"
    BOMB = "bomb"
    CLOCK = "clock"
    SHOVEL = "shovel"
    EXTRA_LIFE = "extra_life"

    def __str__(self) -> str:
        return self.value


# Power-up spawn settings
POWERUP_CARRIER_INDICES: tuple[int, ...] = (3, 10, 17)  # 4th, 11th, 18th enemies
POWERUP_BLINK_INTERVAL: float = 0.15
POWERUP_TIMEOUT: float = 15.0
POWERUP_COLLECT_POINTS: int = 500
CARRIER_BLINK_INTERVAL: float = 0.1
HELMET_INVINCIBILITY_DURATION: float = 10.0
CLOCK_FREEZE_DURATION: float = 10.0
SHOVEL_DURATION: float = 20.0
SHOVEL_WARNING_DURATION: float = 3.0
SHOVEL_FLASH_INTERVAL: float = 0.25
STAR_BULLET_SPEED_MULTIPLIER: float = 2.0
STAR_MAX_BULLETS: int = 2
CURTAIN_CLOSE_DURATION: float = 0.75
CURTAIN_OPEN_DURATION: float = 0.75
CURTAIN_STAGE_DISPLAY: float = 1.5
VICTORY_PAUSE_DURATION: float = 1.0
GAME_OVER_RISE_DURATION: float = 2.0
GAME_OVER_HOLD_DURATION: float = 1.0


# Window settings
WINDOW_WIDTH: int = 1024  # Logical width (16*32) * 2
WINDOW_HEIGHT: int = 1024  # Logical height (16*32) * 2
WINDOW_TITLE: str = "Battle City Clone"
FPS: int = 60

# Grid settings
SOURCE_TILE_SIZE: int = 8  # Original size for loading sprites
SUB_TILE_SIZE: int = 16  # Rendered tile size for the map grid
TILE_SIZE: int = 32  # Entity size (tanks) and visual tile size

# Logical surface (fixed size, map centered inside with gray border)
LOGICAL_WIDTH: int = 512
LOGICAL_HEIGHT: int = 512

# Colors
BLACK: Tuple[int, int, int] = (0, 0, 0)
GRAY: Tuple[int, int, int] = (128, 128, 128)
WHITE: Tuple[int, int, int] = (255, 255, 255)
RED: Tuple[int, int, int] = (255, 0, 0)
GREEN: Tuple[int, int, int] = (0, 255, 0)
YELLOW: Tuple[int, int, int] = (255, 255, 0)

# Tile settings
TILE_ANIMATION_INTERVAL: float = 0.5  # Seconds between frames

# Tank settings
TANK_SPEED: float = 80  # pixels per second (was 12 px/step)
TANK_WIDTH: int = TILE_SIZE
TANK_HEIGHT: int = TILE_SIZE
TANK_ANIMATION_DISTANCE: float = 4  # pixels traveled between animation frame toggles
TANK_ALIGN_THRESHOLD: float = 4.0  # max px offset for steering assist (quarter sub-tile)

# Atlas background color used as colorkey for transparency
ATLAS_BG_COLOR: tuple[int, int, int] = (0, 0, 1)

# Bullet settings
BULLET_SPEED: float = 180  # pixels per second (was 3, multiplied by FPS internally)
BULLET_SIZE: int = 4  # Visual size of bullet sprites after extraction
BULLET_WIDTH: int = BULLET_SIZE
BULLET_HEIGHT: int = BULLET_SIZE

# Effect settings
SMALL_EXPLOSION_FRAME_DURATION: float = 0.067  # ~0.2s total for 3 frames
LARGE_EXPLOSION_FRAME_DURATION: float = 0.06  # ~0.3s total for 5 frames
SPAWN_FRAME_DURATION: float = 0.067  # ~0.8s total, 12 frames
