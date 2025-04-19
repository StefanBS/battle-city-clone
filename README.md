# Battle City Clone

A Python and Pygame implementation of the classic NES game Battle City.

## Project Structure

```
battle-city-clone/
├── src/                    # Source code
│   ├── core/              # Core game mechanics and systems
│   │   ├── __init__.py
│   │   ├── game_object.py # Base GameObject class
│   │   ├── tank.py        # Tank base class and implementations
│   │   ├── bullet.py      # Bullet implementation
│   │   ├── tile.py        # Tile types and implementation
│   │   ├── map.py         # Map management
│   │   └── collision.py   # Collision detection
│   │
│   ├── managers/          # Game managers
│   │   ├── __init__.py
│   │   ├── game_manager.py
│   │   ├── input_handler.py
│   │   ├── renderer.py
│   │   ├── sound_manager.py
│   │   ├── ui_manager.py
│   │   └── powerup_manager.py
│   │
│   ├── states/            # Game states
│   │   ├── __init__.py
│   │   ├── base_state.py
│   │   ├── menu_state.py
│   │   ├── play_state.py
│   │   ├── pause_state.py
│   │   └── game_over_state.py
│   │
│   ├── utils/             # Utility functions and helpers
│   │   ├── __init__.py
│   │   ├── constants.py   # Game constants
│   │   ├── helpers.py     # Helper functions
│   │   └── config.py      # Configuration settings
│   │
│   └── main.py            # Entry point
│
├── assets/                # Game assets
│   ├── sprites/          # Sprite sheets and images
│   ├── sounds/           # Sound effects and music
│   └── maps/             # Level map files
│
├── tests/                # Test files
│   ├── __init__.py
│   ├── test_core/
│   ├── test_managers/
│   └── test_states/
│
├── docs/                 # Documentation
│   ├── core-game-mechanics.md
│   └── technical-architecture.md
│
├── pyproject.toml        # Project configuration and dependencies
└── README.md            # This file
```

## Setup Instructions

1. Install `uv` (if not already installed):
```bash
# Using curl
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

2. Create and activate a virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
uv pip install -e .
```

4. Run the game:
```bash
python src/main.py
```

## Development Guidelines

- Follow PEP 8 style guide
- Use type hints for better code documentation
- Write docstrings for all public functions and classes
- Keep functions and classes focused on a single responsibility
- Write tests for new features
- Update documentation when making significant changes
