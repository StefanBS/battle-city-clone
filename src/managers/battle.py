"""Battle: one playing of a Stage, from its Players appearing to its end."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame
from loguru import logger

from src.managers.collision_manager import CollisionManager
from src.managers.collision_response_handler import CollisionResponseHandler
from src.managers.effect_manager import EffectManager
from src.managers.enemy_manager import EnemyManager
from src.managers.outcomes import (
    BaseDestroyed,
    CarrierHit,
    CollisionOutcome,
    EnemyDestroyed,
    PlayerDestroyed,
    PowerUpCollected,
)
from src.managers.player_manager import CarriedProgress, PlayerManager
from src.managers.power_up_manager import PowerUpManager
from src.managers.spawn_manager import SpawnManager
from src.managers.tank_stepper import TankStepper
from src.managers.world_view import WorldView, build_world_view
from src.states.game_mode import GameMode
from src.utils.constants import (
    ENEMY_POINTS,
    POWERUP_COLLECT_POINTS,
    SPAWN_INVINCIBILITY_DURATION,
    Difficulty,
    EffectType,
)

if TYPE_CHECKING:
    from src.core.enemy_tank import EnemyTank
    from src.core.map import Map
    from src.managers.sound_manager import SoundManager
    from src.managers.texture_manager import TextureManager


class BattleResult(Enum):
    """How a Battle ended."""

    GAME_OVER = auto()
    VICTORY = auto()


class Battle:
    """One playing of a Stage: its collaborators, frame pipeline and outcomes.

    Built from a loaded map and each Player's carried progress. Each ``step``
    runs one frame: World View, Players, Enemies, bullets, spawning, Power-Ups,
    collisions, then outcomes. It ends when it reports Game Over or Victory,
    after which stepping it does nothing.
    """

    def __init__(
        self,
        game_map: Map,
        mode: GameMode,
        carried: Mapping[int, CarriedProgress],
        difficulty: Difficulty,
        controller_instance_ids: list[int],
        texture_manager: TextureManager,
        sound: SoundManager,
    ) -> None:
        """Set up the Stage's collaborators and put its Players on the map.

        Args:
            game_map: The Stage's loaded map.
            mode: Which player slots exist and who drives each one.
            carried: Each Player's progress from the previous Battle, by player
                id. Empty for the first Stage.
            difficulty: The difficulty chosen in Settings. The map's own
                difficulty override wins over it.
            controller_instance_ids: Open SDL game controllers.
            texture_manager: Texture atlas for tanks, tiles and effects.
            sound: Where the Battle plays its sounds.
        """
        self.map = game_map
        self._sound = sound
        self._result: BattleResult | None = None

        self.collision_manager = CollisionManager()
        self.effect_manager = EffectManager(texture_manager)
        # Must be created before CollisionResponseHandler.
        self.power_up_manager = PowerUpManager(texture_manager, game_map)
        self.collision_response_handler = CollisionResponseHandler(
            game_map=game_map,
            effect_manager=self.effect_manager,
            power_up_manager=self.power_up_manager,
            sound_manager=sound,
        )
        self.player_manager = PlayerManager(
            texture_manager,
            sound,
            game_map,
            controller_instance_ids=controller_instance_ids,
            mode=mode,
            carried=carried,
        )
        base_tile = game_map.get_base()
        self.enemy_manager = EnemyManager(
            difficulty=(
                game_map.difficulty_override
                if game_map.difficulty_override is not None
                else difficulty
            ),
            base_position=(
                (float(base_tile.rect.centerx), float(base_tile.rect.centery))
                if base_tile is not None
                else None
            ),
        )
        self.spawn_manager = SpawnManager(
            texture_manager=texture_manager,
            game_map=game_map,
            enemy_composition=game_map.enemy_composition,
            spawn_interval=game_map.spawn_interval,
            tanks=self.player_manager.get_active_players(),
            effect_manager=self.effect_manager,
            powerup_carrier_indices=game_map.powerup_carrier_indices,
        )
        # Owns every bullet, so no bullet outlives the Battle.
        self.tank_stepper = TankStepper(game_map)

        for player in self.player_manager.get_active_players():
            player.activate_invincibility(SPAWN_INVINCIBILITY_DURATION)

    @property
    def result(self) -> BattleResult | None:
        """How the Battle ended, or None while it is still being fought."""
        return self._result

    @property
    def carried_progress(self) -> dict[int, CarriedProgress]:
        """What each Player takes into the next Battle, by player id."""
        return self.player_manager.carried_progress

    def handle_event(self, event: pygame.event.Event) -> None:
        """Pass a pygame event to every Player's input."""
        self.player_manager.handle_event(event)

    def clear_pending_shoot(self) -> None:
        """Drop any buffered shoot input, e.g. after leaving a menu."""
        self.player_manager.clear_pending_shoot()

    def world_view(self) -> WorldView:
        """Snapshot the current battlefield for the Players' inputs."""
        return build_world_view(
            self.map,
            players=self.player_manager.get_active_players(),
            enemies=self.enemy_manager.enemies,
            enemies_frozen=self.enemy_manager.enemies_frozen,
            power_ups=self.power_up_manager.active_power_ups,
            bullets=self.tank_stepper.bullets,
        )

    def step(self, dt: float) -> BattleResult | None:
        """Run one frame and report whether it ended the Battle.

        Args:
            dt: Time step in seconds.

        Returns:
            How the Battle ended, or None if it goes on. Once it has ended,
            this does nothing and returns the same result.
        """
        if self._result is not None:
            return self._result

        self.map.update(dt)
        self.player_manager.observe(self.world_view())
        self.player_manager.update(dt, self.tank_stepper)

        active_players = self.player_manager.get_active_players()

        if self.enemy_manager.step_enemies(dt, self.tank_stepper, active_players):
            self._sound.play("shoot")

        # Engine sound: plays when any tank is moving
        any_moving = any(p.is_moving for p in active_players) or any(
            e.is_moving for e in self.enemy_manager.enemies
        )
        self._sound.update_engine(any_moving)

        self.tank_stepper.update_bullets(dt)

        self._enter_battlefield(
            self.spawn_manager.update(
                dt, [*active_players, *self.enemy_manager.enemies], self.map
            )
        )
        self.power_up_manager.update(dt)

        # Built AFTER updates so newly fired bullets are included
        self.collision_manager.check_collisions(
            player_tanks=active_players,
            enemy_tanks=self.enemy_manager.enemies,
            bullets=self.tank_stepper.bullets,
            tank_blocking_tiles=self.map.get_blocking_tiles(),
            bullet_blocking_tiles=self.map.get_bullet_blocking_tiles(),
            player_base=self.map.get_base(),
            power_ups=self.power_up_manager.active_power_ups,
        )

        events = self.collision_manager.get_collision_events()
        self.apply_outcomes(self.collision_response_handler.process_collisions(events))

        # Powerup blink sound: plays when any powerup is active
        self._sound.update_powerup_blink(bool(self.power_up_manager.active_power_ups))

        self.effect_manager.update(dt)

        # The only place Game Over is decided; it wins over Victory.
        if self.map.is_base_destroyed or self.player_manager.is_game_over():
            logger.info("Game over.")
            self._result = BattleResult.GAME_OVER
        elif self.spawn_manager.is_exhausted and not self.enemy_manager.enemies:
            logger.info("All enemies defeated. Victory!")
            self._result = BattleResult.VICTORY
        return self._result

    def apply_outcomes(self, outcomes: list[CollisionOutcome]) -> None:
        """Apply a frame's outcomes, and the outcomes they cause, in order."""
        queue = deque(outcomes)
        while queue:
            match queue.popleft():
                case CarrierHit(enemy=enemy):
                    self._drop_carrier_power_up(enemy)
                case EnemyDestroyed(enemy=enemy, by=by):
                    # A bullet and a Grenade can both destroy it in one frame.
                    if not self.enemy_manager.remove(enemy):
                        continue
                    self.effect_manager.spawn_at_rect(
                        EffectType.LARGE_EXPLOSION, enemy.rect
                    )
                    self._sound.play("explosion")
                    if by is not None:
                        self.player_manager.add_score(
                            ENEMY_POINTS.get(enemy.tank_type, 0),
                            player_id=by.player_id,
                        )
                    # A Grenade kill is a Carrier's only drop without a hit.
                    self._drop_carrier_power_up(enemy)
                case PlayerDestroyed(player=player):
                    # Before handle_player_destroyed moves it to its spawn point.
                    self.effect_manager.spawn_at_rect(
                        EffectType.LARGE_EXPLOSION, player.rect
                    )
                    self._sound.play("explosion")
                    self.player_manager.handle_player_destroyed(player)
                case BaseDestroyed():
                    pass  # Game Over is decided once all outcomes are applied.
                case PowerUpCollected(power_up_type=power_up_type, player=player):
                    self.player_manager.add_score(
                        POWERUP_COLLECT_POINTS, player_id=player.player_id
                    )
                    self._sound.play("powerup")
                    queue.extend(
                        self.power_up_manager.apply(
                            power_up_type, player, self.enemy_manager
                        )
                    )

    def _enter_battlefield(self, enemies: list[EnemyTank]) -> None:
        """Put newly materialized Enemies on the battlefield.

        A Carrier appearing clears the Power-Ups already on the field.
        """
        for enemy in enemies:
            self.enemy_manager.add(enemy)
        if any(enemy.is_carrier for enemy in enemies):
            self.power_up_manager.clear()

    def _drop_carrier_power_up(self, enemy: EnemyTank) -> None:
        """Make a Carrier's Power-Up appear; a Carrier drops only once."""
        if not enemy.is_carrier:
            return
        enemy.stop_carrying()
        self.power_up_manager.spawn_power_up(
            [
                *self.player_manager.get_active_players(),
                *self.enemy_manager.enemies,
            ]
        )
