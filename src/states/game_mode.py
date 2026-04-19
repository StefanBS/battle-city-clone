"""Game mode: selected at the title screen, fixed for a run."""

from enum import Enum, auto


class GameMode(Enum):
    ONE_PLAYER = auto()
    TWO_PLAYER = auto()
    ONE_PLAYER_AI = auto()
