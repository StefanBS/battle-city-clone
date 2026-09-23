# Battle City Clone

A Python and Pygame implementation of the classic NES game Battle City, featuring all 35 stages, four enemy tank types, power-ups, two-player co-op, a computer-controlled partner, sound effects, gamepad support, and more.

## Features

- **35 stages** authored in [Tiled](https://www.mapeditor.org/) with varied enemy compositions
- **4 enemy tank types** — basic, fast, power, and armor — each with unique sprites and stats
- **6 power-ups** — helmet, star, grenade, clock, shovel, extra life
- **Game modes**: 1 Player, 2 Players (co-op), and 1 Player + CPU, where a [CPU Partner](docs/cpu-partner.md) drives P2 by the same rules as a human
- **Gamepad/controller support** — D-pad, analog sticks, hot-plug detection (SDL GameController API)
- **Sound effects** — shooting, explosions, power-ups, engine sounds, and more
- **Difficulty levels** — Easy (random Enemy AI) and Normal (directional bias, aligned shooting, type-specific tactics)
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
| Pause / back  | Esc              |
| Menu navigate | Arrow keys       |
| Menu confirm  | Enter / R        |

### Gamepad

| Action        | Button                          |
|---------------|---------------------------------|
| Move          | D-pad / Left analog stick       |
| Shoot         | A / B                           |
| Pause / back  | Start                           |
| Menu navigate | D-pad / Left analog stick       |
| Menu confirm  | A                               |
| Menu back     | B                               |

### Who controls which Player

| Mode           | P1                         | P2                                  |
|----------------|----------------------------|-------------------------------------|
| 1 Player       | Keyboard or any controller | —                                   |
| 1 Player + CPU | Keyboard or any controller | CPU Partner                         |
| 2 Players      | Keyboard (first controller if two are connected) | First controller (second if two are connected) |

With no controller connected, both Players in 2 Players mode share the keyboard's keys.

## Project Structure

```
battle-city-clone/
├── src/
│   ├── core/                              # Game entities
│   │   ├── game_object.py                 # Base class (position, rect, draw, update)
│   │   ├── tank.py                        # Tank base (movement, shooting, health)
│   │   ├── player_tank.py                 # Player tank (respawn, lives, Stars, shield)
│   │   ├── enemy_tank.py                  # Enemy tank (4 types, Carrier flashing)
│   │   ├── enemy_ai.py                    # Enemy AI: direction and shooting intent
│   │   ├── bullet.py                      # Bullet (directional movement, bounds checking)
│   │   ├── tile.py                        # Tile types, collision properties, variants
│   │   ├── map.py                         # TMX map loading, tile grid, spawn points
│   │   ├── effect.py                      # Visual effects (explosions, spawn)
│   │   └── power_up.py                    # Power-up entity (blink, timeout, collection)
│   │
│   ├── managers/                          # Game systems
│   │   ├── game_manager.py                # Main loop and screen flow (menus, pause, curtain)
│   │   ├── battle.py                      # One Stage: frame pipeline, outcomes, Game Over / Victory
│   │   ├── tank_stepper.py                # Steps every tank through a frame; owns the bullets
│   │   ├── player_manager.py              # Player slots: tanks, inputs, lives, and score
│   │   ├── enemy_manager.py               # Enemies on the battlefield, their AIs, Frozen
│   │   ├── player_input.py                # Per-player gameplay input (keyboard/controller)
│   │   ├── world_view.py                  # Read-only per-frame snapshot for Player inputs
│   │   ├── cpu_partner.py                 # CPU Partner input (Goals, aiming, safe shots)
│   │   ├── goal_timing.py                 # CPU Partner decision timing and hesitation
│   │   ├── pathfinding.py                 # A* over the sub-tile grid
│   │   ├── steering.py                    # CPU Partner: getting unstuck
│   │   ├── refused_shots.py               # CPU Partner: giving up on unsafe shots
│   │   ├── enemy_memory.py                # CPU Partner: per-Enemy memory until it moves
│   │   ├── input_handler.py               # Menu and system input (SDL GameController API)
│   │   ├── menu_controller.py             # Declarative menu navigation (items + callbacks)
│   │   ├── collision_manager.py           # Collision detection and event queuing
│   │   ├── collision_response_handler.py  # Collision physics; returns outcomes
│   │   ├── outcomes.py                    # Collision outcome types
│   │   ├── spawn_manager.py               # The Stage's Roster, spawn timer and animations
│   │   ├── renderer.py                    # Rendering pipeline (logical -> display surface)
│   │   ├── texture_manager.py             # Sprite atlas slicing and caching
│   │   ├── effect_manager.py              # Effect lifecycle management
│   │   ├── power_up_manager.py            # Power-up spawning, collection, effects
│   │   ├── sound_manager.py               # Sound effect loading and playback
│   │   └── settings_manager.py            # Persistent game settings (volume, difficulty)
│   │
│   ├── states/
│   │   ├── game_state.py                  # GameState enum (TITLE_SCREEN, RUNNING, PAUSED, ...)
│   │   └── game_mode.py                   # GameMode enum (1 Player, 2 Players, 1 Player + CPU)
│   │
│   └── utils/
│       ├── constants.py                   # Sizes, speeds, grid dimensions, enums, colors
│       ├── animation.py                   # Blink timing helper
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
├── docs/
│   ├── cpu-partner.md                     # How the CPU Partner decides (state diagrams)
│   └── adr/                               # Architecture decision records
│
├── installer/                             # Platform-specific packaging
├── main.py                                # Entry point
├── battle-city.spec                       # PyInstaller build spec
├── pyproject.toml                         # Project configuration and dependencies
├── CONTEXT.md                             # Domain glossary (Player, Goal, Roster, ...)
└── README.md
```

## Documentation

- [CONTEXT.md](CONTEXT.md): the domain language used in code, tests and docs
- [docs/cpu-partner.md](docs/cpu-partner.md): how the CPU Partner picks and pursues its Goals
- [docs/adr/](docs/adr/): architecture decisions
  - [0001](docs/adr/0001-cpu-partner-as-player-input.md) CPU Partner is a PlayerInput, not a tank subclass
  - [0002](docs/adr/0002-one-stepping-path-for-all-tanks.md) Every tank goes through one stepping path
  - [0003](docs/adr/0003-collision-response-returns-outcomes.md) Collision response returns outcomes
  - [0004](docs/adr/0004-a-battle-owns-one-stage.md) A Battle owns one Stage

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
