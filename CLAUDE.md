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

# Check the package layers (import-linter, also run in CI and pre-commit)
lint-imports
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

- **Two-step collision resolution:** Tanks move optimistically in `Tank._move()`, then `CollisionManager.resolve` finds every overlap and responds to them in order, calling `Tank.revert_move(obstacle_rect)` to snap a tank flush against the obstacle.
- **Detection, response, outcomes:** `Battle` makes one collision call, `CollisionManager.resolve(players, enemies, bullets)`; the tiles, the Base and the Power-Ups come from the `Map` and `PowerUpManager` it holds. Inside, it finds every collision first, in the order they are responded to (bullets first), then responds: it applies the physics later collisions in the frame depend on (bullets, reverts, tile damage, `take_damage`) and returns game-level outcomes (`src/battle/outcomes.py`). `PowerUpManager.apply` changes only the collecting Player and returns the Grenade, Clock and Shovel as outcomes too. `Battle.apply_outcomes()` applies them (score, removal, Carrier drops, respawn, Power-Up effects), then decides Game Over and Victory in one place. See `docs/adr/0003-collision-response-returns-outcomes.md`.
- **Screen Flow vs. Battle:** `ScreenFlow` owns the Screen Flow (the current `Screen`, the title, pause and options menus, curtain, Game Over animation) and which Stage comes next. It never holds a `Battle` and needs no window: it takes `MenuAction`s (including `PAUSE`), `dt` and the frame's `BattleResult`, and reports what to draw, whether the Battle steps (`battle_steps`) and when to start one (`take_battle_request()` returns a `BattleRequest`). `GameManager` is its pygame adapter: it forwards `InputHandler`'s menu actions, loads the Stage's map file, builds and steps the Battle, and draws what the flow reports. Integration tests of frame rules build a bare Battle with `make_battle(mode)` (or the `battle` fixture) in `tests/integration/conftest.py`; tests of the screens or the adapter reach a running Battle the way a player does, with `start_game(mode)` and `reach_next_stage(game)`. See `docs/adr/0007-the-screen-flow-never-holds-a-battle.md`. A `Battle` owns one Stage's collaborators (`Map`, `BaseWall`, `PlayerManager`, `EnemyManager`, `SpawnManager`, `PowerUpManager`, `EffectManager`, `TankStepper`, `CollisionManager`), runs the frame pipeline in `step(dt)` and returns a `BattleResult` when it ends. Each Battle is built from the previous one's `carried_progress` (lives, Stars, score). A Battle needs no window or `SettingsManager`, so frame rules are tested against it directly. Its collaborators are private: `GameManager` renders from `battle.scene()` (a `BattleScene` of the live objects to draw, unlike the World View's values), and tests arrange a running Battle through its public setup calls (`add_enemy`, `replace_roster`, `drop_power_up`, ...) rather than swapping collaborators. See `docs/adr/0004-a-battle-owns-one-stage.md`.
- **One stepping path:** `TankStepper` steps every tank, Player or Enemy, through a frame (timers, ice check, Slide or move, then fire within the Bullet Cap) and owns the only bullet list. Frozen is state on `Tank`, and the stepper decides it for every tank: a Frozen tank's timers run and it finishes a Slide, but it neither moves, turns nor fires. `EnemyAI` (random direction changes, periodic shooting) and `PlayerInput` only supply intent. The owner of each kind of tank calls the stepper: `PlayerManager.update` for Players, `EnemyManager.step_enemies` for Enemies (pairs each with its `EnemyAI`, steers it toward the nearest Player; it owns the Clock, which freezes every Enemy, including those that Appear during it, and steps each Frozen Enemy without `EnemyAI.update`). `SpawnManager` only works through the Stage's Roster: `Battle` starts the first Enemy Spawning when it begins, then each frame `Battle.bring_in_spawns()` hands the Enemies that Appeared (`take_appeared()`) to `EnemyManager` before `advance()` runs the spawn timer. See `docs/adr/0002-one-stepping-path-for-all-tanks.md` and, for why that handoff stays in `Battle`, `docs/adr/0006-spawning-and-the-enemies-on-the-battlefield-stay-separate.md`.
- **CPU Partner is a `PlayerInput`:** In 1 Player + CPU mode, `GameManager` builds a `CpuPartnerInput` and hands it through `Battle` to `PlayerManager`, which pairs it with P2's ordinary `PlayerTank`. Each frame `Battle` builds a read-only `WorldView`, and `PlayerManager.observe` hands each input its own view (Human inputs ignore it). The CPU Partner decides from the view alone, so it follows every Player rule with no special cases. Its helpers live next to it in `src/cpu_partner/` (`goal_timing`, `pathfinding`, `steering`, `cut_off`, `dodge`). Its Dodge against Incoming Shots is a reflex checked before its Goal, not a Goal. See `docs/adr/0001-cpu-partner-as-player-input.md`, `docs/adr/0005-dodge-is-a-reflex-not-a-goal.md` and `docs/cpu-partner.md`.
- **Logical vs. display surface:** `GameManager` renders to a `game_surface` (512x512) then scales up to the window (1024x1024) for a pixel-art effect.
- **Fixed timestep:** `dt = 1.0 / fps` (constant, not measured from clock).
- **No pygame.sprite.Group:** Entities are plain classes, managed via plain lists (tanks in `PlayerManager`/`EnemyManager`, bullets in `TankStepper`).

### Source Layout

