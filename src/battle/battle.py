"""Battle: one playing of a Stage, from its Players appearing to its end."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame
from loguru import logger

from src.core.base_wall import BaseWall
from src.battle.collision_manager import CollisionManager
from src.battle.effect_manager import EffectManager
from src.battle.enemy_manager import EnemyManager
from src.battle.outcomes import (
    BaseDestroyed,
    BaseWallFortified,
    CarrierHit,
    ClockStarted,
    BattleOutcome,
    EnemyDestroyed,
    GrenadeDetonated,
    PlayerDestroyed,
    PowerUpCollected,
)
from src.battle.player_manager import (
    CarriedProgress,
    PlayerHudEntry,
    PlayerManager,
)
from src.battle.power_up_manager import PowerUpManager
from src.battle.spawn_manager import SpawnManager
from src.battle.tank_stepper import StepResult, TankIntent, TankStepper
from src.world_view.world_view import WorldView, build_world_view
from src.states.battle_result import BattleResult
from src.states.game_mode import GameMode
from src.utils.constants import (
    ENEMY_POINTS,
    POWERUP_COLLECT_POINTS,
    SPAWN_INVINCIBILITY_DURATION,
    Difficulty,
    EffectType,
    PowerUpType,
    TankType,
)

if TYPE_CHECKING:
    from src.core.bullet import Bullet
    from src.core.enemy_ai import EnemyAI
    from src.core.effect import Effect
    from src.core.enemy_tank import EnemyTank
    from src.core.map import Map
    from src.core.player_tank import PlayerTank
    from src.core.power_up import PowerUp
    from src.core.sprite_atlas import SpriteAtlas
    from src.core.tank import Tank
    from src.battle.player_input import PlayerInput
    from src.battle.sound_player import SoundPlayer


@dataclass(frozen=True, kw_only=True)
class BattleScene:
    """What a Battle shows this frame, for the Renderer to draw.

    Unlike the World View, which holds values for the Players' inputs to
    decide from, it holds the live objects, since they draw themselves. It is
    read-only by type: nothing in it is for changing.
    """

    map: Map
    players: tuple[PlayerTank, ...]
    enemies: tuple[EnemyTank, ...]
    bullets: tuple[Bullet, ...]
    power_ups: tuple[PowerUp, ...]
    effects: tuple[Effect, ...]
    hud_entries: tuple[PlayerHudEntry, ...]


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
        atlas: SpriteAtlas,
        sound: SoundPlayer,
        cpu_partner: PlayerInput | None = None,
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
            atlas: Texture atlas for tanks, tiles and effects.
            sound: Where the Battle plays its sounds.
            cpu_partner: The input that drives P2 in 1 Player + CPU mode.
        """
        self._map = game_map
        self._sound = sound
        self._atlas = atlas
        self._result: BattleResult | None = None

        self._base_wall = BaseWall(game_map)
        self._effect_manager = EffectManager(atlas)
        self._power_up_manager = PowerUpManager(atlas, game_map)
        self._collision_manager = CollisionManager(
            game_map=game_map,
            effect_manager=self._effect_manager,
            power_up_manager=self._power_up_manager,
            sound=sound,
        )
        self._player_manager = PlayerManager(
            atlas,
            sound,
            game_map,
            controller_instance_ids=controller_instance_ids,
            mode=mode,
            carried=carried,
            cpu_partner=cpu_partner,
        )
        base_tile = game_map.get_base()
        self._enemy_manager = EnemyManager(
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
        self._spawn_manager = self._new_spawn_manager(
            game_map.enemy_composition,
            game_map.spawn_interval,
            game_map.powerup_carrier_indices,
        )
        # Owns every bullet, so no bullet outlives the Battle.
        self._tank_stepper = TankStepper(game_map)

        for player in self._player_manager.get_active_players():
            player.activate_invincibility(SPAWN_INVINCIBILITY_DURATION)
        # The first Enemy starts Spawning as the Battle begins.
        self._spawn_manager.start_spawning(self._player_manager.get_active_players())

    @property
    def map(self) -> Map:
        """The Stage's map, which the Battle was built on."""
        return self._map

    @property
    def result(self) -> BattleResult | None:
        """How the Battle ended, or None while it is still being fought."""
        return self._result

    @property
    def carried_progress(self) -> dict[int, CarriedProgress]:
        """What each Player takes into the next Battle, by player id."""
        return self._player_manager.carried_progress

    def handle_event(self, event: pygame.event.Event) -> None:
        """Pass a pygame event to every Player's input."""
        self._player_manager.handle_event(event)

    def clear_pending_shoot(self) -> None:
        """Drop any buffered shoot input, e.g. after leaving a menu."""
        self._player_manager.clear_pending_shoot()

    def world_view(self) -> WorldView:
        """Snapshot the current battlefield for the Players' inputs."""
        return build_world_view(
            self._map,
            players=self._player_manager.get_active_players(),
            enemies=self._enemy_manager.enemies,
            power_ups=self._power_up_manager.active_power_ups,
            bullets=self._tank_stepper.bullets,
        )

    def scene(self) -> BattleScene:
        """What the Battle shows this frame, for the Renderer."""
        return BattleScene(
            map=self._map,
            players=tuple(self._player_manager.get_active_players()),
            enemies=tuple(self._enemy_manager.enemies),
            bullets=self._tank_stepper.bullets,
            power_ups=tuple(self._power_up_manager.active_power_ups),
            effects=tuple(self._effect_manager.effects),
            hud_entries=self._player_manager.hud_entries,
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

        self._map.update(dt)
        self._player_manager.observe(self.world_view())
        self._player_manager.update(dt, self._tank_stepper)

        active_players = self._player_manager.get_active_players()

        if self._enemy_manager.step_enemies(dt, self._tank_stepper, active_players):
            self._sound.play("shoot")

        # Engine sound: plays when any tank is moving
        any_moving = any(p.is_moving for p in active_players) or any(
            e.is_moving for e in self._enemy_manager.enemies
        )
        self._sound.update_engine(any_moving)

        self._tank_stepper.update_bullets(dt)

        # Enemies that just Appeared are on the battlefield before the timer
        # runs, so they block their spawn point too.
        self.bring_in_spawns()
        self._spawn_manager.advance(dt, self._tanks_on_battlefield())
        self._power_up_manager.update(dt)
        self._base_wall.update(dt)

        # After the updates, so newly fired bullets are included.
        self.apply_outcomes(
            self._collision_manager.resolve(
                players=active_players,
                enemies=self._enemy_manager.enemies,
                bullets=self._tank_stepper.bullets,
            )
        )

        # Powerup blink sound: plays when any powerup is active
        self._sound.update_powerup_blink(bool(self._power_up_manager.active_power_ups))

        self._effect_manager.update(dt)

        # The only place Game Over is decided; it wins over Victory.
        if self._map.is_base_destroyed or self._player_manager.is_game_over():
            logger.info("Game over.")
            self._result = BattleResult.GAME_OVER
        elif self._spawn_manager.is_exhausted and not self._enemy_manager.enemies:
            logger.info("All enemies defeated. Victory!")
            self._result = BattleResult.VICTORY
        return self._result

    def apply_outcomes(self, outcomes: list[BattleOutcome]) -> None:
        """Apply a frame's outcomes, and the outcomes they cause, in order."""
        queue = deque(outcomes)
        while queue:
            match queue.popleft():
                case CarrierHit(enemy=enemy):
                    self._drop_carrier_power_up(enemy)
                case EnemyDestroyed(enemy=enemy, by=by):
                    # A bullet and a Grenade can both destroy it in one frame.
                    if not self._enemy_manager.remove(enemy):
                        continue
                    self._effect_manager.spawn_at_rect(
                        EffectType.LARGE_EXPLOSION, enemy.rect
                    )
                    self._sound.play("explosion")
                    if by is not None:
                        self._player_manager.add_score(
                            ENEMY_POINTS.get(enemy.tank_type, 0),
                            player_id=by.player_id,
                        )
                    # A Grenade kill is a Carrier's only drop without a hit.
                    self._drop_carrier_power_up(enemy)
                case PlayerDestroyed(player=player):
                    # Before handle_player_destroyed moves it to its spawn point.
                    self._effect_manager.spawn_at_rect(
                        EffectType.LARGE_EXPLOSION, player.rect
                    )
                    self._sound.play("explosion")
                    self._player_manager.handle_player_destroyed(player)
                case BaseDestroyed():
                    pass  # Game Over is decided once all outcomes are applied.
                case GrenadeDetonated():
                    queue.extend(
                        EnemyDestroyed(enemy, by=None)
                        for enemy in self._enemy_manager.enemies
                    )
                case ClockStarted():
                    self._enemy_manager.start_clock()
                case BaseWallFortified():
                    self._base_wall.fortify()
                case PowerUpCollected(power_up_type=power_up_type, player=player):
                    self._player_manager.add_score(
                        POWERUP_COLLECT_POINTS, player_id=player.player_id
                    )
                    self._sound.play("powerup")
                    queue.extend(self._power_up_manager.apply(power_up_type, player))

    def bring_in_spawns(self) -> None:
        """Put the Enemies that have Appeared on the battlefield.

        Starts no new spawn. A Carrier appearing clears the Power-Ups already
        on the field.
        """
        enemies = self._spawn_manager.take_appeared()
        for enemy in enemies:
            self._enemy_manager.add(enemy)
        if any(enemy.is_carrier for enemy in enemies):
            self._power_up_manager.clear()

    def add_enemy(self, enemy: EnemyTank, ai: EnemyAI | None = None) -> None:
        """Put an Enemy on the battlefield without it Spawning.

        Args:
            enemy: The Enemy to put on the battlefield.
            ai: The AI to drive it; one for the Stage's difficulty and Base
                when not given.
        """
        self._enemy_manager.add(enemy, ai)

    def clear_enemies(self) -> None:
        """Take every Enemy off the battlefield, as if it had never been there."""
        self._enemy_manager.clear()

    def replace_roster(
        self,
        composition: dict[TankType, int],
        carrier_indices: tuple[int, ...] = (),
        spawn_interval: float | None = None,
    ) -> None:
        """Give the Battle a fresh Roster, with nothing Spawning yet.

        An Enemy already Spawning is dropped and never Appears, though its
        spawn animation still plays to the end.

        Args:
            composition: How many Enemies of each type are still to come. An
                empty one means the Roster is used up.
            carrier_indices: Which Enemies, by draw order, are Carriers.
            spawn_interval: Seconds before the next Enemy starts Spawning,
                the map's by default; ``inf`` means none comes on its own.
        """
        self._spawn_manager = self._new_spawn_manager(
            composition,
            spawn_interval if spawn_interval is not None else self._map.spawn_interval,
            carrier_indices,
        )

    def start_spawning(self) -> bool:
        """Start the next Enemy of the Roster Spawning now.

        Returns:
            True if an Enemy started Spawning; False if the Roster is used up
            or the chosen Enemy Spawn Point is blocked.
        """
        return self._spawn_manager.start_spawning(self._tanks_on_battlefield())

    def add_bullet(self, bullet: Bullet) -> None:
        """Put a bullet in flight as it is, outside its owner's Bullet Cap.

        No shoot sound plays; firing within the cap is ``TankStepper.step``'s job.
        """
        self._tank_stepper.put_in_flight(bullet)

    def drop_power_up(
        self,
        power_up_type: PowerUpType | None = None,
        position: tuple[int, int] | None = None,
    ) -> None:
        """Make a Power-Up appear, replacing any already on the battlefield.

        Args:
            power_up_type: Which Power-Up; a random one when not given.
            position: Where it lands, in pixels; a free spot clear of every
                tank when not given.
        """
        self._power_up_manager.spawn_power_up(
            self._tanks_on_battlefield(),
            power_up_type=power_up_type,
            position=position,
        )

    def step_tank(self, tank: Tank, intent: TankIntent, dt: float) -> StepResult:
        """Step one tank through a frame on its own, firing within its Bullet Cap.

        Args:
            tank: The tank to step, Player or Enemy.
            intent: Where it moves and whether it fires this frame.
            dt: Time step in seconds.

        Returns:
            Whether the tank started a Slide and whether it fired.
        """
        return self._tank_stepper.step(tank, intent, dt)

    def _new_spawn_manager(
        self,
        composition: dict[TankType, int],
        spawn_interval: float,
        carrier_indices: tuple[int, ...] | None,
    ) -> SpawnManager:
        """A SpawnManager for this Battle's map sending ``composition``."""
        return SpawnManager(
            atlas=self._atlas,
            game_map=self._map,
            enemy_composition=composition,
            spawn_interval=spawn_interval,
            effect_manager=self._effect_manager,
            powerup_carrier_indices=carrier_indices,
        )

    def _drop_carrier_power_up(self, enemy: EnemyTank) -> None:
        """Make a Carrier's Power-Up appear; a Carrier drops only once."""
        if not enemy.is_carrier:
            return
        enemy.stop_carrying()
        self._power_up_manager.spawn_power_up(self._tanks_on_battlefield())

    def _tanks_on_battlefield(self) -> list[Tank]:
        """Every live Player and Enemy: what blocks spawn points and drops."""
        return [
            *self._player_manager.get_active_players(),
            *self._enemy_manager.enemies,
        ]
