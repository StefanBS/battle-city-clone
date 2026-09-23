"""EnemyManager: owns the Enemies on the battlefield and steps them."""

from src.core.enemy_ai import EnemyAI
from src.core.enemy_tank import EnemyTank
from src.core.player_tank import PlayerTank
from src.managers.tank_stepper import TankStepper
from src.utils.constants import Difficulty


class EnemyManager:
    """Owns the Enemies on the battlefield: each Enemy, its AI, and the Clock.

    Responsibilities:
    - Pair each Enemy that enters the battlefield with the EnemyAI that drives it.
    - Each frame: step every Enemy through TankStepper, unless they are Frozen.
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
        self.enemies: list[EnemyTank] = []
        # Keyed by enemy_id, which is never reused.
        self._enemy_ais: dict[int, EnemyAI] = {}
        self._freeze_timer: float = 0.0

    @property
    def base_position(self) -> tuple[float, float] | None:
        """Centre of this stage's base, or None when the map has no base."""
        return self._base_position

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
        self.enemies.append(enemy)
        self._enemy_ais[enemy.enemy_id] = ai

    def remove(self, enemy: EnemyTank) -> bool:
        """Take a destroyed Enemy off the battlefield.

        Returns:
            Whether the Enemy was still on the battlefield.
        """
        self._enemy_ais.pop(enemy.enemy_id, None)
        if enemy not in self.enemies:
            return False
        self.enemies.remove(enemy)
        return True

    def freeze(self, duration: float) -> None:
        """Make every Enemy Frozen for ``duration`` seconds (Clock Power-Up)."""
        self._freeze_timer = duration

    @property
    def enemies_frozen(self) -> bool:
        """Whether the Enemies are Frozen, so step_enemies leaves them be."""
        return self._freeze_timer > 0

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
        if self.enemies_frozen:
            # Counted down after the check, so a Clock lasts whole frames.
            self._freeze_timer -= dt
            return False
        fired = False
        for enemy in self.enemies:
            nearest = min(
                players,
                key=lambda p: abs(p.x - enemy.x) + abs(p.y - enemy.y),
                default=None,
            )
            ai = self._enemy_ais[enemy.enemy_id]
            ai.update(dt, (nearest.x, nearest.y) if nearest is not None else None)
            fired = stepper.step(enemy, ai, dt).fired or fired
        return fired
