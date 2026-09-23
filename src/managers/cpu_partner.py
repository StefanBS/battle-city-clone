"""CPU Partner: a PlayerInput that drives P2 from the World View (ADR 0001)."""

import itertools
import math
from collections.abc import Collection
from dataclasses import replace

import pygame

from src.managers.dodge import (
    Awareness,
    can_shoot_down,
    incoming_shots,
    shields_base,
    sidestep,
)
from src.managers.enemy_memory import EnemyMemory
from src.managers.goal_timing import Goal, GoalKind, GoalTiming, Hesitation
from src.managers.pathfinding import Cell, NavGrid, find_path
from src.managers.refused_shots import RefusedShots
from src.managers.steering import Steering, TankKey
from src.managers.world_view import (
    EnemyView,
    Footprint,
    PlayerView,
    PowerUpView,
    WorldView,
    center,
)
from src.utils.constants import (
    CPU_PARTNER_ALIGN_TOLERANCE,
    CPU_PARTNER_AMBUSH_DISTANCE,
    CPU_PARTNER_DECISION_INTERVAL,
    CPU_PARTNER_DODGE_HORIZON,
    CPU_PARTNER_DODGE_MISS_CHANCE,
    CPU_PARTNER_DODGE_REACTION_TIME,
    CPU_PARTNER_GOAL_STICKINESS,
    CPU_PARTNER_HESITATION_CHANCE,
    CPU_PARTNER_HESITATION_TIME,
    CPU_PARTNER_POWER_UP_RANGE,
    CPU_PARTNER_REACTION_DELAY,
    CPU_PARTNER_REFUSED_SHOT_TIME,
    CPU_PARTNER_STUCK_TIME,
    FPS,
    TANK_ALIGN_THRESHOLD,
    Direction,
)


def _along_step(direction: Direction, horizontal: bool) -> int:
    """``direction``'s step along the lane axis: -1, 0 or 1."""
    return direction.delta[0] if horizontal else direction.delta[1]


def is_line_of_fire_safe(
    world: WorldView, own: PlayerView, target: EnemyView | None
) -> bool:
    """Whether ``own`` may fire at ``target`` along its current facing.

    Unsafe when the bullet could hit the Base or a Base Wall cell before a
    solid tile stops it (even beyond the target, since a miss carries on), or
    when a live Human Player stands in the Line of Fire before both the target
    and that solid tile. With no target (shooting a brick out of the way),
    only the solid tile stops the bullet.
    """
    line = world.line_of_fire(own, own.direction)
    if line.endangers_base:
        return False
    target_at = None if target is None else line.distance_to(target)
    nearest_stop = min(line.stopped_at, math.inf if target_at is None else target_at)
    for player in world.players:
        if player.player_id == own.player_id:
            continue
        human_at = line.distance_to(player)
        if human_at is not None and human_at < nearest_stop:
            return False
    return True


def ambush_positions(world: WorldView, own: PlayerView, spawn_point: Cell) -> set[Cell]:
    """Firing Positions from which ``own`` can wait for Enemies at ``spawn_point``.

    Those at least the ambush distance from it, where ``own`` wouldn't stand
    on any Enemy Spawn Point and so keep Enemies from spawning there.
    """
    size_cells = math.ceil(own.size / world.tile_size)
    spawn_cells = set().union(
        *(
            world.covered_cells(world.spawn_footprint(s))
            for s in world.enemy_spawn_points
        )
    )
    sx, sy = spawn_point
    return {
        (x, y)
        for x, y in world.firing_positions(world.spawn_footprint(spawn_point), own.size)
        if abs(x - sx) + abs(y - sy) >= CPU_PARTNER_AMBUSH_DISTANCE
        and not any(
            (x + dx, y + dy) in spawn_cells
            for dx in range(size_cells)
            for dy in range(size_cells)
        )
    }


def _touching_cells(
    world: WorldView, own: PlayerView, power_up: PowerUpView
) -> set[Cell]:
    """Cells from which ``own``'s footprint overlaps ``power_up``, collecting it."""
    size_cells = math.ceil(own.size / world.tile_size)
    return {
        (x - dx, y - dy)
        for x, y in world.covered_cells(power_up)
        for dx in range(size_cells)
        for dy in range(size_cells)
    }


