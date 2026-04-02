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
        player_tank: Optional[Collidable],
        player_bullets: Sequence[Collidable],
        enemy_tanks: Sequence[Collidable],
        enemy_bullets: Sequence[Collidable],
        destructible_tiles: Sequence[Collidable],
        impassable_tiles: Sequence[Collidable],
        player_base: Optional[Collidable],
    ) -> None:
        """
        Checks for collisions between different groups of game objects.

        Args:
            player_tank: The player's tank object, or None if not present.
            player_bullets: A list/group of player bullet objects.
            enemy_tanks: A list/group of enemy tank objects.
            enemy_bullets: A list/group of enemy bullet objects.
            destructible_tiles: A list/group of destructible tile objects.
            impassable_tiles: A list/group of impassable tile objects.
            player_base: The player's base object, or None if not present.
        """
        self._collision_events.clear()
        self._seen_pairs.clear()

        # Combine tanks, handling potential None for player_tank
        all_tanks: List[Collidable] = []
        if player_tank:
            all_tanks.append(player_tank)
        all_tanks.extend(enemy_tanks)

        # Bullet collisions
        self._check_group_vs_group(player_bullets, enemy_tanks)
        self._check_group_vs_group(player_bullets, destructible_tiles)
        self._check_bullet_vs_bullet(player_bullets, enemy_bullets)
        self._check_group_vs_group(player_bullets, impassable_tiles)
        self._check_group_vs_group(enemy_bullets, destructible_tiles)
        self._check_group_vs_group(enemy_bullets, impassable_tiles)

        # Bullets vs single targets
        if player_base:
            self._check_group_vs_single(player_bullets, player_base)
            self._check_group_vs_single(enemy_bullets, player_base)
        if player_tank:
            self._check_group_vs_single(enemy_bullets, player_tank)

        # Tank collisions
        self._check_group_vs_group(all_tanks, impassable_tiles)
        self._check_self_collisions(all_tanks)

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
