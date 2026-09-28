from enum import Enum, auto


class BattleResult(Enum):
    """How a Battle ended."""

    GAME_OVER = auto()
    VICTORY = auto()