def can_evade_shot(world: WorldView, own: PlayerView, target: EnemyView) -> bool:
    """Whether ``target`` could slip out of ``own``'s Line of Fire in time.

    Only an Enemy hemmed in by walls on both sides of the Line of Fire is
    judged: it evades if it can drive to a corridor exit wide enough for a
    tank and clear the bullet's lane before the bullet arrives. It drives the
    way it faces, or either way when it faces a wall. On open ground there
    are no exits to judge by, so the shot is taken.
    """
    if world.enemies_frozen or target.speed <= 0:
        return False
    line = world.line_of_fire(own, own.direction)
    horizontal, lane = line.horizontal, line.lane
    gap = line.distance_to(target)
    if gap is None:
        return False

    def blocked(along_cell: int, across_cell: int) -> bool:
        if horizontal:
            return world.blocks_tanks((along_cell, across_cell))
        return world.blocks_tanks((across_cell, along_cell))

    # "Along" runs with the bullet; "across" is sideways, out of the lane.
    tile_size = world.tile_size
    along, across = (target.x, target.y) if horizontal else (target.y, target.x)
    first = math.floor(across / tile_size)
    last = math.ceil((across + target.size) / tile_size) - 1
    beside_now = range(
        math.floor(along / tile_size), math.ceil((along + target.size) / tile_size)
    )
    if not all(
        any(blocked(a, side) for a in beside_now) for side in (first - 1, last + 1)
    ):
        return False

    # For each side: how far the target must drive sideways to clear the lane,
    # and the cells beside it that drive takes.
    to_clear_after = lane[1] - across
    to_clear_before = across + target.size - lane[0]
    exits = [
        (
            to_clear_after,
            range(last + 1, last + 1 + math.ceil(to_clear_after / tile_size)),
        ),
        (
            to_clear_before,
            range(first - 1, first - 1 - math.ceil(to_clear_before / tile_size), -1),
        ),
    ]
    corridor = range(first, last + 1)
    size_cells = math.ceil(target.size / tile_size)
    bullet_step = line.step
    target_step = _along_step(target.direction, horizontal)
    for step in [target_step] if target_step else [-1, 1]:
        # The bullet closes the gap more slowly while the target drives away.
        closing = own.bullet_speed - step * bullet_step * target.speed
        if closing <= 0:
            return True
        time_left = gap / closing
        start = round(along / tile_size)
        for k in itertools.count():
            cell = start + k * step
            footprint = range(cell, cell + size_cells)
            travelled = abs(cell * tile_size - along)
            if travelled / target.speed >= time_left or (
                k and any(blocked(a, c) for a in footprint for c in corridor)
            ):
                break
            for sideways, side_cells in exits:
                open_exit = not any(
                    blocked(a, c) for a in footprint for c in side_cells
                )
                if open_exit and (travelled + sideways) / target.speed < time_left:
                    return True
    return False


