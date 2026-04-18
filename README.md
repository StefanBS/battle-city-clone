# Battle City Clone

A Python and Pygame implementation of the classic NES game Battle City, featuring all 35 stages, four enemy tank types, power-ups, sound effects, gamepad support, and more.

## Features

- **35 stages** authored in [Tiled](https://www.mapeditor.org/) with varied enemy compositions
- **4 enemy tank types** — basic, fast, power, and armor — each with unique sprites and stats
- **6 power-ups** — helmet, star, bomb, clock, shovel, extra life
- **Gamepad/controller support** — D-pad, analog sticks, hot-plug detection (SDL GameController API)
- **Sound effects** — shooting, explosions, power-ups, engine sounds, and more
- **Difficulty levels** — Easy (random AI) and Normal (directional bias, aligned shooting, type-specific tactics)
- **Options menu** — difficulty selection and master volume with persistent settings
- **Stage transitions** — curtain animations between stages
- **Explosion animations** — small and large explosions, spawn effects
- **Shield animation** — flicker effect on spawn invincibility
- **Tile types** — brick (destructible, with variants), steel, water, bush (overlay), ice (sliding physics), base

## Controls

### Keyboard

| Action        | Key              |
|---------------|------------------|
| Move          | Arrow keys       |
| Shoot         | Space            |
| Pause         | Enter            |
| Menu navigate | Arrow keys       |
| Menu confirm  | Space / Enter    |
| Restart       | R (on game over) |

### Gamepad

| Action        | Button                          |
|---------------|---------------------------------|
| Move          | D-pad / Left analog stick       |
| Shoot         | A / B                           |
| Pause         | Start                           |
| Menu navigate | D-pad / Left analog stick       |
| Menu confirm  | A / Start                       |

## Project Structure

```
battle-city-clone/
├── src/
│   ├── core/                              # Game entities
│   │   ├── game_object.py                 # Base class (position, rect, draw, update)
│   │   ├── tank.py                        # Tank base (movement, shooting, health)
│   │   ├── player_tank.py                 # Player tank (input, respawn, lives, shield)
│   │   ├── enemy_tank.py                  # AI tank (4 types, difficulty-aware behavior)
│   │   ├── bullet.py                      # Bullet (directional movement, bounds checking)
│   │   ├── tile.py                        # Tile types, collision properties, variants
│   │   ├── map.py                         # TMX map loading, tile grid, spawn points
│   │   ├── effect.py                      # Visual effects (explosions, spawn)
│   │   └── power_up.py                    # Power-up entity (blink, timeout, collection)
│   │
│   ├── managers/                          # Game systems
│   │   ├── game_manager.py                # Main loop, orchestration, state machine
│   │   ├── player_manager.py              # Player tanks, input, bullets, and score
│   │   ├── player_input.py                # Per-player gameplay input (keyboard/controller)
│   │   ├── input_handler.py               # Menu and system input (SDL GameController API)
│   │   ├── menu_controller.py             # Declarative menu navigation (items + callbacks)
│   │   ├── collision_manager.py           # Collision detection and event queuing
│   │   ├── collision_response_handler.py  # Collision outcome processing
│   │   ├── spawn_manager.py               # Enemy wave spawning logic
│   │   ├── renderer.py                    # Rendering pipeline (logical -> display surface)
│   │   ├── texture_manager.py             # Sprite atlas slicing and caching
│   │   ├── effect_manager.py              # Effect lifecycle management
│   │   ├── power_up_manager.py            # Power-up spawning, collection, effects
│   │   ├── sound_manager.py               # Sound effect loading and playback
│   │   └── settings_manager.py            # Persistent game settings (volume, difficulty)
│   │
│   ├── states/
│   │   └── game_state.py                  # GameState enum (RUNNING, PAUSED, GAME_OVER, ...)
│   │
│   └── utils/
│       ├── constants.py                   # Sizes, speeds, grid dimensions, enums, colors
│       └── paths.py                       # Resource path resolution (dev and packaged)
│
├── assets/
│   ├── battle-city.tiled-project          # Tiled project (custom types and enums)
│   ├── sprites/                           # Sprite sheet (sprites.png) and tileset (sprites.tsx)
│   ├── sounds/                            # Sound effects (.wav)
│   └── maps/                              # 35 TMX level maps
│
├── tests/
│   ├── conftest.py                        # Shared fixtures
│   ├── unit/                              # Entity and manager unit tests
│   └── integration/                       # End-to-end tests with real objects
│
├── scripts/
│   ├── generate_icons.py                  # App icon generation
│   └── generate_sounds.py                 # Sound effect generation
│
├── installer/                             # Platform-specific packaging
├── main.py                                # Entry point
├── pyproject.toml                         # Project configuration and dependencies
└── README.md
```

## Setup

Requires Python 3.13+.

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

## Building

To build a standalone executable:

```bash
uv pip install -e ".[build]"
pyinstaller battle-city.spec
```
