from enum import Enum


class GameState(Enum):
    """Possible states of the game."""

    TITLE_SCREEN = 0
    RUNNING = 1
    GAME_OVER = 2
    VICTORY = 3
    EXIT = 4
