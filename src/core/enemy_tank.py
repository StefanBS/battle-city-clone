import itertools
import json
import random
from collections.abc import Callable
from loguru import logger
from .tank import Tank
from typing import TypedDict
from src.utils.animation import is_blink_visible
from src.utils.constants import (
    CARRIER_BLINK_INTERVAL,
    Direction,
    OwnerType,
    TankType,
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
# Unlike id(), never reused for the lifetime of the process.
_next_enemy_id = itertools.count()
_enemy_config: dict | None = None


def get_enemy_config() -> dict:
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
    """Enemy tank entity with type variations. Driven by an EnemyAI."""

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
        config = get_enemy_config()
        props = config[tank_type]

        super().__init__(
            x,
            y,
            texture_manager,
            tile_size,
            health=props["health"],
            lives=1,
            speed=props["speed"],
            bullet_speed=props["bullet_speed"],
            owner_type=OwnerType.ENEMY,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )
        self.enemy_id: int = next(_next_enemy_id)
        self.tank_type = tank_type
        self._sprite_prefix: str = props.get("sprite_prefix", "enemy_tank")
        self.power_bullets = props["power_bullets"]
        self.direction = random.choice(list(Direction))
        self.is_carrier: bool = is_carrier
        self.carrier_blink_timer: float = 0.0
        # Set by the paired EnemyAI, so a blocked move reaches the AI.
        self.movement_blocked_listener: Callable[[], None] | None = None

        self._update_sprite()
        logger.debug(
            f"EnemyTank ({tank_type}) properties: speed={self.speed:.2f}, "
            f"bullet_speed={self.bullet_speed:.2f}, health={self.health}"
        )

    def stop_carrying(self) -> None:
        """Stop being a Carrier: no more flashing, no Power-Up to drop."""
        self.is_carrier = False
        self._update_sprite()

    def _update_sprite(self) -> None:
        """Update sprite using type-specific prefix and carrier red variant."""
        if self.is_carrier and not is_blink_visible(
            self.carrier_blink_timer, CARRIER_BLINK_INTERVAL
        ):
            sprite_name = (
                f"{self._sprite_prefix}_red_{self.direction}_{self.animation_frame}"
            )
            try:
                self.sprite = self.texture_manager.get_sprite(sprite_name)
                return
            except KeyError:
                pass
        sprite_name = f"{self._sprite_prefix}_{self.direction}_{self.animation_frame}"
        try:
            self.sprite = self.texture_manager.get_sprite(sprite_name)
        except KeyError:
            logger.error(f"Sprite '{sprite_name}' not found for enemy tank.")

    def on_movement_blocked(self) -> None:
        """Cancel any Slide, then tell the paired EnemyAI."""
        super().on_movement_blocked()
        if self.movement_blocked_listener is not None:
            self.movement_blocked_listener()

    def update(self, dt: float) -> None:
        """
        Advance tank timers and the Carrier blink.

        Args:
            dt: Time elapsed since last update in seconds
        """
        super().update(dt)

        if self.is_carrier:
            self.carrier_blink_timer += dt
            self._update_sprite()
