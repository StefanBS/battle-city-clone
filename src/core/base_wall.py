"""The Base Wall, and the Shovel that Fortifies it for a while."""

from loguru import logger

from src.core.map import Map
from src.core.tile import BrickVariant, Tile, TileType
from src.utils.animation import is_blink_visible
from src.utils.constants import (
    SHOVEL_DURATION,
    SHOVEL_FLASH_INTERVAL,
    SHOVEL_WARNING_DURATION,
)


class BaseWall:
    """Fortifies the Base Wall when a Shovel is collected, then reverts it.

    The wall is changed through the ``Map``'s own tiles. Shortly before the
    Shovel runs out the wall flashes between steel and brick, then goes back
    to brick. A tile shot away while Fortified stays empty.
    """

    def __init__(self, game_map: Map) -> None:
        self._map = game_map
        self._time_left: float = 0.0
        # The type each tile goes back to; empty when the wall isn't Fortified.
        self._revert_types: list[tuple[Tile, TileType]] = []
        self._flash_timer: float = 0.0
        self._showing_steel: bool = True

    def fortify(self) -> None:
        """Fortify the Base Wall for a Shovel's length.

        Destroyed or damaged bricks are rebuilt first. A Shovel already in
        effect starts over, turning the wall back to steel if it was flashing.
        """
        if not self._revert_types:
            tiles = self._map.get_base_surrounding_tiles(include_empty=True)
            for tile in tiles:
                if tile.type == TileType.EMPTY or (
                    tile.brick_variant != BrickVariant.FULL
                ):
                    self._map.set_tile_type(tile, TileType.BRICK)
                    tile.brick_variant = BrickVariant.FULL
                    tile.reset_rect()
            # Saved after rebuilding, so the wall reverts to full brick.
            self._revert_types = [(tile, tile.type) for tile in tiles]
            logger.info(f"Base Wall Fortified for {SHOVEL_DURATION}s")
        self._time_left = SHOVEL_DURATION
        self._flash_timer = 0.0
        self._show(steel=True)

    def update(self, dt: float) -> None:
        """Count the Shovel down, flash the wall near the end, then revert it."""
        if self._time_left <= 0:
            return
        self._time_left -= dt
        if self._time_left <= 0:
            self._show(steel=False)
            self._revert_types = []
            logger.info("Shovel ran out: Base Wall reverted")
            return
        if self._time_left <= SHOVEL_WARNING_DURATION:
            self._flash_timer += dt
            steel = is_blink_visible(self._flash_timer, SHOVEL_FLASH_INTERVAL)
            if steel != self._showing_steel:
                self._show(steel=steel)

    def _show(self, steel: bool) -> None:
        """Set every tile still standing to steel or to the type it reverts to."""
        self._showing_steel = steel
        for tile, revert_type in self._revert_types:
            if tile.type != TileType.EMPTY:
                self._map.set_tile_type(tile, TileType.STEEL if steel else revert_type)
