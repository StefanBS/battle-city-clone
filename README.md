# Battle City Clone

A Python and Pygame implementation of the classic NES game Battle City.

## Project Structure

```
battle-city-clone/
├── src/
│   ├── core/                       # Game entities
│   │   ├── game_object.py          # Base class (position, rect, draw, update)
│   │   ├── tank.py                 # Tank base (movement, shooting, health)
│   │   ├── player_tank.py          # Player-controlled tank (input, respawn, lives)
│   │   ├── enemy_tank.py           # AI-controlled tank (4 types: basic/fast/power/armor)
│   │   ├── bullet.py               # Bullet (directional movement, bounds checking)
│   │   ├── tile.py                 # Tile types and behavior
│   │   └── map.py                  # Map loading and tile grid management
│   │
│   ├── managers/                   # Game systems
│   │   ├── game_manager.py         # Main loop, orchestration, collision dispatch
│   │   ├── collision_manager.py    # Collision detection and event queuing
│   │   ├── collision_response_handler.py  # Collision outcome processing
│   │   ├── spawn_manager.py        # Enemy wave spawning logic
│   │   ├── renderer.py             # Rendering pipeline (logical → display surface)
│   │   ├── texture_manager.py      # Sprite atlas slicing and caching
│   │   └── input_handler.py        # Keyboard input mapping
│   │
│   ├── states/
│   │   └── game_state.py           # GameState enum (RUNNING, GAME_OVER, VICTORY, EXIT)
│   │
│   └── utils/
│       ├── constants.py            # Sizes, speeds, grid dimensions, colors
│       └── level_data.py           # Level definitions
│
├── assets/
│   ├── battle-city.tiled-project   # Tiled project (custom types and enums)
│   ├── sprites/                    # Sprite sheet (sprites.png) and tileset (sprites.tsx)
│   ├── sounds/                     # Sound effects and music (placeholder)
│   └── maps/                       # TMX level map files
│
├── tests/
│   ├── conftest.py                 # Shared fixtures
│   ├── unit/
│   │   ├── conftest.py             # pygame_init (session-scoped, SDL dummy driver)
│   │   ├── core/                   # Entity unit tests
│   │   └── managers/               # Manager unit tests
│   └── integration/                # End-to-end tests with real objects
│
├── main.py                         # Entry point
├── pyproject.toml                  # Project configuration and dependencies
└── README.md
```

## Controls

- Arrow keys to move
- Space to shoot
- Defend your base from enemy tanks

## Setup

Requires Python 3.12+.

1. Install [uv](https://docs.astral.sh/uv/) (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create and activate a virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
uv pip install -e ".[dev]"
```

4. Run the game:
```bash
python main.py
```

## Testing

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src

# Run a specific test file
pytest tests/unit/core/test_tank.py

# Run a specific test
pytest tests/unit/core/test_tank.py::TestTank::test_shoot
```

## Linting and Formatting

```bash
ruff check src/ tests/
ruff format src/ tests/
```
