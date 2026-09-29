# Battle City Clone

A Python and Pygame implementation of the classic NES game Battle City, featuring all 35 stages, four enemy tank types, power-ups, two-player co-op, a computer-controlled partner, sound effects, gamepad support, and more.

<p align="center">
  <img src="docs/images/title-screen.png" alt="Title screen with the 1 Player + CPU mode selected" width="400">
  <img src="docs/images/battle-cpu-partner.png" alt="Stage 1 in 1 Player + CPU mode, the CPU Partner in green" width="400">
</p>

## Installation

Download the latest build from the [Releases page](https://github.com/StefanBS/battle-city-clone/releases/latest). Each release also has a `SHA256SUMS` file to check your download against.

### Windows

1. Download `BattleCitySetup-<version>.exe`.
2. Run it. It installs for your user only, so it doesn't need administrator rights.
3. The installer isn't code-signed, so Windows SmartScreen may warn you. Choose **More info**, then **Run anyway**.
4. Start **Battle City** from the Start menu.

To check the download in PowerShell, compare the hash with the one in `SHA256SUMS`:

```powershell
Get-FileHash .\BattleCitySetup-<version>.exe -Algorithm SHA256
```

### Linux

The game ships as a Flatpak bundle. It needs [Flatpak](https://flatpak.org/setup/) and the Flathub remote, which provides the runtime it's built on:

```bash
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user BattleCity-v<version>.flatpak
flatpak run com.battlecity.BattleCity
```

The game also appears in your desktop's application menu. To remove it, run `flatpak uninstall --user com.battlecity.BattleCity`.

### macOS

There's no packaged macOS build yet, so run the game from source. [uv](https://docs.astral.sh/uv/) downloads the right Python version for you:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/StefanBS/battle-city-clone.git
cd battle-city-clone
uv sync
uv run python main.py
```

The same steps work on Linux. On Windows, install uv with `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` and then run the same `git clone`, `uv sync` and `uv run` commands.

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

## Documentation

- [CONTEXT.md](CONTEXT.md): the domain language used in code, tests and docs
- [docs/cpu-partner.md](docs/cpu-partner.md): how the CPU Partner picks and pursues its Goals
- [docs/adr/](docs/adr/): architecture decisions
  - [0001](docs/adr/0001-cpu-partner-as-player-input.md) CPU Partner is a PlayerInput, not a tank subclass
  - [0002](docs/adr/0002-one-stepping-path-for-all-tanks.md) Every tank goes through one stepping path
  - [0003](docs/adr/0003-collision-response-returns-outcomes.md) Collision response returns outcomes
  - [0004](docs/adr/0004-a-battle-owns-one-stage.md) A Battle owns one Stage
  - [0005](docs/adr/0005-dodge-is-a-reflex-not-a-goal.md) Dodge is a reflex, not a Goal
  - [0006](docs/adr/0006-spawning-and-the-enemies-on-the-battlefield-stay-separate.md) Spawning and the Enemies on the battlefield stay separate
  - [0007](docs/adr/0007-the-screen-flow-never-holds-a-battle.md) The Screen Flow never holds a Battle
  - [0008](docs/adr/0008-four-layered-packages-with-the-world-view-between-battle-and-cpu-partner.md) Four layered packages, with the World View between the Battle and the CPU Partner

## Development Setup

Requires [uv](https://docs.astral.sh/uv/), which downloads Python 3.13+ for you.

```bash
uv sync --extra dev
uv run python main.py
```

## Testing

```bash
uv run pytest
uv run pytest --cov=src
```

## Linting, Formatting and Type Checking

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src
uv run lint-imports
```

The pre-commit hooks and CI run all four. `lint-imports` checks the package layers in `pyproject.toml`: `shell` → `battle` and `cpu_partner` → `world_view` → `core` (see ADR 0008).

## Building

To build a standalone executable:

```bash
uv sync --extra dev --extra build
uv run pyinstaller battle-city.spec
```

Release builds are made by CI when a `v*` tag is pushed: a Windows installer (PyInstaller + Inno Setup, `installer/windows/`) and a Linux Flatpak (`installer/linux/`).
