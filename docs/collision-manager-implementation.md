# Simple Centralized Manager (Type-Based Pairwise Checks)

## Implementation

*   A `CollisionManager` class is created.
*   The `GameManager` (or main game loop) passes lists of relevant active objects to the `CollisionManager` each frame (e.g., `player_bullets`, `enemy_bullets`, `enemy_tanks`, `player_tank`, `destructible_tiles`, `player_base`).
*   The `CollisionManager` has methods like `check_collisions()`. Inside this method, it iterates through meaningful pairs of these lists using nested loops and performs AABB (Axis-Aligned Bounding Box) checks using `pygame.Rect.colliderect()`.

### Example Checks

*   Loop through `player_bullets` vs `enemy_tanks`.
*   Loop through `player_bullets` vs `destructible_tiles`.
*   Loop through `player_bullets` vs `player_base` (if friendly fire is off) or `enemy_bullets` vs `player_base`.
*   Loop through `enemy_bullets` vs `player_tank`.
*   Loop through `enemy_bullets` vs `destructible_tiles`.
*   Loop through `all_tanks` vs `impassable_tiles` (for movement prediction/blocking).
*   Loop through `all_tanks` vs `all_tanks` (excluding self-collision).

### Collision Handling
Queue collision events by storing `(object_a, object_b)` pairs. The `GameManager` processes this queue after all checks are complete, calling appropriate handlers based on the object types involved.
