"""EnemyAI: the Enemy AI that tells one EnemyTank where to go and when to fire."""

import random

from loguru import logger

from src.core.enemy_tank import EnemyTank, get_enemy_config
from src.utils.constants import (
    Difficulty,
    Direction,
    DIRECTION_CHANGE_RANDOM_OFFSET,
    SHOOT_RANDOM_OFFSET,
)

_ALL_DIRECTIONS = list(Direction)


class EnemyAI:
    """Enemy AI for one EnemyTank: turns at random and fires periodically.

    Implements TankIntent, and is paired with its tank the way a PlayerInput
    is paired with a PlayerTank. It only records a wanted direction and a
    wish to shoot; TankStepper turns, moves and fires the tank.
    """

    def __init__(
        self,
        tank: EnemyTank,
        *,
        difficulty: Difficulty = Difficulty.NORMAL,
        base_position: tuple[float, float] | None = None,
        shoot_interval: float | None = None,
        direction_change_interval: float | None = None,
    ) -> None:
        """
        Initialize the AI and listen for its tank being blocked.

        Args:
            tank: The Enemy this AI drives.
            difficulty: Scales how strongly the AI steers toward the base
                and the Player, and how eagerly it fires when aligned.
            base_position: Centre of the base, steered toward and fired at.
            shoot_interval: Seconds between shots; None uses the tank type's.
            direction_change_interval: Seconds between turns; None uses the
                tank type's.
        """
        config = get_enemy_config()
        props = config[tank.tank_type]

        self.tank = tank
        self.base_position = base_position
        # This frame's target, from update(); a blocked turn steers by it too.
        self._target_position: tuple[float, float] | None = None
        self.direction_timer: float = 0
        self.direction_change_interval: float = (
            direction_change_interval
            if direction_change_interval is not None
            else props["direction_change_interval"]
        )
        self.shoot_timer: float = 0
        self.shoot_interval: float = (
            shoot_interval if shoot_interval is not None else props["shoot_interval"]
        )
        self._wants_to_shoot: bool = False
        self._blocked_directions: set[Direction] = set()
        # A turn the AI wants but TankStepper hasn't made yet; None means
        # keep going the way the tank faces.
        self._turn_to: Direction | None = None

        # Compute effective AI biases from difficulty config + type multipliers
        difficulty_config = config.get("difficulty", {}).get(
            difficulty,
            {"base_bias": 0.0, "player_bias": 0.0, "aligned_shoot_multiplier": 1.0},
        )
        self.effective_base_bias: float = difficulty_config["base_bias"] * props.get(
            "base_bias_multiplier", 1.0
        )
        self.effective_player_bias: float = difficulty_config[
            "player_bias"
        ] * props.get("player_bias_multiplier", 1.0)
        self.aligned_shoot_multiplier: float = difficulty_config[
            "aligned_shoot_multiplier"
        ]

        tank.movement_blocked_listener = self.on_movement_blocked

    def _direction_moves_toward(
        self, direction: Direction, target: tuple[float, float]
    ) -> bool:
        """Check if moving in direction reduces distance to target."""
        dx, dy = direction.delta
        tx, ty = target
        if dx != 0:
            return (dx > 0 and tx > self.tank.x) or (dx < 0 and tx < self.tank.x)
        return (dy > 0 and ty > self.tank.y) or (dy < 0 and ty < self.tank.y)

    def _change_direction(self) -> None:
        """Pick a direction to turn to, weighted by AI biases when applicable."""
        old_direction = self.tank.direction

        # Prefer unblocked directions, excluding opposite to avoid reversing
        opposite = old_direction.opposite
        candidates = [
            d
            for d in _ALL_DIRECTIONS
            if d not in self._blocked_directions and d != opposite
        ]
        # Fall back to unblocked only (allow opposite)
        if not candidates:
            candidates = [
                d for d in _ALL_DIRECTIONS if d not in self._blocked_directions
            ]
        # All directions blocked — stay put and wait for one to open
        if not candidates:
            return

        if self.effective_base_bias > 0 or self.effective_player_bias > 0:
            weights = [1.0] * len(candidates)
            for i, d in enumerate(candidates):
                if self.base_position is not None:
                    if self._direction_moves_toward(d, self.base_position):
                        weights[i] += self.effective_base_bias
                if self._target_position is not None:
                    if self._direction_moves_toward(d, self._target_position):
                        weights[i] += self.effective_player_bias
            new_direction = random.choices(candidates, weights)[0]
        else:
            new_direction = random.choice(candidates)

        self._turn_to = new_direction
        if new_direction != old_direction:
            logger.trace(
                f"EnemyAI ({self.tank.tank_type}) turning "
                f"from {old_direction} to {new_direction}"
            )
        else:
            logger.trace(
                f"EnemyAI ({self.tank.tank_type}) direction remained {old_direction}."
            )

    def _is_aligned_with(self, target: tuple[float, float]) -> bool:
        """Check if the tank is facing toward and aligned with a target position."""
        tx, ty = target
        dx, dy = self.tank.direction.delta
        tile = self.tank.tile_size
        if dx != 0:
            if abs(self.tank.y - ty) > tile:
                return False
        else:
            if abs(self.tank.x - tx) > tile:
                return False
        return self._direction_moves_toward(self.tank.direction, target)

    def get_movement_direction(self) -> tuple[int, int]:
        """The way the AI wants to drive: its pending turn, else straight on."""
        return (self._turn_to or self.tank.direction).delta

    def consume_shoot(self) -> bool:
        """Check if the AI wants to shoot and clear the flag."""
        if self._wants_to_shoot:
            self._wants_to_shoot = False
            return True
        return False

    def on_movement_blocked(self) -> None:
        """Pick a new direction when the tank hits a wall, tank or map edge."""
        self._blocked_directions.add(self.tank.direction)
        self._change_direction()
        self.direction_timer = 0

    def update(self, dt: float, target_position: tuple[float, float] | None) -> None:
        """
        Advance timers and decide where to go and whether to shoot.

        Run once per frame, before TankStepper steps the tank.

        Args:
            dt: Time elapsed since last update in seconds
            target_position: The Player to steer and fire toward this frame,
                or None when there is no live Player.
        """
        self._target_position = target_position
        if self._turn_to is self.tank.direction:
            self._turn_to = None
        # Clear blocked directions once the tank successfully moved,
        # meaning the path is no longer obstructed. Check before the
        # tank's own update overwrites prev_x/prev_y.
        if self.tank.x != self.tank.prev_x or self.tank.y != self.tank.prev_y:
            self._blocked_directions.clear()

        self.direction_timer += dt
        self.shoot_timer += dt

        # Change direction periodically
        if self.direction_timer >= self.direction_change_interval:
            logger.trace(f"EnemyAI ({self.tank.tank_type}) direction timer triggered.")
            self._change_direction()
            self.direction_timer = random.uniform(0, DIRECTION_CHANGE_RANDOM_OFFSET)

        # Shoot periodically (reduced interval when aligned with a target)
        reduced_threshold = self.shoot_interval * self.aligned_shoot_multiplier
        if self.shoot_timer >= self.shoot_interval:
            logger.trace(f"EnemyAI ({self.tank.tank_type}) shoot timer triggered.")
            self._wants_to_shoot = True
            self.shoot_timer = random.uniform(0, SHOOT_RANDOM_OFFSET)
        elif (
            self.aligned_shoot_multiplier < 1.0
            and self.shoot_timer >= reduced_threshold
        ):
            # Only check alignment when timer is between reduced and full thresholds
            aligned = False
            if self.base_position is not None:
                aligned = self._is_aligned_with(self.base_position)
            if not aligned and self._target_position is not None:
                aligned = self._is_aligned_with(self._target_position)
            if aligned:
                logger.trace(
                    f"EnemyAI ({self.tank.tank_type}) aligned shoot triggered."
                )
                self._wants_to_shoot = True
                self.shoot_timer = random.uniform(0, SHOOT_RANDOM_OFFSET)
