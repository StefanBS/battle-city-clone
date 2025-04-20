from enum import Enum


class GameState(Enum):
    """Possible states of the game."""

    RUNNING = 0
    GAME_OVER = 1
    VICTORY = 2
