"""Dodge: the CPU Partner's reflex against Incoming Shots (ADR 0005).

Only :class:`Dodge` is public: it decides the whole Dodge, and guards the
Goal's step against shots.
"""

import math
import random
from dataclasses import dataclass, replace

from src.managers.footprint import Footprint, Placed, moved, swept_cells
from src.managers.world_view import BulletView, PlayerView, WorldView
from src.utils.constants import (
    CPU_PARTNER_DODGE_HORIZON,
    FPS,
    Direction,
    OwnerType,
)


@dataclass(frozen=True)
class _IncomingShot:
    """An Enemy bullet that will hit ``own`` in ``time_to_hit`` seconds."""

    bullet: BulletView
    time_to_hit: float

    @property
    def horizontal(self) -> bool:
        """Whether the bullet flies along a row (else down a column)."""
        return self.bullet.direction in (Direction.LEFT, Direction.RIGHT)

    @property
    def lane(self) -> tuple[float, float]:
        """The span the bullet sweeps across its direction of travel (px)."""
        start = self.bullet.y if self.horizontal else self.bullet.x
        return start, start + self.bullet.size


def _incoming_shots(
    world: WorldView, own: PlayerView, horizon: float
) -> list[_IncomingShot]:
    """The Incoming Shots at ``own`` that hit within ``horizon`` s, soonest first.

    An Enemy bullet is one when ``own`` lies in its lane ahead of it, with no
    solid tile and no other Player in between. Enemy bullets fly through
    Enemies, so they don't shield ``own``.
    """
    shots = []
    for bullet in world.bullets:
        if bullet.owner_type is not OwnerType.ENEMY:
            continue
        line = world.line_of_fire(bullet, bullet.direction)
        distance = line.distance_to(own)
        if distance is None or distance > line.stopped_at:
            continue
        if any(
            (at := line.distance_to(p)) is not None and at < distance
            for p in world.players
            if p.player_id != own.player_id
        ):
            continue
        # The distance runs from the bullet's center; its front is half ahead.
        time_to_hit = max(distance - bullet.size / 2, 0.0) / bullet.speed
        if time_to_hit <= horizon:
            shots.append(_IncomingShot(bullet, time_to_hit))
    return sorted(shots, key=lambda shot: shot.time_to_hit)


def _shields_base(world: WorldView, shot: _IncomingShot) -> bool:
    """Whether ``shot`` would fly on to hit the Base itself, were ``own`` gone.

    Only the Base counts: losing a Base Wall brick is worth less than a life.
    """
    bullet = shot.bullet
    line = world.line_of_fire(bullet, bullet.direction)
    if not line.endangers_base:
        return False
    size = world.tile_size
    return any(
        (at := line.distance_to(Footprint(x * size, y * size, size))) is not None
        and at <= line.stopped_at
        for x, y in world.base_cells
    )


def _can_shoot_down(world: WorldView, own: PlayerView, shot: _IncomingShot) -> bool:
    """Whether a bullet ``own`` fires facing ``shot`` would meet it head-on.

    Its bullet leaves from its middle, so a shot that would only clip the
    tank's edge flies past it. No Line of Fire safety check is needed: the
    two bullets cancel out before its own could fly on.
    """
    if not own.can_fire:
        return False
    own_lane = world.line_of_fire(own, shot.bullet.direction.opposite).lane
    shot_lane = shot.lane
    return shot_lane[0] < own_lane[1] and own_lane[0] < shot_lane[1]


def _sidestep(
    world: WorldView, own: PlayerView, shot: _IncomingShot, horizon: float
) -> Direction | None:
    """The way to step out of ``shot``'s lane in time, the sooner way first.

    A way is ruled out when a tile or another tank is in it, or when it
    brings any other shot sooner: one not coming at ``own`` yet, or one
    already coming at it along the way it would step. ``None`` when no way is
    left.
    """
    across = own.y if shot.horizontal else own.x
    lane = shot.lane
    before, after = (
        (Direction.UP, Direction.DOWN)
        if shot.horizontal
        else (Direction.LEFT, Direction.RIGHT)
    )
    ways = sorted(
        [
            (across + own.size - lane[0], before),
            (lane[1] - across, after),
        ],
        key=lambda way: way[0],
    )
    for distance, direction in ways:
        if distance / own.speed >= shot.time_to_hit:
            continue
        if not _is_way_clear(world, own, direction, distance):
            continue
        if _brings_a_shot_sooner(world, own, direction, distance, horizon):
            continue
        return direction
    return None


def _brings_a_shot_sooner(
    world: WorldView,
    own: PlayerView,
    direction: Direction,
    distance: float,
    horizon: float,
) -> bool:
    """Whether moving ``distance`` px toward ``direction`` brings a shot sooner.

    That is a shot not coming at ``own`` yet, or one already coming at it
    along that way.
    """
    due_now = {
        other.bullet: other.time_to_hit
        for other in _incoming_shots(world, own, horizon)
    }
    after_step = moved(own, direction.delta, distance)
    stepped = replace(
        world,
        players=tuple(
            after_step if p.player_id == own.player_id else p for p in world.players
        ),
    )
    return any(
        other.time_to_hit < due_now.get(other.bullet, math.inf)
        for other in _incoming_shots(stepped, after_step, horizon)
    )


