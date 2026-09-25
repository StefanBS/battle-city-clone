from __future__ import annotations
from typing import TYPE_CHECKING, Any
from collections.abc import Callable
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from src.managers.power_up_manager import PowerUpManager
    from src.managers.sound_manager import SoundManager
from loguru import logger
from src.core.bullet import Bullet
from src.core.power_up import PowerUp
from src.core.tank import HitResult, Tank
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType
from src.utils.constants import (
    EffectType,
    FRIENDLY_FIRE_FREEZE_DURATION,
    OwnerType,
)
from src.core.map import Map
from src.managers.effect_manager import EffectManager
from src.managers.outcomes import (
    BaseDestroyed,
    CarrierHit,
    CollisionOutcome,
    EnemyDestroyed,
    PlayerDestroyed,
    PowerUpCollected,
)


@dataclass
class _Frame:
    """What one ``process_collisions`` call has produced so far."""

    outcomes: list[CollisionOutcome] = field(default_factory=list)
    # Tanks destroyed earlier in the frame: bullets pass through them.
    destroyed: set[Tank] = field(default_factory=set)


class CollisionResponseHandler:
    """Handles collision responses using a type-pair handler registry.

    Physics that later events in the same frame depend on (bullets, reverts,
    tiles, damage) is applied immediately; game-level consequences are
    returned as outcomes for ``GameManager`` to apply.
    """

    def __init__(
        self,
        game_map: Map,
        effect_manager: EffectManager,
        power_up_manager: PowerUpManager | None = None,
        sound_manager: SoundManager | None = None,
    ) -> None:
        self._map = game_map
        self._effect_manager = effect_manager
        self._power_up_manager = power_up_manager
        self._sound_manager = sound_manager

        self._handlers: dict[tuple[type, type], Callable[[Any, Any, _Frame], bool]] = {
            (Bullet, EnemyTank): self._handle_bullet_vs_enemy,
            (Bullet, PlayerTank): self._handle_bullet_vs_player,
            (Bullet, Tile): self._handle_bullet_vs_tile,
            (Bullet, Bullet): self._handle_bullet_vs_bullet,
            (PlayerTank, PowerUp): self._handle_player_vs_powerup,
            (PlayerTank, EnemyTank): self._handle_tank_vs_tank,
            (PlayerTank, PlayerTank): self._handle_tank_vs_tank,
            (EnemyTank, EnemyTank): self._handle_tank_vs_tank,
            (PlayerTank, Tile): self._handle_tank_vs_tile,
            (EnemyTank, Tile): self._handle_tank_vs_tile,
        }

    def _play(self, name: str) -> None:
        if self._sound_manager is not None:
            self._sound_manager.play(name)

    def process_collisions(
        self, events: list[tuple[Any, Any]]
    ) -> list[CollisionOutcome]:
        """Process collision events and return their outcomes in event order."""
        if not events:
            return []

        processed_bullets: set = set()
        reverted_tanks: set = set()
        frame = _Frame()

        for obj_a, obj_b in events:
            handler, a, b = self._lookup(obj_a, obj_b)
            if handler is None:
                continue

            # Bullet events must be consumed before tank/powerup blocks
            # to prevent a bullet-tile hit from also triggering tank revert.
            is_bullet_pair = isinstance(a, Bullet) or isinstance(b, Bullet)

            if is_bullet_pair:
                # Identify the bullet(s)
                bullet = a if isinstance(a, Bullet) else b
                if not bullet.active or bullet in processed_bullets:
                    continue
                # Also check if the other is a bullet and processed/inactive
                other = b if bullet is a else a
                if isinstance(other, Bullet) and (
                    not other.active or other in processed_bullets
                ):
                    continue

                result = handler(a, b, frame)
                if result:
                    processed_bullets.add(bullet)
                    if isinstance(other, Bullet):
                        processed_bullets.add(other)
                # Consumed — do not evaluate as tank collision
                continue

            # Must be before tank block — PlayerTank is a Tank subclass
            if isinstance(a, PowerUp) or isinstance(b, PowerUp):
                handler(a, b, frame)
                continue

            # Tank collisions
            if isinstance(a, Tank) and isinstance(b, Tank):
                if (a not in reverted_tanks or b not in reverted_tanks) and handler(
                    a, b, frame
                ):
                    reverted_tanks.add(a)
                    reverted_tanks.add(b)
            elif isinstance(a, Tank):
                if a not in reverted_tanks and handler(a, b, frame):
                    reverted_tanks.add(a)
            elif isinstance(b, Tank):
                if b not in reverted_tanks and handler(a, b, frame):
                    reverted_tanks.add(b)

        return frame.outcomes

    def _lookup(self, obj_a: Any, obj_b: Any) -> tuple[Any, Any, Any]:
        """Look up handler for type pair, trying both orderings.

        All participating types are concrete leaves (PlayerTank, EnemyTank,
        Bullet, Tile, PowerUp), so exact-class dispatch via ``__class__`` is
        correct and avoids scanning the handler table with ``isinstance`` on
        the per-event hot path. ``__class__`` is used rather than ``type()``
        so MagicMock(spec=X) test doubles resolve to the spec class.
        """
        cls_a, cls_b = obj_a.__class__, obj_b.__class__
        handler = self._handlers.get((cls_a, cls_b))
        if handler is not None:
            return handler, obj_a, obj_b
        handler = self._handlers.get((cls_b, cls_a))
        if handler is not None:
            return handler, obj_b, obj_a

        logger.warning(f"No collision handler for ({cls_a.__name__}, {cls_b.__name__})")
        return None, obj_a, obj_b

    def _handle_bullet_vs_enemy(
        self,
        bullet: Bullet,
        enemy: EnemyTank,
        frame: _Frame,
    ) -> bool:
        if bullet.owner_type != OwnerType.PLAYER or enemy in frame.destroyed:
            return False
        logger.debug(f"Player bullet hit enemy tank (type: {enemy.tank_type})")
        bullet.active = False
        if enemy.is_carrier:
            frame.outcomes.append(CarrierHit(enemy))
        if enemy.take_damage() is not HitResult.ABSORBED:
            logger.info(f"Enemy tank (type: {enemy.tank_type}) destroyed.")
            frame.destroyed.add(enemy)
            frame.outcomes.append(EnemyDestroyed(enemy, by=bullet.owner))
        return True

    def _handle_bullet_vs_player(
        self,
        bullet: Bullet,
        player: PlayerTank,
        frame: _Frame,
    ) -> bool:
        if getattr(bullet, "owner", None) is player or player in frame.destroyed:
            return False

        if bullet.owner_type == OwnerType.PLAYER:
            bullet.active = False
            if not player.is_invincible:
                player.freeze(FRIENDLY_FIRE_FREEZE_DURATION)
            return True

        if bullet.owner_type != OwnerType.ENEMY:
            return False

        logger.debug("Enemy bullet hit player tank.")
        bullet.active = False
        if player.take_damage() is not HitResult.ABSORBED:
            logger.info("Player tank destroyed.")
            frame.destroyed.add(player)
            frame.outcomes.append(PlayerDestroyed(player))
        return True

    def _handle_bullet_vs_tile(
        self,
        bullet: Bullet,
        tile: Tile,
        frame: _Frame,
    ) -> bool:
        if not tile.blocks_bullets:
            return False

        logger.debug(f"Bullet hit {tile.type.name} tile at ({tile.x}, {tile.y})")
        bullet.active = False
        self._effect_manager.spawn_at_rect(EffectType.SMALL_EXPLOSION, bullet.rect)
        if tile.type == TileType.BASE:
            self._play("explosion")
        else:
            self._play("brick_hit")

        if tile.type == TileType.STEEL:
            if bullet.power_bullet:
                self._map.set_tile_type(tile, TileType.EMPTY)
            return True

        if tile.is_destructible:
            self._map.damage_brick(tile, bullet.direction, bullet.rect)
        elif tile.type == TileType.BASE:
            self._map.destroy_base()
            frame.outcomes.append(BaseDestroyed())
        return True

    def _handle_bullet_vs_bullet(
        self,
        bullet_a: Bullet,
        bullet_b: Bullet,
        frame: _Frame,
    ) -> bool:
        logger.debug("Bullet hit bullet. Both deactivated.")
        bullet_a.active = False
        bullet_b.active = False
        self._play("bullet_hit_bullet")
        return True

    def _handle_player_vs_powerup(
        self,
        player: PlayerTank,
        power_up: PowerUp,
        frame: _Frame,
    ) -> bool:
        if self._power_up_manager is None or player in frame.destroyed:
            return False
        power_up_type = self._power_up_manager.collect_power_up(power_up)
        if power_up_type is not None:
            logger.info(f"Player collected power-up: {power_up_type}")
            frame.outcomes.append(PowerUpCollected(power_up_type, player))
        return True

    @staticmethod
    def _caused_collision(mover: Tank, other: Tank) -> bool:
        """Check if mover's movement contributed to the collision.

        Compares mover's previous position against other's current
        (post-move) rect. Returns True when the previous position does
        NOT overlap, meaning mover's movement closed the gap.
        """
        return not mover.prev_rect.colliderect(other.rect)

    def _handle_tank_vs_tank(
        self,
        tank_a: Tank,
        tank_b: Tank,
        frame: _Frame,
    ) -> bool:
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

    def _handle_tank_vs_tile(
        self,
        tank: Tank,
        tile: Tile,
        frame: _Frame,
    ) -> bool:
        if tile.blocks_tanks:
            tank.revert_move(tile.rect)
            tank.on_movement_blocked()
            return True
        return False
