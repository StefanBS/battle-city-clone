# Battle City Clone

A Python and Pygame implementation of the classic NES game Battle City.

## Project Structure

```
battle-city-clone/
├── src/                    # Source code
│   ├── __init__.py
│   ├── core/              # Core game mechanics and systems
│   │   ├── __init__.py
│   │   ├── game_object.py # Base GameObject class
│   │   ├── tank.py        # Tank base class
│   │   ├── player_tank.py # Player-controlled tank
│   │   ├── enemy_tank.py  # AI-controlled tank
│   │   ├── bullet.py      # Bullet implementation
│   │   ├── tile.py        # Tile types and implementation
│   │   └── map.py         # Map management
│   │
│   ├── managers/          # Game managers
│   │   ├── game_manager.py
│   │   └── input_handler.py
│   │
│   ├── states/            # Game states
│   │   └── game_state.py  # Game state enum
│   │
│   ├── utils/             # Utility functions and helpers
│   │   └── constants.py   # Game constants
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
│   ├── core/            # Core component tests
│   ├── managers/        # Manager tests
│   ├── integration/     # Integration tests
│   └── utils/          # Utility tests
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
python main.py
```

## Testing

The project uses pytest for testing. To run the tests:

```bash
# Run all tests
python -m pytest

# Run tests with coverage report
python -m pytest --cov=src

# Run specific test file
python -m pytest tests/managers/test_game_manager.py

# Run tests matching a pattern
python -m pytest -k "test_bullet"
```

Tests are organized into:
- Unit tests: Test individual components in isolation
- Integration tests: Test interactions between components