def _is_way_clear(
    world: WorldView, own: PlayerView, direction: Direction, distance: float
) -> bool:
    """Whether ``own`` can drive ``distance`` px toward ``direction`` unhindered."""
    cells = swept_cells(own, direction.delta, distance, world.tile_size)
    if any(world.blocks_tanks(c) for c in cells):
        return False
    end = moved(own, direction.delta, distance)
    left, top = min(own.x, end.x), min(own.y, end.y)
    right, bottom = max(own.x, end.x) + own.size, max(own.y, end.y) + own.size
    tanks: list[Placed] = [
        *world.enemies,
        *(p for p in world.players if p.player_id != own.player_id),
    ]
    return not any(
        t.x < right and left < t.x + t.size and t.y < bottom and top < t.y + t.size
        for t in tanks
    )


class _Awareness:
    """Which Incoming Shots the CPU Partner has noticed.

    It notices a shot only once the shot has been coming at it for
    ``reaction_frames``, and never notices one it misses: a chance rolled
    once per bullet, the first time the bullet comes at it. A shot it has
    fired back at is left to its own bullet, and no longer noticed.
    """

    def __init__(self, reaction_frames: int, miss_chance: float) -> None:
        self._reaction_frames = reaction_frames
        self._miss_chance = miss_chance
        # Frames each bullet has come at it, kept while the bullet flies.
        self._seen: dict[int, int] = {}
        self._missed: set[int] = set()
        self._fired_back_at: set[int] = set()

    def noticed(
        self, world: WorldView, shots: list[_IncomingShot]
    ) -> list[_IncomingShot]:
        """The ``shots`` it has noticed, in the same order."""
        flying = {b.bullet_id for b in world.bullets}
        self._seen = {i: n for i, n in self._seen.items() if i in flying}
        self._missed &= flying
        self._fired_back_at &= flying
        result = []
        for shot in shots:
            bullet_id = shot.bullet.bullet_id
            if bullet_id not in self._seen and random.random() < self._miss_chance:
                self._missed.add(bullet_id)
            self._seen[bullet_id] = self._seen.get(bullet_id, 0) + 1
            if (
                bullet_id not in self._missed | self._fired_back_at
                and self._seen[bullet_id] > self._reaction_frames
            ):
                result.append(shot)
        return result

    def fired_back_at(self, shot: _IncomingShot) -> None:
        """Leave ``shot`` to the bullet just fired back at it."""
        self._fired_back_at.add(shot.bullet.bullet_id)


@dataclass(frozen=True)
class DodgeMove:
    """What a Dodge does this frame, in place of what the Goal would do."""

    movement: tuple[int, int]
    shoot: bool


class Dodge:
    """The CPU Partner's Dodge: its reflex against Incoming Shots (ADR 0005).

    It notices a shot only ``reaction_frames`` after the shot starts coming
    at it, misses a bullet altogether with ``miss_chance``, and looks
    ``horizon`` seconds ahead. It knows nothing of the Goal: the CPU Partner
    asks it whether to Dodge this frame, and whether the Goal's step is safe.
    """

    def __init__(
        self,
        reaction_frames: int,
        miss_chance: float,
        horizon: float = CPU_PARTNER_DODGE_HORIZON,
    ) -> None:
        self._horizon = horizon
        self._awareness = _Awareness(reaction_frames, miss_chance)

    def react(self, world: WorldView) -> DodgeMove | None:
        """This frame's Dodge against the soonest noticed shot, if it Dodges.

        It shoots the shot down if it faces it, else sidesteps, else turns to
        fire back at it. It never steps aside from a shot that would fly on
        into the Base: it takes the hit instead. ``None`` when there is no
        shot to Dodge, or when nothing would help; never while shielded or
        frozen.
        """
        own = world.own_player
        if own is None or own.shielded or own.frozen:
            return None
        shots = self._awareness.noticed(
            world, _incoming_shots(world, own, self._horizon)
        )
        if not shots:
            return None
        shot = shots[0]
        toward_shot = shot.bullet.direction.opposite
        able_to_shoot_down = _can_shoot_down(world, own, shot)
        if own.direction == toward_shot and able_to_shoot_down:
            return self._fire_back_at(shot, (0, 0))
        if _shields_base(world, shot):
            if able_to_shoot_down:
                return self._fire_back_at(shot, toward_shot.delta)
            return DodgeMove((0, 0), False)
        way = _sidestep(world, own, shot, self._horizon)
        if way is not None:
            return DodgeMove(way.delta, False)
        if able_to_shoot_down:
            return self._fire_back_at(shot, toward_shot.delta)
        return None

    def is_step_safe(self, world: WorldView, movement: tuple[int, int]) -> bool:
        """Whether the Goal may take one step toward ``movement``.

        A step is unsafe when it brings a shot sooner, so the Goal doesn't
        steer the CPU Partner straight back into the lane of a shot it has
        just sidestepped. Unlike :meth:`react`, it guards against every shot,
        noticed or not.
        """
        own = world.own_player
        if own is None or own.shielded or movement == (0, 0):
            return True
        direction = next(d for d in Direction if d.delta == movement)
        return not _brings_a_shot_sooner(
            world, own, direction, own.speed / FPS, self._horizon
        )

    def _fire_back_at(
        self, shot: _IncomingShot, movement: tuple[int, int]
    ) -> DodgeMove:
        """Fire at ``shot`` and leave it to that bullet from now on."""
        self._awareness.fired_back_at(shot)
        return DodgeMove(movement, True)
