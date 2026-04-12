import pygame
from typing import List, Tuple, Optional, Protocol, runtime_checkable, Sequence


# Define a protocol for objects that have a rect attribute
@runtime_checkable
class Collidable(Protocol):
    rect: pygame.Rect


class CollisionManager:
    """Manages collision detection between game objects."""

    def __init__(self) -> None:
        """Initializes the CollisionManager."""
        # Stores pairs of objects that have collided
        self._collision_events: List[Tuple[Collidable, Collidable]] = []
        self._seen_pairs: set[tuple[int, int]] = set()

    def check_collisions(
        self,
        player_tanks: Sequence[Collidable],
        player_bullets: Sequence[Collidable],
        enemy_tanks: Sequence[Collidable],
        enemy_bullets: Sequence[Collidable],
        tank_blocking_tiles: Sequence[Collidable],
        bullet_blocking_tiles: Sequence[Collidable],
        player_base: Optional[Collidable],
        power_ups: Sequence[Collidable] = (),
    ) -> None:
        """
        Checks for collisions between different groups of game objects.

        Args:
            player_tanks: List of player tank objects (may be empty).
            player_bullets: A list/group of player bullet objects.
            enemy_tanks: A list/group of enemy tank objects.
            enemy_bullets: A list/group of enemy bullet objects.
            tank_blocking_tiles: Tiles that block tank movement.
            bullet_blocking_tiles: Tiles that block bullets.
            player_base: The player's base object, or None if not present.
            power_ups: Active power-up objects to check against players.
        """
        self._collision_events.clear()
        self._seen_pairs.clear()

        # Combine tanks
        all_tanks: List[Collidable] = list(player_tanks)
        all_tanks.extend(enemy_tanks)

        # Bullet collisions
        self._check_group_vs_group(player_bullets, enemy_tanks)
        self._check_group_vs_group(player_bullets, bullet_blocking_tiles)
        self._check_bullet_vs_bullet(player_bullets, enemy_bullets)
        self._check_group_vs_group(enemy_bullets, bullet_blocking_tiles)

        # Bullets vs single targets
        if player_base:
            self._check_group_vs_single(player_bullets, player_base)
            self._check_group_vs_single(enemy_bullets, player_base)
        for player_tank in player_tanks:
            self._check_group_vs_single(enemy_bullets, player_tank)
            self._check_group_vs_single(player_bullets, player_tank)

        # Tank collisions
        self._check_group_vs_group(all_tanks, tank_blocking_tiles)
        self._check_self_collisions(all_tanks)

        # Power-up collection
        for player_tank in player_tanks:
            for power_up in power_ups:
                if player_tank.rect.colliderect(power_up.rect):
                    self._queue_collision(player_tank, power_up)

    def _check_group_vs_group(
        self,
        group_a: Sequence[Collidable],
        group_b: Sequence[Collidable],
    ) -> None:
        """Check all pairs between two groups for collisions."""
        for obj_a in group_a:
            for obj_b in group_b:
                if obj_a.rect.colliderect(obj_b.rect):
                    self._queue_collision(obj_a, obj_b)

    def _check_bullet_vs_bullet(
        self,
        group_a: Sequence[Collidable],
        group_b: Sequence[Collidable],
    ) -> None:
        """Check bullet-vs-bullet collisions using swept rects to prevent tunneling.

        Swept rects cover both the previous and current positions of each
        bullet, so fast-moving bullets heading towards each other cannot
        pass through one another between frames.
        """
        for bullet_a in group_a:
            rect_a = self._get_swept_rect(bullet_a)
            for bullet_b in group_b:
                rect_b = self._get_swept_rect(bullet_b)
                if rect_a.colliderect(rect_b):
                    self._queue_collision(bullet_a, bullet_b)

    def _check_group_vs_single(
        self,
        group: Sequence[Collidable],
        target: Collidable,
    ) -> None:
        """Check all objects in a group against a single target."""
        for obj in group:
            if obj.rect.colliderect(target.rect):
                self._queue_collision(obj, target)

    def _check_self_collisions(self, group: Sequence[Collidable]) -> None:
        """Check all unique pairs within a single group."""
        for i, obj_a in enumerate(group):
            for obj_b in group[i + 1 :]:
                if obj_a.rect.colliderect(obj_b.rect):
                    self._queue_collision(obj_a, obj_b)

    @staticmethod
    def _get_swept_rect(obj: Collidable) -> pygame.Rect:
        """Return the swept_rect if available, otherwise fall back to rect."""
        swept = getattr(obj, "swept_rect", None)
        if isinstance(swept, pygame.Rect):
            return swept
        return obj.rect

    def _queue_collision(self, obj_a: Collidable, obj_b: Collidable) -> None:
        """Adds a collision event to the queue, deduplicating pairs."""
        pair_key = (id(obj_a), id(obj_b))
        reverse_key = (id(obj_b), id(obj_a))
        if pair_key in self._seen_pairs or reverse_key in self._seen_pairs:
            return
        self._seen_pairs.add(pair_key)
        self._collision_events.append((obj_a, obj_b))

    def get_collision_events(self) -> List[Tuple[Collidable, Collidable]]:
        """Returns the list of detected collision events for this frame."""
        return self._collision_events
