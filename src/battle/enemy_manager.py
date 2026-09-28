"""EnemyManager: owns the Enemies on the battlefield and steps them."""

from src.core.enemy_ai import EnemyAI
from src.core.enemy_tank import EnemyTank
from src.core.player_tank import PlayerTank
from src.battle.tank_stepper import TankStepper
from src.utils.constants import CLOCK_FREEZE_DURATION, Difficulty


class EnemyManager:
    """Owns the Enemies on the battlefield: each Enemy, its AI, and the Clock.

    Responsibilities:
    - Pair each Enemy that enters the battlefield with the EnemyAI that drives it.
    - Each frame: step every Enemy through TankStepper. A Frozen Enemy's AI
      doesn't decide, and the stepper keeps the Enemy still.
    - Keep the time left on a Clock, so Enemies that appear during it are
      Frozen too, even once every Enemy is gone.
    - Drop destroyed Enemies.

    Lasts one Battle, like PlayerManager.
    """

    def __init__(
        self,
        difficulty: Difficulty = Difficulty.NORMAL,
        base_position: tuple[float, float] | None = None,
    ) -> None:
        """Initialize the EnemyManager with no Enemies on the battlefield.

        Args:
            difficulty: AI difficulty level for every Enemy this Stage.
            base_position: Centre of the Stage's base, which every Enemy AI
                steers and fires toward. None when the map has no base.
        """
        self._difficulty = difficulty
        self._base_position = base_position
        self._enemies: list[EnemyTank] = []
        # Keyed by enemy_id, which is never reused.
        self._enemy_ais: dict[int, EnemyAI] = {}
        self._clock_time_left: float = 0.0

    @property
    def enemies(self) -> tuple[EnemyTank, ...]:
        """The Enemies on the battlefield, in the order they were added."""
        return tuple(self._enemies)

    def add(self, enemy: EnemyTank, ai: EnemyAI | None = None) -> None:
        """Put an Enemy on the battlefield, paired with the EnemyAI that drives it.

        Args:
            enemy: The Enemy entering the battlefield.
            ai: The AI to drive it. Built for the Stage's difficulty and base
                when not given.
        """
        if ai is None:
            ai = EnemyAI(
                enemy, difficulty=self._difficulty, base_position=self._base_position
            )
        if self._clock_time_left > 0:
            enemy.freeze(self._clock_time_left)
        self._enemies.append(enemy)
        self._enemy_ais[enemy.enemy_id] = ai

    def remove(self, enemy: EnemyTank) -> bool:
        """Take a destroyed Enemy off the battlefield.

        Returns:
            Whether the Enemy was still on the battlefield.
        """
        self._enemy_ais.pop(enemy.enemy_id, None)
        if enemy not in self._enemies:
            return False
        self._enemies.remove(enemy)
        return True

    def clear(self) -> None:
        """Take every Enemy, and the AI driving it, off the battlefield.

        A Clock in effect keeps running: Enemies added later are still Frozen.
        """
        self._enemies.clear()
        self._enemy_ais.clear()

    def start_clock(self) -> None:
        """Start a Clock: every Enemy is Frozen until it runs out.

        A Clock already in effect starts over.
        """
        self._clock_time_left = CLOCK_FREEZE_DURATION
        for enemy in self._enemies:
            enemy.freeze(CLOCK_FREEZE_DURATION)

    def step_enemies(
        self, dt: float, stepper: TankStepper, players: list[PlayerTank]
    ) -> bool:
        """Step every Enemy through the frame, driven by its Enemy AI.

        Args:
            dt: Time step in seconds.
            stepper: Steps each tank and owns the bullets it fires.
            players: The live Players; each Enemy steers toward the nearest.

        Returns:
            Whether any Enemy fired, so the caller can play the sound.
        """
        # Counted down here, like each Enemy's own freeze, so an Enemy that
        # appears later gets the same time left as those already Frozen.
        self._clock_time_left = max(0.0, self._clock_time_left - dt)
        fired = False
        for enemy in self.enemies:
            ai = self._enemy_ais[enemy.enemy_id]
            # While Frozen the AI's timers pause; the stepper keeps it still.
            if not enemy.is_frozen:
                nearest = min(
                    players,
                    key=lambda p: abs(p.x - enemy.x) + abs(p.y - enemy.y),
                    default=None,
                )
                target = (nearest.x, nearest.y) if nearest is not None else None
                ai.update(dt, target)
            fired = stepper.step(enemy, ai, dt).fired or fired
        return fired
