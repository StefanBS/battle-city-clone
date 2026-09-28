"""Which Enemies the CPU Partner has given up on, and from which sides."""

from dataclasses import dataclass, field

from src.managers.pathfinding import Cell
from src.managers.world_view import EnemyView, PlayerView, WorldView
from src.utils.constants import Direction


@dataclass(frozen=True)
class RefusedShot:
    """A shot it held this frame: lined up on ``target`` from ``own``, facing it."""

    own: PlayerView
    target: EnemyView
    facing: Direction


@dataclass
class _GivenUp:
    """What it gave up on an Enemy while the Enemy stands on ``cell``."""

    cell: Cell
    sides: set[Direction] = field(default_factory=set)
    cut_off: bool = False


class CutOff:
    """Gives up sides of Enemies it keeps refusing to shoot, then the Enemies.

    Holding a Refused Shot on the same Enemy for ``refused_shot_frames`` in a
    row gives up the side it was held on; with no Firing Position left on the
    other sides, the Enemy is Cut Off. An Enemy it finds no path to a Firing
    Position for is Cut Off too (:meth:`cut_off`). Both are forgotten once the
    Enemy moves off the cell it stood on.

    Each frame the CPU Partner calls :meth:`forget_moved` before it picks its
    Goal and :meth:`refused` after it acts. On a frame it Dodges it calls
    neither, so the count and the forgetting pause (ADR 0005).
    """

    def __init__(self, refused_shot_frames: int) -> None:
        self._refused_shot_frames = refused_shot_frames
        self._refused_count: int = 0
        self._refusing: int | None = None
        self._given_up: dict[int, _GivenUp] = {}

    def forget_moved(self, world: WorldView) -> None:
        """Forget the Enemies that left the battlefield or moved off their cell."""
        cells = {e.enemy_id: world.cell_of(e) for e in world.enemies}
        self._given_up = {
            enemy_id: given_up
            for enemy_id, given_up in self._given_up.items()
            if cells.get(enemy_id) == given_up.cell
        }

    def refused(self, world: WorldView, shot: RefusedShot | None) -> bool:
        """Count one frame's Refused Shot, or ``None`` if it refused no shot.

        Returns whether it left the Enemy Cut Off.
        """
        refusing = None if shot is None else shot.target.enemy_id
        if refusing != self._refusing:
            self._refused_count = 0
        self._refusing = refusing
        if shot is None:
            return False
        self._refused_count += 1
        if self._refused_count < self._refused_shot_frames:
            return False
        self._refused_count = 0
        target = shot.target
        self._on(world, target).sides.add(shot.facing.opposite)
        if world.firing_positions(target, shot.own.size, self.open_sides(target)):
            return False
        self.cut_off(world, target)
        return True

    def cut_off(self, world: WorldView, enemy: EnemyView) -> None:
        """Leave ``enemy`` Cut Off: it found no Firing Position it can reach."""
        self._on(world, enemy).cut_off = True

    def open_sides(self, enemy: EnemyView) -> list[Direction]:
        """Sides of ``enemy`` it hasn't given up firing from."""
        given_up = self._given_up.get(enemy.enemy_id)
        sides = set() if given_up is None else given_up.sides
        return [side for side in Direction if side not in sides]

    def is_cut_off(self, enemy: EnemyView) -> bool:
        """Whether ``enemy`` is Cut Off: left out of its Goals until it moves."""
        given_up = self._given_up.get(enemy.enemy_id)
        return given_up is not None and given_up.cut_off

    def _on(self, world: WorldView, enemy: EnemyView) -> _GivenUp:
        """What it gave up on ``enemy``, kept while it stands where it is now."""
        return self._given_up.setdefault(enemy.enemy_id, _GivenUp(world.cell_of(enemy)))
