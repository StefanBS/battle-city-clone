"""How the CPU Partner gets unstuck: which tanks it routes around."""

from collections.abc import Callable, Mapping
from typing import Literal

from src.managers.pathfinding import Cell

# Identifies a tank in the World View: Enemy and Player ids can overlap.
TankKey = tuple[Literal["enemy", "player"], int]


class Steering:
    """Spots when the CPU Partner is stuck and picks the tanks to route around.

    Once it has tried to move without getting anywhere for
    ``stuck_frames``, the tanks right ahead of it are routed around until
    they move off the cells where they stood.
    """

    def __init__(self, stuck_frames: int) -> None:
        self._stuck_frames = stuck_frames
        self._last_position: tuple[float, float] | None = None
        self._frames_stuck: int = 0
        # The direction it keeps trying to move in while stuck.
        self._pushing: tuple[int, int] = (0, 0)
        # Tanks to route around, with the cells they blocked it from.
        self._detour_around: dict[TankKey, set[Cell]] = {}

    def track(
        self, position: tuple[float, float] | None, movement: tuple[int, int]
    ) -> None:
        """Advance one frame: it now stands at ``position`` after ``movement``.

        ``movement`` is the direction it tried to move in last frame;
        ``position`` is ``None`` while it isn't on the battlefield.
        """
        if movement != (0, 0) and position == self._last_position:
            self._frames_stuck += 1
            self._pushing = movement
        else:
            self._frames_stuck = 0
        self._last_position = position

    def detour(
        self,
        tanks: Mapping[TankKey, set[Cell]],
        cells_ahead: Callable[[tuple[int, int]], set[Cell]],
        target: TankKey | None = None,
    ) -> dict[TankKey, set[Cell]]:
        """Update which tanks to route around and return them with their cells.

        ``tanks`` maps every other tank to the cells it covers now.
        ``cells_ahead`` gives the cells it would cover one cell further in a
        direction. Its ``target`` is never routed around.
        """
        if self._frames_stuck >= self._stuck_frames:
            self._frames_stuck = 0
            ahead = cells_ahead(self._pushing)
            self._detour_around = {
                key: cells
                for key, cells in tanks.items()
                if key != target and cells & ahead
            }
        still_there = {
            key: cells
            for key, cells in tanks.items()
            if key in self._detour_around and cells & self._detour_around[key]
        }
        self._detour_around = {key: self._detour_around[key] for key in still_there}
        return still_there
