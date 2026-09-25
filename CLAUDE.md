# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Battle City (NES) clone built with Python 3.13 and Pygame. Uses `uv` as the package manager.

- `CONTEXT.md` is the domain glossary (Player, CPU Partner, Goal, Roster, Battle, Frozen, ...). Use its terms in code, tests, docs and commit messages, and avoid the words it lists under _Avoid_.
- `docs/adr/` holds the architecture decisions. Read the relevant ADR before changing a design it covers.
- `docs/cpu-partner.md` explains how the CPU Partner decides, with state diagrams. Update it when its Goals, timing or engagement rules change.

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

# Type check (mypy, also run in CI and pre-commit)
mypy src
```

## Architecture

### Inheritance Hierarchy

```
GameObject (base: position, rect, draw, update)
├── Tank (movement, shooting, health)
│   ├── PlayerTank (respawn, lives, Stars, shield; driven by a PlayerInput)
│   └── EnemyTank (4 types: basic/fast/power/armor; driven by a paired EnemyAI)
└── Bullet (directional movement, bounds checking)
```

### Key Design Patterns

- **Two-step collision resolution:** Tanks move optimistically in `Tank._move()`, then `CollisionManager` detects overlaps and queues events, then `CollisionResponseHandler` calls `Tank.revert_move(obstacle_rect)` to snap the tank flush against the obstacle.
- **Detection, response, outcomes:** `CollisionManager` only detects collisions and queues events. `CollisionResponseHandler` applies the physics later events in the frame depend on (bullets, reverts, tile damage, `take_damage`) and returns game-level outcomes (`src/managers/outcomes.py`). `Battle.apply_outcomes()` applies them (score, removal, Carrier drops, respawn, Power-Up effects), then decides Game Over and Victory in one place. See `docs/adr/0003-collision-response-returns-outcomes.md`.
- **Screen flow vs. Battle:** `GameManager` owns the screen flow (menus, pause, curtain, Game Over animation) and which Stage comes next. A `Battle` owns one Stage's collaborators (`Map`, `PlayerManager`, `EnemyManager`, `SpawnManager`, `PowerUpManager`, `EffectManager`, `TankStepper`, collision managers), runs the frame pipeline in `step(dt)` and returns a `BattleResult` when it ends. Each Battle is built from the previous one's `carried_progress` (lives, Stars, score). A Battle needs no window or `SettingsManager`, so frame rules are tested against it directly. See `docs/adr/0004-a-battle-owns-one-stage.md`.
- **One stepping path:** `TankStepper` steps every tank, Player or Enemy, through a frame (timers, ice check, Slide or move, then fire within the Bullet Cap) and owns the only bullet list. Frozen is state on `Tank`, and the stepper decides it for every tank: a Frozen tank's timers run and it finishes a Slide, but it neither moves, turns nor fires. `EnemyAI` (random direction changes, periodic shooting) and `PlayerInput` only supply intent. The owner of each kind of tank calls the stepper: `PlayerManager.update` for Players, `EnemyManager.step_enemies` for Enemies (pairs each with its `EnemyAI`, steers it toward the nearest Player; during a Clock it freezes every Enemy, and steps them without `EnemyAI.update`). `SpawnManager` only works through the Stage's Roster: `update()` returns the Enemies that materialized, and `Battle` hands them to `EnemyManager`. See `docs/adr/0002-one-stepping-path-for-all-tanks.md`.
- **CPU Partner is a `PlayerInput`:** In 1 Player + CPU mode, `PlayerManager` pairs P2's ordinary `PlayerTank` with a `CpuPartnerInput`. Each frame `Battle` builds a read-only `WorldView`, and `PlayerManager.observe` hands each input its own view (Human inputs ignore it). The CPU Partner decides from the view alone, so it follows every Player rule with no special cases. Its helpers live next to it in `src/managers/` (`goal_timing`, `pathfinding`, `steering`, `refused_shots`, `enemy_memory`, `dodge`). Its Dodge against Incoming Shots is a reflex checked before its Goal, not a Goal. See `docs/adr/0001-cpu-partner-as-player-input.md`, `docs/adr/0005-dodge-is-a-reflex-not-a-goal.md` and `docs/cpu-partner.md`.
- **Logical vs. display surface:** `GameManager` renders to a `game_surface` (512x512) then scales up to the window (1024x1024) for a pixel-art effect.
- **Fixed timestep:** `dt = 1.0 / fps` (constant, not measured from clock).
- **No pygame.sprite.Group:** Entities are plain classes, managed via plain lists (tanks in `PlayerManager`/`EnemyManager`, bullets in `TankStepper`).

### Source Layout

- `src/core/` — Game entities (`GameObject`, `Tank`, `PlayerTank`, `EnemyTank`, `Bullet`, `Tile`, `Map`, `PowerUp`, `Effect`) and `EnemyAI`
- `src/managers/` — `GameManager` (main loop, screen flow), `Battle` (one Stage: frame pipeline, applying collision outcomes, Game Over / Victory), `CollisionManager`, `CollisionResponseHandler` and its `outcomes`, `TankStepper` (per-frame tank stepping, bullet list), `PlayerManager` (player slots: tank, input, kind, score), `PlayerInput` (keyboard, controller), `WorldView`, `footprint` (which grid cells a tank covers, and when it blocks an Enemy Spawn Point), `CpuPartnerInput` and its helpers, `EnemyManager` (Enemies on the battlefield, their AIs, Frozen), `SpawnManager` (the Roster, spawn timer and animations), `PowerUpManager`, `EffectManager`, `Renderer`, `TextureManager` (sprite atlas slicing), `SoundManager`, `SettingsManager`, `MenuController`, `InputHandler` (menu and system input)
- `src/states/` — `GameState` enum (screen flow: TITLE_SCREEN, RUNNING, PAUSED, OPTIONS_MENU, STAGE_CURTAIN_CLOSE/OPEN, GAME_OVER, GAME_OVER_ANIMATION, VICTORY, GAME_COMPLETE, EXIT) and `GameMode` enum (ONE_PLAYER, TWO_PLAYERS, ONE_PLAYER_CPU)
- `src/utils/constants.py` — All game constants (sizes, speeds, grid dimensions, colors)

### Map and Tiles

Maps are authored in [Tiled](https://www.mapeditor.org/) and loaded via `pytmx`. The Tiled project file (`assets/battle-city.tiled-project`) defines custom enums (`TileType`, `BrickVariant`, `SpawnPointType`) shared across all maps and tilesets. The tileset is `assets/sprites/sprites.tsx` (8x8 source tiles from `sprites.png`).

Grid is 26x26 sub-tiles (8x8px each), scaled to 32x32px at display. Tile types: EMPTY, BRICK (destructible, with variants: full/right/bottom/left/top), STEEL (indestructible), WATER (blocks tanks, not bullets), BUSH (visual only), ICE, BASE, BASE_DESTROYED. Level maps live in `assets/maps/` (e.g., `level_01.tmx`). Each map has a `spawn_points` object layer for player and enemy spawn positions.

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

**Per-call collaborator exception:** within-module mocks are allowed for a collaborator the unit under test is handed on each call, when the test is about what the unit asks of it. The collaborator's own behavior is covered by its own tests. Example: `test_enemy_manager.py` mocks the `TankStepper` passed to `step_enemies`, to check which Enemy is stepped with which AI.

### Integration Tests

Real objects only, no mocks. `SDL_VIDEODRIVER=dummy` for headless execution.

### General

- Tests are organized in classes (e.g., `class TestTank:`)
- Use `@pytest.mark.parametrize` for multi-case testing (directions, tank types)
- Use `MagicMock(spec=ClassName)` when mocking to catch interface mismatches

## Code Style

- Ruff for linting (rules: E, F) and formatting (double quotes, 88 char line length)
- PEP 8, type hints on public APIs, docstrings on public functions/classes
- Pre-commit hooks run ruff check --fix, ruff format and mypy automatically

## Git Conventions

- When writing a git commit, never add Claude as a co-author.
- When creating a pull request, never mention Claude as a co-author or generator.
