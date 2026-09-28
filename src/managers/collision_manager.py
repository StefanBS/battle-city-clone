"""One frame's collisions: found, responded to, and returned as outcomes.

See ``docs/adr/0003-collision-response-returns-outcomes.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING

import pygame
from loguru import logger

from src.core.bullet import Bullet
from src.core.enemy_tank import EnemyTank
from src.core.game_object import GameObject
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.core.power_up import PowerUp
from src.core.tank import HitResult, Tank
from src.core.tile import Tile, TileType
from src.managers.effect_manager import EffectManager
from src.managers.outcomes import (
    BaseDestroyed,
    BattleOutcome,
    CarrierHit,
    EnemyDestroyed,
    PlayerDestroyed,
    PowerUpCollected,
)
from src.utils.constants import (
    EffectType,
    FRIENDLY_FIRE_FREEZE_DURATION,
    OwnerType,
)

if TYPE_CHECKING:
    from src.managers.power_up_manager import PowerUpManager
    from src.managers.sound_manager import SoundManager


@dataclass
class _Frame:
    """What one ``resolve`` call has produced so far."""

    outcomes: list[BattleOutcome] = field(default_factory=list)
    # Tanks destroyed earlier in the frame: bullets pass through them.
    destroyed: set[Tank] = field(default_factory=set)
    # Tanks already stopped this frame, by a tile or another tank.
    stopped: set[Tank] = field(default_factory=set)


# One collision found, waiting to be responded to.
_Collision = Callable[[_Frame], None]


class CollisionManager:
    """Finds a frame's collisions, responds to them and returns the outcomes.

    Physics that later collisions in the same frame depend on (bullets,
    reverts, tiles, damage) is applied while responding; game-level
    consequences are returned as outcomes for ``Battle`` to apply.
    """

    def __init__(
        self,
        game_map: Map,
        effect_manager: EffectManager,
        power_up_manager: PowerUpManager,
        sound_manager: SoundManager,
    ) -> None:
        self._map = game_map
        self._effect_manager = effect_manager
        self._power_up_manager = power_up_manager
        self._sound_manager = sound_manager

    def resolve(
        self,
        players: Sequence[PlayerTank],
        enemies: Sequence[EnemyTank],
        bullets: Sequence[Bullet],
    ) -> list[BattleOutcome]:
        """Resolve one frame's collisions and return their outcomes in order.

        Every collision is found against where things are after this frame's
        moves, before any is responded to. Tiles, the Base and the Power-Ups
        on the battlefield come from the Map and the PowerUpManager.

        Args:
            players: The active Players' tanks.
            enemies: The Enemies on the battlefield.
            bullets: Every bullet in flight, Player's and Enemy's.

        Returns:
            The frame's outcomes, in the order they happened.
        """
        frame = _Frame()
        for collision in self._detect(players, enemies, bullets):
            collision(frame)
        return frame.outcomes

    # --- Detection -------------------------------------------------------

    def _detect(
        self,
        players: Sequence[PlayerTank],
        enemies: Sequence[EnemyTank],
        bullets: Sequence[Bullet],
    ) -> list[_Collision]:
        """Find every collision, in the order they are responded to.

        Bullets come first: a bullet stopped by one thing can't also hit
        another, and a tile a bullet hits is damaged before any tank is
        stopped. Then tanks against tiles and each other, then Power-Ups.
        """
        collisions: list[_Collision] = []
        seen: set[tuple[int, int]] = set()

        def add[A, B](
            respond: Callable[[A, B, _Frame], None], first: A, second: B
        ) -> None:
            # A pair found twice (e.g. the Base is also a bullet-blocking tile)
            # is responded to once, as it was first found.
            if (id(first), id(second)) in seen or (id(second), id(first)) in seen:
                return
            seen.add((id(first), id(second)))
            collisions.append(partial(respond, first, second))

        def overlapping[A: GameObject | Tile, B: GameObject | Tile](
            respond: Callable[[A, B, _Frame], None],
            firsts: Sequence[A],
            seconds: Sequence[B],
        ) -> None:
            for first in firsts:
                for second in seconds:
                    if first.rect.colliderect(second.rect):
                        add(respond, first, second)

        player_bullets = [b for b in bullets if b.owner_type == OwnerType.PLAYER]
        enemy_bullets = [b for b in bullets if b.owner_type == OwnerType.ENEMY]
        bullet_blocking_tiles = self._map.get_bullet_blocking_tiles()
        base = self._map.get_base()
        tanks: list[Tank] = [*players, *enemies]

        overlapping(self._bullet_vs_enemy, player_bullets, enemies)
        overlapping(self._bullet_vs_tile, player_bullets, bullet_blocking_tiles)
        # Swept rects, so bullets heading at each other can't pass through
        # one another between frames.
        for player_bullet in player_bullets:
            for enemy_bullet in enemy_bullets:
                if player_bullet.swept_rect.colliderect(enemy_bullet.swept_rect):
                    add(self._bullet_vs_bullet, player_bullet, enemy_bullet)
        overlapping(self._bullet_vs_tile, enemy_bullets, bullet_blocking_tiles)
        if base is not None:
            overlapping(self._bullet_vs_tile, player_bullets, [base])
            overlapping(self._bullet_vs_tile, enemy_bullets, [base])
        # Player by Player, an Enemy's bullet before a Player's.
        for player in players:
            overlapping(self._bullet_vs_player, enemy_bullets, [player])
            overlapping(self._bullet_vs_player, player_bullets, [player])

        overlapping(self._tank_vs_tile, tanks, self._map.get_blocking_tiles())
        for i, tank in enumerate(tanks):
            overlapping(self._tank_vs_tank, [tank], tanks[i + 1 :])

        overlapping(
            self._player_vs_power_up, players, self._power_up_manager.active_power_ups
        )
        return collisions

    # --- Response --------------------------------------------------------
    # Responded to in the order found. A bullet responds once: once it has
    # stopped, later collisions with it do nothing. A tank is stopped once.

    def _bullet_vs_enemy(self, bullet: Bullet, enemy: EnemyTank, frame: _Frame) -> None:
        if not bullet.active or enemy in frame.destroyed:
            return
        logger.debug(f"Player bullet hit enemy tank (type: {enemy.tank_type})")
        bullet.active = False
        if enemy.is_carrier:
            frame.outcomes.append(CarrierHit(enemy))
        if enemy.take_damage() is not HitResult.ABSORBED:
            logger.info(f"Enemy tank (type: {enemy.tank_type}) destroyed.")
            frame.destroyed.add(enemy)
            frame.outcomes.append(EnemyDestroyed(enemy, by=bullet.owner))

    def _bullet_vs_player(
        self, bullet: Bullet, player: PlayerTank, frame: _Frame
    ) -> None:
        if not bullet.active or bullet.owner is player or player in frame.destroyed:
            return

        if bullet.owner_type == OwnerType.PLAYER:
            bullet.active = False
            if not player.is_invincible:
                player.freeze(FRIENDLY_FIRE_FREEZE_DURATION)
            return

        logger.debug("Enemy bullet hit player tank.")
        bullet.active = False
        if player.take_damage() is not HitResult.ABSORBED:
            logger.info("Player tank destroyed.")
            frame.destroyed.add(player)
            frame.outcomes.append(PlayerDestroyed(player))

    def _bullet_vs_tile(self, bullet: Bullet, tile: Tile, frame: _Frame) -> None:
        # The tile may have been shot away earlier this frame.
        if not bullet.active or not tile.blocks_bullets:
            return

        logger.debug(f"Bullet hit {tile.type.name} tile at ({tile.x}, {tile.y})")
        bullet.active = False
        self._effect_manager.spawn_at_rect(EffectType.SMALL_EXPLOSION, bullet.rect)
        if tile.type == TileType.BASE:
            self._sound_manager.play("explosion")
        else:
            self._sound_manager.play("brick_hit")

        if tile.type == TileType.STEEL:
            if bullet.power_bullet:
                self._map.set_tile_type(tile, TileType.EMPTY)
            return

        if tile.is_destructible:
            self._map.damage_brick(tile, bullet.direction, bullet.rect)
        elif tile.type == TileType.BASE:
            self._map.destroy_base()
            frame.outcomes.append(BaseDestroyed())

    def _bullet_vs_bullet(
        self, bullet_a: Bullet, bullet_b: Bullet, frame: _Frame
    ) -> None:
        if not bullet_a.active or not bullet_b.active:
            return
        logger.debug("Bullet hit bullet. Both deactivated.")
        bullet_a.active = False
        bullet_b.active = False
        self._sound_manager.play("bullet_hit_bullet")

    def _player_vs_power_up(
        self, player: PlayerTank, power_up: PowerUp, frame: _Frame
    ) -> None:
        if player in frame.destroyed:
            return
        power_up_type = self._power_up_manager.collect_power_up(power_up)
        if power_up_type is not None:
            logger.info(f"Player collected power-up: {power_up_type}")
            frame.outcomes.append(PowerUpCollected(power_up_type, player))

    @staticmethod
    def _caused_collision(mover: Tank, other: Tank) -> bool:
        """Check if mover's movement contributed to the collision.

        Compares mover's previous position against other's current
        (post-move) rect. Returns True when the previous position does
        NOT overlap, meaning mover's movement closed the gap.
        """
        return not mover.prev_rect.colliderect(other.rect)

    def _tank_vs_tank(self, tank_a: Tank, tank_b: Tank, frame: _Frame) -> None:
        """Stop whichever tank closed the gap."""
        if tank_a in frame.stopped and tank_b in frame.stopped:
            return
        a_caused = self._caused_collision(tank_a, tank_b)
        b_caused = self._caused_collision(tank_b, tank_a)
        neither = not a_caused and not b_caused

        # Pre-existing overlap (e.g. from spawn): let both tanks move
        # freely so they can separate instead of getting permanently stuck.
        if neither and tank_a.prev_rect.colliderect(tank_b.prev_rect):
            return

        if neither or a_caused:
            self._stop(tank_a)
        if neither or b_caused:
            self._stop(tank_b)
        frame.stopped.update((tank_a, tank_b))

    def _tank_vs_tile(self, tank: Tank, tile: Tile, frame: _Frame) -> None:
        """Stop a tank flush against a tile that blocks it."""
        # The tile may have been shot away earlier this frame.
        if tank in frame.stopped or not tile.blocks_tanks:
            return
        self._stop(tank, tile.rect)
        frame.stopped.add(tank)

    @staticmethod
    def _stop(tank: Tank, obstacle_rect: pygame.Rect | None = None) -> None:
        """Move a tank back (flush against ``obstacle_rect``, if given)."""
        tank.revert_move(obstacle_rect)
        tank.on_movement_blocked()
