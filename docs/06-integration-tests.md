# Integration Test Plan

## 1. Introduction

This document outlines the plan for adding comprehensive integration tests to the Battle City Clone project. Integration tests focus on verifying the interactions between different components of the game (e.g., player movement and collision detection, bullets hitting walls, game state transitions). These tests ensure that modules work together as expected.

## 2. Test Environment and Tools

*   **Framework:** Pytest will be used as the test runner.
*   **Setup:** Tests will typically involve initializing the `GameManager`, which sets up the core components (Map, Player, CollisionManager, etc.).
*   **Simulation:** Pygame will be initialized in a headless mode (`pygame.NOFRAME`). Game updates will be simulated by calling `game_manager.update()` repeatedly over a specific duration (`dt`).
*   **Fixtures:** Consider creating Pytest fixtures for common setups (e.g., a `game_manager` fixture, potentially one with a specific map state).

## 3. Test Scenarios

The following scenarios represent key interactions to cover with integration tests:

### 3.1. Player Tank Integration

*   **Movement (Open Space):**
    *   Verify tank moves correctly Up, Down, Left, Right in an open area. *(Partially Implemented)*
    *   Verify tank sprite/direction updates correctly during movement.
*   **Movement (Blocked by Walls):**
    *   Verify tank cannot move into `STEEL` walls.
    *   Verify tank cannot move into `BRICK` walls.
    *   Verify tank cannot move into `WATER` tiles.
    *   Verify tank cannot move off the map boundaries. *(Implicitly tested by default map)*
*   **Shooting:**
    *   Verify pressing the shoot key creates an active `Bullet` object associated with the player.
    *   Verify the bullet spawns at the correct position relative to the tank.
    *   Verify the bullet travels in the direction the tank is facing.
    *   Verify the player cannot fire another bullet while one is active.
*   **Respawn Logic:**
    *   Verify player tank respawns at the starting location after being destroyed (if lives remain).
    *   Verify player tank is temporarily invincible after respawning.
    *   Verify player lives decrease upon destruction.
*   **Game Over (Player Lives):**
    *   Verify game state changes to `GAME_OVER` when the player runs out of lives.

### 3.2. Bullet and Collision Integration

*   **Bullet vs. Walls:**
    *   Verify bullet is destroyed upon hitting a `BRICK` wall.
    *   Verify the `BRICK` wall tile is destroyed (becomes `EMPTY`).
    *   Verify bullet is destroyed upon hitting a `STEEL` wall.
    *   Verify the `STEEL` wall tile remains unchanged.
    *   Verify bullet interaction with `WATER` (likely destroyed, no tile change).
    *   Verify bullet interaction with `BUSH` (likely passes through, no effect).
*   **Bullet vs. Tanks:**
    *   Verify player bullet hitting an enemy tank damages/destroys it.
    *   Verify enemy bullet hitting the player tank damages/destroys it (respecting invincibility).
    *   Verify enemy bullet hitting another enemy tank has no effect.
    *   Verify player bullet hitting another player bullet (if possible) has no effect or cancels both.
    *   Verify enemy bullet hitting another enemy bullet has no effect or cancels both.
*   **Bullet vs. Base:**
    *   Verify player bullet hitting the base has no effect.
    *   Verify enemy bullet hitting the base destroys it.
    *   Verify game state changes to `GAME_OVER` when the base is destroyed.

### 3.3. Enemy Tank Integration

*   **Spawning:**
    *   Verify enemies spawn at designated spawn points.
    *   Verify enemies do not spawn if the maximum number is already present.
    *   Verify enemies do not spawn if the spawn point is blocked.
    *   Verify the total enemy spawn count limit is respected.
*   **Movement:**
    *   Verify enemies change direction periodically.
    *   Verify enemies attempt to move.
    *   Verify enemies are blocked by walls correctly.
*   **Shooting:**
    *   Verify enemies shoot periodically.
    *   Verify enemy bullets travel correctly.
*   **Interaction:**
    *   Verify player destroying an enemy removes it from the game.

### 3.4. Game Flow Integration

*   **Initial State:**
    *   Verify `GameManager` initializes with the correct state (`RUNNING`), player lives, score (if applicable), etc.
    *   Verify the map loads the expected initial layout.
*   **Victory Condition:**
    *   Verify game state changes to `VICTORY` when all required enemies are destroyed (requires defining enemy waves/counts). *(Needs clarification on victory logic)*

## 4. Future Considerations

*   **Power-ups:** Test picking up and the effects of various power-ups.
*   **Different Enemy Types:** Test the specific behaviors (speed, health, bullet speed) of different enemy tank types.
*   **Map Variations:** Test interactions on different map layouts or with features like Ice tiles.
*   **Performance:** While not functional tests, consider adding benchmarks for key loops if performance becomes a concern. 