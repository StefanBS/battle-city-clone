# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Battle City (NES) clone built with Python 3.12 and Pygame. Uses `uv` as the package manager.

## Common Commands

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run the game
python main.py

# Run all tests
pytest

# Run tests with coverage
pytest --cov=src

# Run a specific test file or test
pytest tests/unit/core/test_tank.py
pytest tests/unit/core/test_tank.py::TestTank::test_shoot

# Lint and format (ruff)
ruff check src/ tests/
ruff check --fix src/ tests/
ruff format src/ tests/
```

## Architecture

### Inheritance Hierarchy

```
GameObject (base: position, rect, draw, update)
├── Tank (movement, shooting, health)
│   ├── PlayerTank (keyboard input, respawn, lives)
│   └── EnemyTank (AI: random direction changes, periodic shooting; 4 types: basic/fast/power/armor)
└── Bullet (directional movement, bounds checking)
```

### Key Design Patterns

- **Two-step collision resolution:** Tanks move optimistically in `Tank._move()`, then `CollisionManager` detects overlaps and queues events, then `GameManager._process_collisions()` calls `Tank.revert_move(obstacle_rect)` to snap the tank flush against the obstacle.
- **Separation of detection vs. response:** `CollisionManager` only detects collisions and queues events. `GameManager._process_collisions()` handles all outcomes (damage, tile destruction, state changes).
- **One bullet per tank:** Each tank holds a single `Optional[Bullet]`. A new bullet fires only when the previous one is inactive.
- **Logical vs. display surface:** `GameManager` renders to a `game_surface` (512x512) then scales up to the window (1024x1024) for a pixel-art effect.
- **Fixed timestep:** `dt = 1.0 / fps` (constant, not measured from clock).
- **No pygame.sprite.Group:** Entities are plain classes, managed via lists in `GameManager`.

### Source Layout

- `src/core/` — Game entities (`GameObject`, `Tank`, `PlayerTank`, `EnemyTank`, `Bullet`, `Tile`, `Map`)
- `src/managers/` — `GameManager` (main loop, spawning, collision dispatch), `CollisionManager`, `TextureManager` (sprite atlas slicing), `InputHandler`
- `src/states/` — `GameState` enum: RUNNING, GAME_OVER, VICTORY, EXIT
- `src/utils/constants.py` — All game constants (sizes, speeds, grid dimensions, colors)

### Map and Tiles

Grid is 16x16 tiles, each 32x32px. Tile types: EMPTY, BRICK (destructible), STEEL (indestructible), WATER (blocks tanks, not bullets), BUSH (visual only), ICE, BASE, BASE_DESTROYED. Currently uses a hardcoded test map in `Map._create_test_map()`. The `feature/use-pytmx` branch has TMX assets (`assets/maps/level_01.tmx`) but pytmx loading is not yet wired into the code.

### TextureManager

Loads `assets/sprites/sprites.png` as an atlas. Sprites are sliced from an 8x8 source grid and scaled to TILE_SIZE (32px). Sprite names are looked up from a hardcoded coordinate table.

## Testing Conventions

### Directory Structure

```
tests/
├── conftest.py              # shared fixtures (mock_texture_manager, create_tank, event factories)
├── unit/
│   ├── conftest.py           # pygame_init (session-scoped, autouse, SDL dummy driver)
│   ├── core/                 # entity unit tests
│   ├── managers/             # manager unit tests
│   └── utils/                # utility unit tests
└── integration/
    ├── conftest.py           # real GameManager fixture, SDL dummy driver
    └── test_*.py             # end-to-end tests with real objects
```

### Mocking Policy

**Mock these:**
- External I/O: `TextureManager`, pygame display/font/surface, file system
- Cross-module boundaries: when testing `managers/`, mock `core/` entities; when testing `core/`, mock `managers/` dependencies
- Non-determinism: `random.choice`, `random.uniform`

**Do NOT mock these:**
- Objects within the same module: Tank tests create real Bullets, EnemyTank/PlayerTank use real Tank through inheritance
- Pure logic with no dependencies: InputHandler, level_data, constants

**Data-carrier exception:** within-module mocks are allowed when the dependency is used only as a data carrier (read-only attribute access, no behavior). Example: `test_bullet.py` mocks the owner Tank because Bullet only reads `owner.owner_type` and map dimensions.

### Integration Tests

Real objects only, no mocks. `SDL_VIDEODRIVER=dummy` for headless execution.

### General

- Tests are organized in classes (e.g., `class TestTank:`)
- Use `@pytest.mark.parametrize` for multi-case testing (directions, tank types)
- Use `MagicMock(spec=ClassName)` when mocking to catch interface mismatches

## Code Style

- Ruff for linting (rules: E, F) and formatting (double quotes, 88 char line length)
- PEP 8, type hints on public APIs, docstrings on public functions/classes
- Pre-commit hooks run ruff check --fix and ruff format automatically

## Git Conventions

- When writing a git commit, never add Claude as a co-author.
- When creating a pull request, never mention Claude as a co-author or generator.
