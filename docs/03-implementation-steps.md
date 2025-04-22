# Battle City Clone - Implementation Steps

## 1. Setup
- Install Python and pygame/arcade
- Create project structure:
  - Assets folder
  - Source code folder

## 2. Basic Window
- Create a basic Pygame/Arcade window
- Implement core game loop structure with timing

## 3. Map Rendering
- Define Tile types
- Create a simple, hardcoded Map (2D list)
- Render static map tiles onto the screen
- *(Future: Integrate Tiled and pytmx/Arcade's loader)*

## 4. Player Tank
- Create the `PlayerTank` class
- Load a simple sprite
- Implement keyboard input handling (`InputHandler`) for 4-directional movement
- Implement basic collision with Brick/Steel tiles to stop movement

## 5. Shooting
- Implement the `Bullet` class
- Allow player tank to shoot (spacebar)
- Make the bullet move
- Limit to one bullet on screen initially

## 6. Collision (Bullet-Wall)
- Implement AABB collision detection between Bullet and Brick tiles
- Destroy the brick tile upon collision
- Make bullets stop at Steel

## 7. Base & Game Over
- Add the Base (Eagle) tile
- Implement collision check: if any bullet hits the Base, trigger a "Game Over" state

## 8. Basic Enemies
- Create a simple `EnemyTank` class with basic random movement AI
- Spawn one enemy on the map
- Implement bullet-tank collision (destroy enemy)

## 9. Refinement Loop

### Core Gameplay
- Add enemy shooting
- Implement player lives and respawning
- Implement enemy spawning logic (from specific points, limited total enemies per level)
- Implement level win condition (all enemies destroyed)
- Add different enemy types

### Features & Polish
- Add scoring (`UIManager`)
- Implement power-ups (`PowerUpManager`)
- Add sound effects (`SoundManager`)
- Improve AI
- Load maps from Tiled files
- Add menus (Main Menu, Pause Menu)
