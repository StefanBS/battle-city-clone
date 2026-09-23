"""The CPU Partner's human-like timing: when it decides, reacts and shoots."""

import random
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from src.managers.pathfinding import Cell


class GoalKind(Enum):
    """What the CPU Partner is trying to do, highest priority first."""

    DEFEND = auto()
    GRAB_POWER_UP = auto()
    HUNT = auto()
    AMBUSH = auto()


@dataclass(frozen=True)
class Goal:
    """A Goal and what it targets."""

    kind: GoalKind
    # The target Enemy's id, or the target Power-Up's or Enemy Spawn Point's
    # cell (neither ever moves).
    target: int | Cell


class GoalTiming:
    """When the CPU Partner changes the Goal it acts on.

    It decides every ``decision_frames``, or at once when it has no Goal or
    its Goal's target is gone. It keeps its Goal until another has been
    preferred for ``stickiness_frames``, unless its Goal's target is gone;
    Ambush, just waiting, gives way at once. Stickiness counts the time it
    has preferred any other Goal, even if that Goal changes meanwhile:
    counting only one particular Goal would never let it switch while its
    preference keeps changing (e.g. two Base Threats taking turns as the one
    nearest the Base). Once it decides on a new Goal, it keeps acting on the
    old one for the Reaction Delay (``reaction_frames``).
    """

    def __init__(
        self, decision_frames: int, reaction_frames: int, stickiness_frames: int
    ) -> None:
        self._decision_frames = decision_frames
        self._reaction_frames = reaction_frames
        self._stickiness_frames = stickiness_frames
        # The Goal it has decided on, and the one it is acting on: the
        # previous Goal until the Reaction Delay has passed.
        self._decided: Goal | None = None
        self._acting: Goal | None = None
        self._frames_to_react: int = 0
        self._frames_to_decision: int = 0
        # Frames it has preferred another Goal to its current one.
        self._frames_preferring_other: int = 0

    @property
    def decided(self) -> Goal | None:
        """The Goal it has decided on, which it may not be acting on yet."""
        return self._decided

    def update(
        self,
        prefer: Callable[[], Goal | None],
        exists: Callable[[Goal], bool],
    ) -> Goal | None:
        """Advance one frame and return the Goal to act on.

        ``prefer`` gives the Goal it would pick right now, and is only called
        when it decides. ``exists`` tells whether a Goal's target is still
        there.
        """
        self._frames_to_decision -= 1
        if (
            self._frames_to_decision <= 0
            or self._decided is None
            or not exists(self._decided)
        ):
            self._frames_to_decision = self._decision_frames
            chosen = self._decide(prefer, exists)
            if chosen != self._decided:
                self._decided = chosen
                self._frames_to_react = self._reaction_frames
        if self._frames_to_react > 0:
            self._frames_to_react -= 1
        else:
            self._acting = self._decided
        return self._acting

    def abandon(self) -> None:
        """Give up the Goal it is acting on (its target can't be reached).

        A newer Goal it has decided on but not yet reacted to is kept.
        """
        if self._decided == self._acting:
            self._decided = None
        self._acting = None

    def _decide(
        self,
        prefer: Callable[[], Goal | None],
        exists: Callable[[Goal], bool],
    ) -> Goal | None:
        """The Goal to pursue from now on."""
        preferred = prefer()
        if (
            self._decided is None
            or self._decided.kind is GoalKind.AMBUSH
            or not exists(self._decided)
            or preferred == self._decided
        ):
            self._frames_preferring_other = 0
            return preferred
        self._frames_preferring_other += self._decision_frames
        if self._frames_preferring_other >= self._stickiness_frames:
            self._frames_preferring_other = 0
            return preferred
        return self._decided


class Hesitation:
    """Now and then holds back a shot the CPU Partner has just lined up.

    Each time it starts aiming, with probability ``chance`` it holds its fire
    for ``frames``.
    """

    def __init__(self, chance: float, frames: int) -> None:
        self._chance = chance
        self._frames = frames
        self._was_aiming: bool = False
        self._frames_to_hesitate: int = 0

    def filter(self, aiming: bool) -> bool:
        """Advance one frame: whether to shoot, given whether it's aiming."""
        if aiming and not self._was_aiming:
            if random.random() < self._chance:
                self._frames_to_hesitate = self._frames
        self._was_aiming = aiming
        if self._frames_to_hesitate > 0:
            self._frames_to_hesitate -= 1
            return False
        return aiming
