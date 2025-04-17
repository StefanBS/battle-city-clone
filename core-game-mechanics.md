# Core Game Mechanics

## Overview
- Top-Down View: 2D perspective
- Grid-Based Map: The world is fundamentally a grid of tiles

## Core Mechanics

### Tank Movement
- 4-directional (Up, Down, Left, Right)
- Aligned with the grid
- Occupies roughly 2x2 tiles
- Tanks cannot occupy the same grid space simultaneously (simple collision)
- Movement stops at obstacles

### Shooting
- Tanks fire projectiles (bullets) in the direction they face
- Typically, only one player bullet onscreen at a time (can be upgraded)
- Bullets travel linearly until hitting an obstacle or edge of the screen

### Tile Types
- **Empty**: Passable by tanks and bullets
- **Brick**: Blocks tanks. Destroyed by bullets (usually 1 hit)
- **Steel**: Blocks tanks. Destroyed only by upgraded player bullets (e.g., 3+ stars) or indestructible
- **Water**: Blocks tanks. Bullets pass over
- **Trees/Bushes**: Tanks pass through, bullets pass through. Visually obscures tanks underneath
- **Ice**: Tanks slide a short distance after stopping input
- **Base (Eagle)**: Must be protected. If destroyed by any bullet, Game Over. Blocks tanks

### Entities
- **Player Tank**
  - Controlled by the user
  - Starts with limited lives
  - Respawns at a designated base location
  - Can collect power-ups

- **Enemy Tanks**
  - Spawn from specific map locations
  - Varying types (speed, armor/hits required, bullet speed)
  - Basic AI (random movement, path towards base/player)

- **Bullets**
  - Fired by tanks
  - Have speed, direction, and owner (player/enemy)
  - Cause destruction/damage on impact

- **Power-ups**
  - Appear randomly (often after destroying flashing enemies)
  - Grant temporary abilities:
    - Invincibility
    - Freeze enemies
    - Upgrade weapon
    - Fortify base
    - Extra life
    - Destroy all enemies

## Game Systems

### Game Loop
Input → Update State → Render → Repeat

### Win/Loss Conditions
- **Win Level**: Destroy all predetermined enemy tanks for the level
- **Lose Level**: Player loses all lives OR the base is destroyed

### Progression
Multiple levels with increasing numbers/types of enemies and different map layouts