- `src/core/` — Game entities (`GameObject`, `Tank`, `PlayerTank`, `EnemyTank`, `Bullet`, `Tile`, `Map`, `PowerUp`, `Effect`), `BaseWall` (the Shovel's Fortify and revert), `EnemyAI` and `SpriteAtlas`
- `src/shell/` — `GameManager` (main loop; pygame adapter around the Screen Flow), `ScreenFlow` (screens, menus, curtain, Stage advance; `BattleRequest`), `Renderer`, `TextureManager` (sprite atlas slicing), `SoundManager`, `SettingsManager`, `MenuController`, `InputHandler` (menu and system input)
- `src/battle/` — `Battle` (one Stage: frame pipeline, applying collision outcomes, Game Over / Victory), `CollisionManager` (finds and responds to a frame's collisions) and its `outcomes`, `TankStepper` (per-frame tank stepping, bullet list), `PlayerManager` (player slots: tank, input, kind, score), `PlayerInput` (keyboard, controller), `EnemyManager` (Enemies on the battlefield, their AIs, Frozen), `SpawnManager` (the Roster, spawn timer and animations), `PowerUpManager` (the Power-Up on the battlefield; `apply` gives the Player its effect), `EffectManager`, `SoundPlayer` (the sound calls the Battle makes)
- `src/cpu_partner/` — `CpuPartnerInput` and its helpers (`goal_timing`, `pathfinding`, `steering`, `cut_off`, `dodge`)
- `src/world_view/` — `WorldView` (what the Battle hands the CPU Partner) and `footprint` (which grid cells a tank covers, and when it blocks an Enemy Spawn Point)
- `src/states/` — `Screen` enum (the Screen Flow: TITLE_SCREEN, RUNNING, PAUSED, OPTIONS_MENU, STAGE_CURTAIN_CLOSE/OPEN, GAME_OVER_ANIMATION, VICTORY, GAME_COMPLETE, EXIT), `GameMode` enum (ONE_PLAYER, TWO_PLAYERS, ONE_PLAYER_CPU) and `BattleResult` enum (GAME_OVER, VICTORY)
- `src/utils/constants.py` — All game constants (sizes, speeds, grid dimensions, colors)

The packages are layered, and `lint-imports` (import-linter, contracts in `pyproject.toml`) fails when an import points the wrong way: `shell` → `battle` and `cpu_partner` (which never import each other) → `world_view` → `core`. `states` and `utils` import none of them. `core/` and the Battle annotate with the `SpriteAtlas` and `SoundPlayer` Protocols, never the shell's classes. See `docs/adr/0008-four-layered-packages-with-the-world-view-between-battle-and-cpu-partner.md`.

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
│   ├── shell/                # Screen Flow, menus, input, rendering, textures, sound
│   ├── battle/               # the Battle and its collaborators
│   ├── cpu_partner/          # CPU Partner (world_views.py builds World Views by hand)
│   ├── world_view/           # World View and footprint
│   └── utils/                # utility unit tests
└── integration/
    ├── conftest.py           # make_battle(mode) / battle: a bare Battle; start_game(mode) / reach_next_stage: real GameManager driven by input; SDL dummy driver
    └── test_*.py             # end-to-end tests with real objects
```

### Mocking Policy

**Mock these:**
- External I/O: `TextureManager`, pygame display/font/surface, file system
- Cross-module boundaries: when testing `shell/`, `battle/`, `cpu_partner/` or `world_view/`, mock `core/` entities; when testing `core/`, mock their dependencies
- Non-determinism: `random.choice`, `random.uniform`

**Do NOT mock these:**
- Objects within the same module: Tank tests create real Bullets, EnemyTank/PlayerTank use real Tank through inheritance
- Pure logic with no dependencies: InputHandler, level_data, constants

**Data-carrier exception:** within-module mocks are allowed when the dependency is used only as a data carrier (read-only attribute access, no behavior). Example: `test_bullet.py` mocks the owner Tank because Bullet only reads `owner.owner_type` and map dimensions.

**Per-call collaborator exception:** within-module mocks are allowed for a collaborator the unit under test is handed on each call, when the test is about what the unit asks of it. The collaborator's own behavior is covered by its own tests. Example: `test_enemy_manager.py` mocks the `TankStepper` passed to `step_enemies`, to check which Enemy is stepped with which AI.

**Collision exception:** `test_collision_manager.py` uses real `core/` entities on a real `Map`, `EffectManager` and `PowerUpManager`, since what it checks is how they collide. Only I/O (`TextureManager`, `SoundManager`) is mocked. Tests call `resolve` and read the outcomes and the entities' state, never the module's internals.

**Battle exception:** `test_battle.py` uses real collaborators and real `core/` entities, since a `Battle` is what puts one Stage's pieces together and its frame rules are tested against it directly (ADR-0004). Only I/O (`TextureManager`, `SoundManager`) and the Enemy AIs handed to `add_enemy` are mocked. Tests arrange a Battle through its public calls and read it through `scene()`, never by swapping a collaborator.

### Integration Tests

Real map files, a real `TextureManager` and `EnemyAI`, and real frames, with `SDL_VIDEODRIVER=dummy` for headless execution. The only stand-in is the conftest's `SoundRecorder`, which takes the `SoundManager`'s place and remembers the sound calls a Battle makes. No mocks, except patching `random` to pin down Enemy AI choices.

- Tests of a frame rule build a bare Battle with `make_battle(mode, sound=...)` or the `battle` fixture, and step it with `tick(battle, n)`. How a Battle ends is read from `battle.result`.
- Only tests of the screens, the menus or the adapter build a whole `GameManager` with `start_game(mode)` and run whole frames with `run_frames(game, n)`. That includes going on to the next Stage (`reach_next_stage(game)`), since carrying progress into the next Battle is the adapter's job. They pass `game.battle` to the same helpers.
- Unlike `tests/unit/battle/`, which checks one rule with I/O mocked and arranges each case by hand, integration tests play the real assets over many frames.

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
