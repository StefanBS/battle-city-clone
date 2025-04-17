# Technical Architecture & Design Patterns

## Core Design Principles

### Modular Design
- Break the game into distinct, loosely coupled components

### Object-Oriented Programming (OOP)
Ideal for representing game entities

#### Base Classes and Components

##### GameObject (Abstract Base Class)
Common properties and methods:
- Position (x, y)
- Dimensions (width, height)
- Sprite/image
- `update()` method
- `draw()` method

##### Tank (GameObject)
Properties:
- Direction
- Speed
- Health
- Bullet limit
- Bullet speed
- Shoot cooldown

Methods:
- `move()`
- `shoot()`
- `take_damage()`

###### PlayerTank (Tank)
Additional features:
- Input handling
- Lives
- Score
- Power-up state

###### EnemyTank (Tank)
Additional features:
- AI logic (`update_ai()`)
- Type (basic, fast, power, armor)

##### Bullet (GameObject)
Properties:
- Direction
- Speed
- Owner type (player/enemy)
- Power (for hitting steel)

Methods:
- `move()`

##### Tile (GameObject)
Properties:
- Tile type (enum: BRICK, STEEL, etc.)
- Is destructible
- Is passable
- Can be static or have simple state (e.g., damaged brick)

##### Map
Manages the grid of Tile objects

Methods:
- `load_level()`
- `get_tile(x, y)`
- `set_tile(x, y)`
- `get_tiles_in_rect(rect)`

##### GameManager
Orchestrates the game flow

Responsibilities:
- Manages state (MainMenu, Playing, Paused, GameOver, LevelComplete)
- Score
- Current level
- Remaining lives
- Enemy spawning
- Collision detection delegation
- Game loop control

##### InputHandler
Translates raw input events (keyboard presses) into game actions (move left, shoot)

##### Renderer
Responsibilities:
- Drawing all GameObject instances onto the screen/surface
- Managing loading and caching sprites

##### CollisionDetector
Contains logic for:
- Bullet vs tank collisions
- Tank vs tile collisions
- Tank vs tank collisions
- Uses AABB (Axis-Aligned Bounding Box) collision detection

##### UIManager
Displays:
- Score
- Lives
- Level number
- Remaining enemies
- Menus

##### SoundManager
Handles:
- Loading sound effects
- Playing sound effects
- Background music

##### PowerUpManager
Manages:
- Power-up spawning
- Collection
- Effect application
- Duration

## Design Patterns

### State Pattern
- Manages game states (MainMenu, Playing, Paused, etc.) within GameManager
- Each state object implements:
  - `handle_input()`
  - `update()`
  - `render()`

## Technical Implementation

### Map Representation
- 2D list (list of lists)
- Each element is either:
  - Tile object instance
  - Identifier (enum/int) for Tile object creation
- Recommended: Load from file format (e.g., TMX from Tiled) instead of hardcoding

### Collision Detection
- Primary method: Axis-Aligned Bounding Box (AABB)
- Grid-based movement:
  - Check target grid cell before moving
- Bullet collision:
  - Check collision with objects in movement path for current frame

### Enemy AI
Simple implementation mimicking the original:

- Random movement changes:
  - At intervals
  - When hitting obstacles
- Targeting behavior:
  - Move towards player's base
  - Target player tank within line-of-sight/proximity
- Pathfinding:
  - Try direct routes first
  - Random turns if blocked
- State machine:
  - Patrolling
  - Attacking
- Shooting logic:
  - Random intervals
  - When target is aligned
