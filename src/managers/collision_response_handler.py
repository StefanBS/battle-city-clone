import pygame
from typing import Any, Callable, Dict, List, Tuple, Type
from loguru import logger
from src.core.bullet import Bullet
from src.core.tank import Tank
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType, IMPASSABLE_TILE_TYPES
from src.utils.constants import (
    Direction,
    OwnerType,
    SEGMENT_LEFT,
    SEGMENT_RIGHT,
    SEGMENT_TOP,
    SEGMENT_BOTTOM,
)
from src.core.map import Map
from src.states.game_state import GameState


class CollisionResponseHandler:
    """Handles collision responses using a type-pair handler registry."""

    def __init__(
        self,
        game_map: Map,
        set_game_state: Callable[[GameState], None],
    ) -> None:
        self._map = game_map
        self._set_game_state = set_game_state

        self._handlers: Dict[Tuple[Type, Type], Callable[[Any, Any, List], bool]] = {
            (Bullet, EnemyTank): self._handle_bullet_vs_enemy,
            (Bullet, PlayerTank): self._handle_bullet_vs_player,
            (Bullet, Tile): self._handle_bullet_vs_tile,
            (Bullet, Bullet): self._handle_bullet_vs_bullet,
            (PlayerTank, EnemyTank): self._handle_tank_vs_tank,
            (PlayerTank, PlayerTank): self._handle_tank_vs_tank,
            (EnemyTank, EnemyTank): self._handle_tank_vs_tank,
            (PlayerTank, Tile): self._handle_tank_vs_tile,
            (EnemyTank, Tile): self._handle_tank_vs_tile,
        }

    def process_collisions(self, events: List[Tuple[Any, Any]]) -> List[EnemyTank]:
        """Process collision events and return list of enemies to remove."""
        if not events:
            return []

        processed_bullets: set = set()
        reverted_tanks: set = set()
        enemies_to_remove: List[EnemyTank] = []

        for obj_a, obj_b in events:
            handler, a, b = self._lookup(obj_a, obj_b)
            if handler is None:
                continue

            # Bullet pair consumption: if either object is a bullet,
            # this is a bullet collision — consume the pair regardless
            is_bullet_pair = isinstance(a, Bullet) or isinstance(b, Bullet)

            if is_bullet_pair:
                # Identify the bullet(s)
                bullet = a if isinstance(a, Bullet) else b
                if bullet in processed_bullets:
                    continue
                # Also check if the other is a bullet and processed
                other = b if bullet is a else a
                if isinstance(other, Bullet) and other in processed_bullets:
                    continue

                result = handler(a, b, enemies_to_remove)
                if result:
                    processed_bullets.add(bullet)
                    if isinstance(other, Bullet):
                        processed_bullets.add(other)
                # Consumed — do not evaluate as tank collision
                continue

            # Tank collisions
            if isinstance(a, Tank) and isinstance(b, Tank):
                if a not in reverted_tanks or b not in reverted_tanks:
                    if handler(a, b, enemies_to_remove):
                        reverted_tanks.add(a)
                        reverted_tanks.add(b)
            elif isinstance(a, Tank):
                if a not in reverted_tanks:
                    if handler(a, b, enemies_to_remove):
                        reverted_tanks.add(a)
            elif isinstance(b, Tank):
                if b not in reverted_tanks:
                    if handler(a, b, enemies_to_remove):
                        reverted_tanks.add(b)

        return enemies_to_remove

    def _lookup(self, obj_a: Any, obj_b: Any) -> Tuple[Any, Any, Any]:
        """Look up handler for type pair, trying both orderings."""
        for (type_a, type_b), handler in self._handlers.items():
            if isinstance(obj_a, type_a) and isinstance(obj_b, type_b):
                return handler, obj_a, obj_b
            if isinstance(obj_b, type_a) and isinstance(obj_a, type_b):
                return handler, obj_b, obj_a

        logger.warning(
            f"No collision handler for ({type(obj_a).__name__}, {type(obj_b).__name__})"
        )
        return None, obj_a, obj_b

    def _handle_bullet_vs_enemy(
        self,
        bullet: Bullet,
        enemy: EnemyTank,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if not bullet.active:
            return False
        if bullet.owner_type != OwnerType.PLAYER:
            return False
        logger.debug(f"Player bullet hit enemy tank (type: {enemy.tank_type})")
        bullet.active = False
        destroyed = enemy.take_damage()
        if destroyed:
            logger.info(f"Enemy tank (type: {enemy.tank_type}) destroyed.")
            enemies_to_remove.append(enemy)
        return True

    def _handle_bullet_vs_player(
        self,
        bullet: Bullet,
        player: PlayerTank,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if not bullet.active:
            return False
        if bullet.owner_type != OwnerType.ENEMY:
            return False
        logger.debug("Enemy bullet hit player tank.")
        bullet.active = False
        if not player.is_invincible:
            destroyed = player.take_damage()
            if destroyed:
                logger.info("Player tank destroyed.")
                self._set_game_state(GameState.GAME_OVER)
            else:
                player.respawn()
        return True

    def _handle_bullet_vs_tile(
        self,
        bullet: Bullet,
        tile: Tile,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if not bullet.active:
            return False
        if tile.type == TileType.BRICK:
            logger.debug(f"Bullet hit brick tile at ({tile.x}, {tile.y})")
            bullet.active = False
            self._destroy_brick_segments(tile, bullet)
            return True
        elif tile.type == TileType.STEEL:
            logger.debug(f"Bullet hit steel tile at ({tile.x}, {tile.y})")
            bullet.active = False
            return True
        elif tile.type == TileType.BASE:
            logger.debug(f"Bullet hit base tile at ({tile.x}, {tile.y})")
            bullet.active = False
            self._map.destroy_base_group(tile)
            self._set_game_state(GameState.GAME_OVER)
            return True
        return False

    def _handle_bullet_vs_bullet(
        self,
        bullet_a: Bullet,
        bullet_b: Bullet,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if not bullet_a.active or not bullet_b.active:
            return False
        if bullet_a == bullet_b:
            return False
        logger.debug("Bullet hit bullet. Both deactivated.")
        bullet_a.active = False
        bullet_b.active = False
        return True

    def _destroy_brick_segments(self, tile: Tile, bullet: Bullet) -> None:
        """Destroy brick quadrants hit by a bullet (4x4 segment model).

        Each 32x32 brick = 4 sub-tiles (2x2, 16x16 each).
        Each sub-tile has 4 quadrants (2x2, 8x8 each) = 16 segments total.

        A bullet destroys the full entry-side row/column of each sub-tile
        it overlaps. For a RIGHT bullet that means both left-column quadrants
        (TL+BL); for a DOWN bullet both top-row quadrants (TL+TR), etc.

        If the entry side is already gone the bullet passes through and
        destroys the remaining side instead.
        """
        direction = bullet.direction
        bullet_rect = bullet.rect

        if direction in (Direction.LEFT, Direction.RIGHT):
            entry_mask = SEGMENT_LEFT if direction == Direction.RIGHT else SEGMENT_RIGHT
            sibling = self._map.get_tile_at(tile.x, tile.y ^ 1)
        else:
            entry_mask = SEGMENT_TOP if direction == Direction.DOWN else SEGMENT_BOTTOM
            sibling = self._map.get_tile_at(tile.x ^ 1, tile.y)

        # Always destroy the full entry side of the primary tile
        self._destroy_entry_side(tile, entry_mask)

        # Sibling only if the bullet physically reaches it
        if sibling and sibling.type == TileType.BRICK:
            if bullet_rect.colliderect(sibling.rect):
                self._destroy_entry_side(sibling, entry_mask)

    def _destroy_entry_side(self, tile: Tile, entry_mask: int) -> None:
        """Destroy the full entry-side of a sub-tile.

        If entry side has remaining quadrants, destroy them all.
        If entry side is already gone, destroy the opposite side (pass-through).
        """
        target = tile.brick_segments & entry_mask
        if not target:
            # Entry side gone — pass-through to remaining quadrants
            target = tile.brick_segments
        if target:
            self._remove_segment(tile, target)

    def _remove_segment(self, tile: Tile, segment: int) -> None:
        """Remove one segment from a brick sub-tile; set EMPTY if none remain."""
        tile.remove_brick_segment(segment)
        if tile.brick_segments == 0:
            self._map.set_tile_type(tile, TileType.EMPTY)
        else:
            self._map.mark_tile_cache_dirty()

    @staticmethod
    def _caused_collision(mover: Tank, other: Tank) -> bool:
        """Check if mover's movement contributed to the collision.

        Compares mover's previous position against other's current
        (post-move) rect. Returns True when the previous position does
        NOT overlap, meaning mover's movement closed the gap.
        """
        prev_rect = pygame.Rect(
            round(mover.prev_x), round(mover.prev_y),
            mover.width, mover.height,
        )
        return not prev_rect.colliderect(other.rect)

    def _handle_tank_vs_tank(
        self,
        tank_a: Tank,
        tank_b: Tank,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        a_caused = self._caused_collision(tank_a, tank_b)
        b_caused = self._caused_collision(tank_b, tank_a)
        neither = not a_caused and not b_caused

        if a_caused or neither:
            tank_a.revert_move()
        if b_caused or neither:
            tank_b.revert_move()

        # Notify tanks that caused the collision so enemies change direction.
        # In the 'neither' case (pre-existing overlap), notify both so they
        # can escape rather than staying stuck indefinitely.
        if a_caused or neither:
            tank_a.on_wall_hit()
        if b_caused or neither:
            tank_b.on_wall_hit()
        return True

    def _handle_tank_vs_tile(
        self,
        tank: Tank,
        tile: Tile,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if tile.type in IMPASSABLE_TILE_TYPES:
            tank.revert_move(tile.rect)
            tank.on_wall_hit()
            return True
        return False
