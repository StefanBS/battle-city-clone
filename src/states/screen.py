from enum import Enum


class Screen(Enum):
    """The screens of the Screen Flow."""

    TITLE_SCREEN = 0
    RUNNING = 1
    VICTORY = 3
    EXIT = 4
    STAGE_CURTAIN_CLOSE = 5
    STAGE_CURTAIN_OPEN = 6
    GAME_OVER_ANIMATION = 7
    GAME_COMPLETE = 8
    PAUSED = 9
    OPTIONS_MENU = 10
