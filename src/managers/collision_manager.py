"""One frame's collisions: found, responded to, and returned as outcomes.

See ``docs/adr/0003-collision-response-returns-outcomes.md``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from loguru import logger

from src.core.bullet import Bullet
from src.core.enemy_tank import EnemyTank
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


class _Kind(Enum):
    """What collided with what; the first object of the pair comes first."""

    BULLET_VS_ENEMY = auto()
    BULLET_VS_PLAYER = auto()
    BULLET_VS_TILE = auto()
    BULLET_VS_BULLET = auto()
    TANK_VS_TILE = auto()
    TANK_VS_TANK = auto()
    PLAYER_VS_POWER_UP = auto()


_BULLET_KINDS = frozenset(
    {
        _Kind.BULLET_VS_ENEMY,
        _Kind.BULLET_VS_PLAYER,
        _Kind.BULLET_VS_TILE,
        _Kind.BULLET_VS_BULLET,
    }
)

_Event = tuple[_Kind, Any, Any]


@dataclass
class _Frame:
    """What one ``resolve`` call has produced so far."""

    outcomes: list[BattleOutcome] = field(default_factory=list)
    # Tanks destroyed earlier in the frame: bullets pass through them.
    destroyed: set[Tank] = field(default_factory=set)
    # Tanks already stopped this frame, by a tile or another tank.
    reverted: set[Tank] = field(default_factory=set)


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
        return self._respond(self._detect(players, enemies, bullets))

    # --- Detection -------------------------------------------------------

    def _detect(
        self,
        players: Sequence[PlayerTank],
        enemies: Sequence[EnemyTank],
        bullets: Sequence[Bullet],
    ) -> list[_Event]:
        """Find every collision, in the order they are responded to.

        Bullets come first: a bullet stopped by one thing can't also hit
        another, and a tile a bullet hits is damaged before any tank is
        stopped. Then tanks against tiles and each other, then Power-Ups.
        """
        events: list[_Event] = []
        seen: set[tuple[int, int]] = set()

        def add(kind: _Kind, a: Any, b: Any) -> None:
            # A pair found twice (e.g. the Base is also a bullet-blocking tile)
            # is responded to once, as the kind it was first found as.
            if (id(a), id(b)) in seen or (id(b), id(a)) in seen:
                return
            seen.add((id(a), id(b)))
            events.append((kind, a, b))

        def overlapping(
            kind: _Kind, group_a: Sequence[Any], group_b: Sequence[Any]
        ) -> None:
            for a in group_a:
                for b in group_b:
                    if a.rect.colliderect(b.rect):
                        add(kind, a, b)

        player_bullets = [b for b in bullets if b.owner_type == OwnerType.PLAYER]
        enemy_bullets = [b for b in bullets if b.owner_type == OwnerType.ENEMY]
        bullet_blocking_tiles = self._map.get_bullet_blocking_tiles()
        base = self._map.get_base()
        tanks: list[Tank] = [*players, *enemies]

        overlapping(_Kind.BULLET_VS_ENEMY, player_bullets, enemies)
        overlapping(_Kind.BULLET_VS_TILE, player_bullets, bullet_blocking_tiles)
        # Swept rects, so bullets heading at each other can't pass through
        # one another between frames.
        for player_bullet in player_bullets:
            for enemy_bullet in enemy_bullets:
                if player_bullet.swept_rect.colliderect(enemy_bullet.swept_rect):
                    add(_Kind.BULLET_VS_BULLET, player_bullet, enemy_bullet)
        overlapping(_Kind.BULLET_VS_TILE, enemy_bullets, bullet_blocking_tiles)
        if base is not None:
            overlapping(_Kind.BULLET_VS_TILE, player_bullets, [base])
            overlapping(_Kind.BULLET_VS_TILE, enemy_bullets, [base])
        for player in players:
            overlapping(_Kind.BULLET_VS_PLAYER, enemy_bullets, [player])
            overlapping(_Kind.BULLET_VS_PLAYER, player_bullets, [player])

        overlapping(_Kind.TANK_VS_TILE, tanks, self._map.get_blocking_tiles())
        for i, tank_a in enumerate(tanks):
            overlapping(_Kind.TANK_VS_TANK, [tank_a], tanks[i + 1 :])

        overlapping(
            _Kind.PLAYER_VS_POWER_UP, players, self._power_up_manager.active_power_ups
        )
        return events

    # --- Response --------------------------------------------------------

    def _respond(self, events: list[_Event]) -> list[BattleOutcome]:
        """Respond to each collision in order, skipping those already settled.

        A bullet responds once: after it has stopped, later collisions with it
        are skipped. A tank is stopped once: a tank already stopped this frame
        isn't stopped again.
        """
        frame = _Frame()
        for kind, a, b in events:
            if kind in _BULLET_KINDS:
                if not a.active or (isinstance(b, Bullet) and not b.active):
                    continue
                self._respond_to_bullet(kind, a, b, frame)
            elif kind is _Kind.PLAYER_VS_POWER_UP:
                self._player_vs_power_up(a, b, frame)
            elif kind is _Kind.TANK_VS_TANK:
                if (a not in frame.reverted or b not in frame.reverted) and (
                    self._tank_vs_tank(a, b)
                ):
                    frame.reverted.update((a, b))
            elif kind is _Kind.TANK_VS_TILE:
                if a not in frame.reverted and self._tank_vs_tile(a, b):
                    frame.reverted.add(a)
        return frame.outcomes

    def _respond_to_bullet(
        self, kind: _Kind, bullet: Bullet, other: Any, frame: _Frame
    ) -> None:
        match kind:
            case _Kind.BULLET_VS_ENEMY:
                self._bullet_vs_enemy(bullet, other, frame)
            case _Kind.BULLET_VS_PLAYER:
                self._bullet_vs_player(bullet, other, frame)
            case _Kind.BULLET_VS_TILE:
                self._bullet_vs_tile(bullet, other, frame)
            case _Kind.BULLET_VS_BULLET:
                self._bullet_vs_bullet(bullet, other)

    def _bullet_vs_enemy(self, bullet: Bullet, enemy: EnemyTank, frame: _Frame) -> None:
        if enemy in frame.destroyed:
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
        if bullet.owner is player or player in frame.destroyed:
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
        if not tile.blocks_bullets:
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

    def _bullet_vs_bullet(self, bullet_a: Bullet, bullet_b: Bullet) -> None:
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

    def _tank_vs_tank(self, tank_a: Tank, tank_b: Tank) -> bool:
        """Stop whichever tank closed the gap; return whether any was stopped."""
        a_caused = self._caused_collision(tank_a, tank_b)
        b_caused = self._caused_collision(tank_b, tank_a)
        neither = not a_caused and not b_caused

        # Pre-existing overlap (e.g. from spawn): let both tanks move
        # freely so they can separate instead of getting permanently stuck.
        if neither and tank_a.prev_rect.colliderect(tank_b.prev_rect):
            return False

        if neither or a_caused:
            tank_a.revert_move()
            tank_a.on_movement_blocked()
        if neither or b_caused:
            tank_b.revert_move()
            tank_b.on_movement_blocked()
        return True

    @staticmethod
    def _tank_vs_tile(tank: Tank, tile: Tile) -> bool:
        """Stop a tank flush against a tile that blocks it."""
        if not tile.blocks_tanks:
            return False
        tank.revert_move(tile.rect)
        tank.on_movement_blocked()
        return True
