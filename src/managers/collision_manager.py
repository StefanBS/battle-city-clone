import pygame
from typing import List, Tuple, Optional, Protocol, runtime_checkable, Sequence
from loguru import logger # Import loguru


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
        self._collision_events.clear()  # Clear events from previous frame
        logger.trace("Collision check started. Cleared previous events.")

        # Combine tanks, handling potential None for player_tank
        all_tanks: List[Collidable] = []
        if player_tank:
            all_tanks.append(player_tank)
        all_tanks.extend(enemy_tanks)

        # Player bullets vs Enemy tanks
        for bullet in player_bullets:
            for tank in enemy_tanks:
                if bullet.rect.colliderect(tank.rect):
                    self._queue_collision(bullet, tank)

        # Player bullets vs Destructible tiles
        for bullet in player_bullets:
            for tile in destructible_tiles:
                if bullet.rect.colliderect(tile.rect):
                    self._queue_collision(bullet, tile)

        # Player bullets vs Enemy bullets
        for p_bullet in player_bullets:
            for e_bullet in enemy_bullets:
                if p_bullet.rect.colliderect(e_bullet.rect):
                    self._queue_collision(p_bullet, e_bullet)

        # Player bullets vs Impassable tiles
        for bullet in player_bullets:
            for tile in impassable_tiles:
                if bullet.rect.colliderect(tile.rect):
                    self._queue_collision(bullet, tile)

        # Enemy bullets vs Player base
        if player_base:
            for bullet in enemy_bullets:
                if bullet.rect.colliderect(player_base.rect):
                    self._queue_collision(bullet, player_base)

        # Enemy bullets vs Player tank
        if player_tank:
            for bullet in enemy_bullets:
                if bullet.rect.colliderect(player_tank.rect):
                    self._queue_collision(bullet, player_tank)

        # Enemy bullets vs Destructible tiles
        for bullet in enemy_bullets:
            for tile in destructible_tiles:
                if bullet.rect.colliderect(tile.rect):
                    self._queue_collision(bullet, tile)

        # Enemy bullets vs Impassable tiles
        for bullet in enemy_bullets:
            for tile in impassable_tiles:
                if bullet.rect.colliderect(tile.rect):
                    self._queue_collision(bullet, tile)

        # Tanks vs Impassable tiles
        for tank in all_tanks:
            for tile in impassable_tiles:
                if tank.rect.colliderect(tile.rect):
                    self._queue_collision(tank, tile)

        # Tanks vs Tanks
        for i, tank_a in enumerate(all_tanks):
            # Check against tanks listed after tank_a to avoid duplicates/self-collision
            for tank_b in all_tanks[i + 1 :]:
                if tank_a.rect.colliderect(tank_b.rect):
                    self._queue_collision(tank_a, tank_b)

        logger.trace(f"Collision check finished. Found {len(self._collision_events)} events.")

    def _queue_collision(self, obj_a: Collidable, obj_b: Collidable) -> None:
        """Adds a collision event to the queue."""
        # Basic type checking for logging purposes
        type_a = type(obj_a).__name__
        type_b = type(obj_b).__name__
        logger.debug(f"Collision detected between {type_a} and {type_b}")
        self._collision_events.append((obj_a, obj_b))

    def get_collision_events(self) -> List[Tuple[Collidable, Collidable]]:
        """Returns the list of detected collision events for this frame."""
        return self._collision_events


# Basic Rect object for testing purposes if needed
# Ensure this mock object matches the Collidable protocol if used for typing
class MockSprite(pygame.sprite.Sprite):  # Inherit from Sprite for type compatibility
    def __init__(self, x, y, w, h):
        super().__init__()  # Initialize the parent Sprite class
        self.rect = pygame.Rect(x, y, w, h)