class CpuPartnerInput:
    """Computer-controlled input for the CPU Partner in the P2 slot.

    Reads the World View once per frame in :meth:`observe` and turns it into
    a movement direction and shoot requests, exactly like a human input. Like
    a human it is imperfect: it decides on its Goal only every
    ``decision_interval`` seconds, takes ``reaction_delay`` seconds to act on
    a new Goal or target, and sometimes (``hesitation_chance``) hesitates
    before a shot.
    """

    def __init__(
        self,
        decision_interval: float = CPU_PARTNER_DECISION_INTERVAL,
        reaction_delay: float = CPU_PARTNER_REACTION_DELAY,
        hesitation_chance: float = CPU_PARTNER_HESITATION_CHANCE,
        dodge_reaction_time: float = CPU_PARTNER_DODGE_REACTION_TIME,
        dodge_miss_chance: float = CPU_PARTNER_DODGE_MISS_CHANCE,
    ) -> None:
        self._decision_frames = max(1, round(decision_interval * FPS))
        self._reaction_frames = round(reaction_delay * FPS)
        self._hesitation_chance = hesitation_chance
        self._dodge_reaction_frames = round(dodge_reaction_time * FPS)
        self._dodge_miss_chance = dodge_miss_chance
        self.reset()

    def reset(self) -> None:
        """Start afresh (on stage start and respawn).

        All state that changes during play is set here and nowhere else, so
        nothing it has decided, learnt or planned survives a reset.
        """
        self._movement: tuple[int, int] = (0, 0)
        self._shoot_requested: bool = False
        self._goal_timing = GoalTiming(
            self._decision_frames,
            self._reaction_frames,
            round(CPU_PARTNER_GOAL_STICKINESS * FPS),
        )
        self._hesitation = Hesitation(
            self._hesitation_chance, round(CPU_PARTNER_HESITATION_TIME * FPS)
        )
        # Enemies that are Cut Off, left out of its Goals until they move.
        self._cut_off: EnemyMemory[None] = EnemyMemory()
        # Sides of Enemies it gave up firing from, avoided until they move.
        self._given_up_sides: EnemyMemory[set[Direction]] = EnemyMemory()
        self._refused_shots = RefusedShots(round(CPU_PARTNER_REFUSED_SHOT_TIME * FPS))
        self._steering = Steering(round(CPU_PARTNER_STUCK_TIME * FPS))
        self._awareness = Awareness(
            self._dodge_reaction_frames, self._dodge_miss_chance
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        """The CPU Partner ignores pygame events."""

    def observe(self, world: WorldView) -> None:
        """Decide this frame's movement and shooting from the World View."""
        own = world.own_player
        self._steering.track(None if own is None else (own.x, own.y), self._movement)
        self._movement = (0, 0)
        self._shoot_requested = False
        if self._dodge(world):
            return
        self._act(world)
        self._shoot_requested = self._hesitation.filter(self._shoot_requested)

    def _dodge(self, world: WorldView) -> bool:
        """Dodge the soonest Incoming Shot, if any; whether it dodged.

        It shoots the shot down if it faces it, else sidesteps, else turns to
        fire back at it. It never steps aside from a shot that would fly on
        into the Base: it takes the hit instead. A Dodge overrides this
        frame's movement and shooting but leaves the Goal and everything
        that times it untouched (ADR 0005).
        """
        own = world.own_player
        if own is None or own.shielded or own.frozen:
            return False
        shots = self._awareness.noticed(
            world, incoming_shots(world, own, CPU_PARTNER_DODGE_HORIZON)
        )
        if not shots:
            return False
        shot = shots[0]
        facing_it = shot.bullet.direction.opposite
        shoot_down = can_shoot_down(world, own, shot)
        if own.direction == facing_it and shoot_down:
            self._shoot_requested = True
            return True
        guarding_base = shields_base(world, shot)
        way = (
            None
            if guarding_base
            else sidestep(world, own, shot, CPU_PARTNER_DODGE_HORIZON)
        )
        if way is not None:
            self._movement = way.delta
        elif shoot_down:
            self._movement = facing_it.delta
            self._shoot_requested = True
        return way is not None or shoot_down or guarding_base

    def _act(self, world: WorldView) -> None:
        """Set this frame's movement and shoot request for its Goal.

        Lined up on an Enemy but kept from shooting it safely for the refused
        shot time, it gives up on that side of the Enemy and moves to a Firing
        Position on another. With none left on the other sides, the Enemy is
        Cut Off.
        """
        self._refused_shots.start_frame()
        own = world.own_player
        if own is None:
            return
        target = self._update_goal(world, own)
        if target is None:
            return
        if isinstance(target, PowerUpView):
            self._follow_path(world, own, _touching_cells(world, own, target), None)
            return
        if isinstance(target, Footprint):
            self._ambush(world, own, target)
            return
        ox, oy = center(own)
        ex, ey = center(target)
        dx, dy = ex - ox, ey - oy
        vertical = Direction.DOWN if dy > 0 else Direction.UP
        horizontal = Direction.RIGHT if dx > 0 else Direction.LEFT
        facing = None
        if abs(dx) <= CPU_PARTNER_ALIGN_TOLERANCE:
            facing = vertical
        elif abs(dy) <= CPU_PARTNER_ALIGN_TOLERANCE:
            facing = horizontal
        sides = self._open_sides(target)
        if (
            facing is None
            or facing.opposite not in sides
            or not world.line_of_fire(own, facing).is_from_firing_position(target)
        ):
            positions = world.firing_positions(target, own.size, sides)
            self._follow_path(world, own, positions, target)
            return
        if own.direction != facing:
            self._movement = facing.delta
            return
        self._shoot_requested = is_line_of_fire_safe(
            world, own, target
        ) and not can_evade_shot(world, own, target)
        if not self._shoot_requested and self._refused_shots.refuse(target.enemy_id):
            given_up = set(Direction) - set(sides) | {facing.opposite}
            self._given_up_sides.remember(
                target.enemy_id, world.cell_of(target), given_up
            )
            if not world.firing_positions(target, own.size, self._open_sides(target)):
                self._give_up_on(world, target)

    def _open_sides(self, enemy: EnemyView) -> list[Direction]:
        """Sides of ``enemy`` it hasn't given up firing from."""
        given_up = self._given_up_sides.get(enemy.enemy_id) or set()
        return [side for side in Direction if side not in given_up]

    def _ambush(self, world: WorldView, own: PlayerView, spawn: Footprint) -> None:
        """Go to a Firing Position on ``spawn`` and wait there, facing it."""
        spawn_point = world.cell_of(spawn)
        positions = ambush_positions(world, own, spawn_point)
        cx, cy = world.cell_of(own)
        if (cx, cy) not in positions:
            self._follow_path(world, own, positions, None)
            return
        sx, sy = spawn_point
        if cx == sx:
            facing = Direction.DOWN if sy > cy else Direction.UP
        else:
            facing = Direction.RIGHT if sx > cx else Direction.LEFT
        if own.direction != facing:
            self._movement = facing.delta

    def _update_detour(
        self, world: WorldView, own: PlayerView, target: EnemyView | None
    ) -> tuple[set[Cell], set[Cell]]:
        """Update which tanks to route around and return their cells.

        Once stuck, it routes around the tanks right ahead of it: Enemies
        other than the ``target``, and the Human Player, to give way rather
        than push. Returns the cells of every tank to route around, and of the
        Players among them.
        """
        tanks: dict[TankKey, set[Cell]] = {
            ("enemy", e.enemy_id): world.covered_cells(e) for e in world.enemies
        } | {
            ("player", p.player_id): world.covered_cells(p)
            for p in world.players
            if p.player_id != own.player_id
        }

        def cells_ahead(direction: tuple[int, int]) -> set[Cell]:
            dx, dy = direction
            return world.covered_cells(
                replace(
                    own, x=own.x + dx * world.tile_size, y=own.y + dy * world.tile_size
                )
            )

        detour = self._steering.detour(
            tanks, cells_ahead, None if target is None else ("enemy", target.enemy_id)
        )
        players = [cells for key, cells in detour.items() if key[0] == "player"]
        return set().union(*detour.values()), set().union(*players)

    def _follow_path(
        self,
        world: WorldView,
        own: PlayerView,
        goals: set[Cell],
        target: EnemyView | None,
    ) -> None:
        """Take the next step on the cheapest path to one of ``goals``.

        ``target`` is the Enemy the goals are Firing Positions for, if any.
        Shoots a brick that stands in the way once facing it.
        """
        start = world.cell_of(own)
        blockers, players = self._update_detour(world, own, target)
        grid = self._nav_grid(world, own, blockers)
        path = find_path(grid, start, goals)
        if path is None:
            # No way round the Enemies in its way: push on and hope they move.
            # It never pushes the Human Player, though.
            grid = self._nav_grid(world, own, players)
            path = find_path(grid, start, goals)
        if path is None:
            if players and find_path(self._nav_grid(world, own), start, goals):
                # Only the Human Player is in the way: wait for them to move.
                return
            # Cut off from the target: pick another one next frame.
            if target is None:
                self._goal_timing.abandon()
            else:
                self._give_up_on(world, target)
            return
        if len(path) < 2:
            return
        (cx, cy), (nx, ny) = path[0], path[1]
        self._movement = (nx - cx, ny - cy)
        # Too far off the path's grid line (e.g. after sliding on ice) for the
        # steering nudge to line it up: get back on the line before moving on.
        if self._movement[0] == 0:
            off_line = cx * world.tile_size - own.x
            realign = (1 if off_line > 0 else -1, 0)
        else:
            off_line = cy * world.tile_size - own.y
            realign = (0, 1 if off_line > 0 else -1)
        if abs(off_line) > TANK_ALIGN_THRESHOLD:
            self._movement = realign
            return
        if (
            grid.has_brick((nx, ny))
            and own.direction.delta == self._movement
            and is_line_of_fire_safe(world, own, target)
        ):
            self._shoot_requested = True

    def _give_up_on(self, world: WorldView, target: EnemyView) -> None:
        """Leave ``target`` Cut Off and abandon the Goal: pick another next frame."""
        self._cut_off.remember(target.enemy_id, world.cell_of(target), None)
        self._goal_timing.abandon()

    def _update_goal(
        self, world: WorldView, own: PlayerView
    ) -> EnemyView | PowerUpView | Footprint | None:
        """Settle this frame's Goal and return what it acts on, if anything."""
        cells = {e.enemy_id: world.cell_of(e) for e in world.enemies}
        self._cut_off.expire(cells)
        self._given_up_sides.expire(cells)
        goal = self._goal_timing.update(
            lambda: self._preferred_goal(world, own),
            lambda g: self._find_target(world, g) is not None,
        )
        return None if goal is None else self._find_target(world, goal)

    @staticmethod
    def _find_target(
        world: WorldView, goal: Goal
    ) -> EnemyView | PowerUpView | Footprint | None:
        """What ``goal`` targets in ``world``, or ``None`` once it's gone."""
        if goal.kind is GoalKind.GRAB_POWER_UP:
            return next(
                (p for p in world.power_ups if world.cell_of(p) == goal.target),
                None,
            )
        if goal.kind is GoalKind.AMBUSH:
            spawn_point = goal.target
            if (
                not isinstance(spawn_point, tuple)
                or spawn_point not in world.enemy_spawn_points
            ):
                return None
            return world.spawn_footprint(spawn_point)
        return next((e for e in world.enemies if e.enemy_id == goal.target), None)

    def _preferred_goal(self, world: WorldView, own: PlayerView) -> Goal | None:
        """The Goal it would pick right now, highest priority first.

        Defend targets the Base Threat nearest the Base. Grab Power-Up targets
        the Power-Up cheapest to reach, if within range. Hunt keeps its
        current target while it lives, else takes the Enemy with the Firing
        Position cheapest to reach, if any can be reached. Cut Off Enemies are
        left out. Ambush keeps its current Enemy Spawn Point, else takes the
        one cheapest to reach.
        """
        enemies = [e for e in world.enemies if e.enemy_id not in self._cut_off]
        threats = [e for e in world.base_threats if e.enemy_id not in self._cut_off]
        if threats:
            return Goal(GoalKind.DEFEND, threats[0].enemy_id)
        power_up = self._nearest_power_up(world, own)
        if power_up is not None:
            return Goal(GoalKind.GRAB_POWER_UP, world.cell_of(power_up))
        current = self._goal_timing.decided
        if current is not None and current.kind is GoalKind.HUNT:
            if any(e.enemy_id == current.target for e in enemies):
                return current
        target = self._nearest_enemy(world, own, enemies)
        if target is not None:
            return Goal(GoalKind.HUNT, target.enemy_id)
        if current is not None and current.kind is GoalKind.AMBUSH:
            return current
        spawn_point = self._nearest_spawn_point(world, own)
        return None if spawn_point is None else Goal(GoalKind.AMBUSH, spawn_point)

    def _nearest_power_up(
        self, world: WorldView, own: PlayerView
    ) -> PowerUpView | None:
        """The Power-Up cheapest to reach by path, if within grabbing range."""
        if not world.power_ups:
            return None
        cells = {
            cell: p
            for p in reversed(world.power_ups)
            for cell in _touching_cells(world, own, p)
        }
        grid = self._nav_grid(world, own)
        path = find_path(grid, world.cell_of(own), cells)
        if path is None:
            return None
        cost = sum(grid.step_cost(cell) for cell in path[1:])
        return cells[path[-1]] if cost <= CPU_PARTNER_POWER_UP_RANGE else None

    def _nearest_enemy(
        self, world: WorldView, own: PlayerView, enemies: list[EnemyView]
    ) -> EnemyView | None:
        """The one of ``enemies`` with a Firing Position cheapest to reach by path.

        ``None`` if no Enemy has a Firing Position it can reach.
        """
        if not enemies:
            return None
        positions = {
            position: enemy
            for enemy in reversed(enemies)
            for position in world.firing_positions(
                enemy, own.size, self._open_sides(enemy)
            )
        }
        path = find_path(self._nav_grid(world, own), world.cell_of(own), positions)
        return None if path is None else positions[path[-1]]

    def _nearest_spawn_point(self, world: WorldView, own: PlayerView) -> Cell | None:
        """The Enemy Spawn Point cheapest to reach by path, if any can be."""
        path = find_path(
            self._nav_grid(world, own), world.cell_of(own), world.enemy_spawn_points
        )
        return None if path is None else path[-1]

    @staticmethod
    def _nav_grid(
        world: WorldView, own: PlayerView, avoid: Collection[Cell] = frozenset()
    ) -> NavGrid:
        return NavGrid(world, math.ceil(own.size / world.tile_size), avoid)

    def get_movement_direction(self) -> tuple[int, int]:
        return self._movement

    def consume_shoot(self) -> bool:
        requested = self._shoot_requested
        self._shoot_requested = False
        return requested

    def clear_pending_shoot(self) -> None:
        self._shoot_requested = False
