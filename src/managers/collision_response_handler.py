from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Type

if TYPE_CHECKING:
    from src.managers.power_up_manager import PowerUpManager
    from src.managers.sound_manager import SoundManager
from loguru import logger
from src.core.bullet import Bullet
from src.core.power_up import PowerUp
from src.core.tank import Tank
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType
from src.utils.constants import (
    EffectType,
    ENEMY_POINTS,
    OwnerType,
    POWERUP_COLLECT_POINTS,
    PowerUpType,
)
from src.core.map import Map
from src.managers.effect_manager import EffectManager
from src.states.game_state import GameState


class CollisionResponseHandler:
    """Handles collision responses using a type-pair handler registry."""

    def __init__(
        self,
        game_map: Map,
        set_game_state: Callable[[GameState], None],
        effect_manager: EffectManager,
        add_score: Callable[[int], None] = lambda _: None,
        power_up_manager: Optional[PowerUpManager] = None,
        sound_manager: Optional[SoundManager] = None,
        on_player_death: Optional[Callable[[PlayerTank], bool]] = None,
    ) -> None:
        self._map = game_map
        self._set_game_state = set_game_state
        self._effect_manager = effect_manager
        self._add_score = add_score
        self._power_up_manager = power_up_manager
        self._sound_manager = sound_manager
        self._on_player_death = on_player_death
        self._collected_power_up_type: Optional[PowerUpType] = None
        self._collected_power_up_player: Optional[PlayerTank] = None

        self._handlers: Dict[Tuple[Type, Type], Callable[[Any, Any, List], bool]] = {
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

    def _play_explosion(self) -> None:
        if self._sound_manager is not None:
            self._sound_manager.play_explosion()

    def _play_brick_hit(self) -> None:
        if self._sound_manager is not None:
            self._sound_manager.play_brick_hit()

    def _play_bullet_hit_bullet(self) -> None:
        if self._sound_manager is not None:
            self._sound_manager.play_bullet_hit_bullet()

    def _play_powerup(self) -> None:
        if self._sound_manager is not None:
            self._sound_manager.play_powerup()

    def process_collisions(self, events: List[Tuple[Any, Any]]) -> List[EnemyTank]:
        """Process collision events and return list of enemies to remove."""
        if not events:
            return []

        processed_bullets: set = set()
        reverted_tanks: set = set()
        enemies_to_remove: List[EnemyTank] = []

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
                if bullet in processed_bullets:
                    continue
                # Also check if the other is a bullet and processed
                other = b if bullet is a else a
                if isinstance(other, Bullet) and other in processed_bullets:
                    continue

                result = handler(a, b, enemies_to_remove)
                if result:
                    processed_bullets.add(bullet)
                    if isinstance(other, Bullet):
                        processed_bullets.add(other)
                # Consumed — do not evaluate as tank collision
                continue

            # Must be before tank block — PlayerTank is a Tank subclass
            if isinstance(a, PowerUp) or isinstance(b, PowerUp):
                handler(a, b, enemies_to_remove)
                continue

            # Tank collisions
            if isinstance(a, Tank) and isinstance(b, Tank):
                if (a not in reverted_tanks or b not in reverted_tanks) and handler(
                    a, b, enemies_to_remove
                ):
                    reverted_tanks.add(a)
                    reverted_tanks.add(b)
            elif isinstance(a, Tank):
                if a not in reverted_tanks and handler(a, b, enemies_to_remove):
                    reverted_tanks.add(a)
            elif isinstance(b, Tank):
                if b not in reverted_tanks and handler(a, b, enemies_to_remove):
                    reverted_tanks.add(b)

        return enemies_to_remove

    def _lookup(self, obj_a: Any, obj_b: Any) -> Tuple[Any, Any, Any]:
        """Look up handler for type pair, trying both orderings."""
        for (type_a, type_b), handler in self._handlers.items():
            if isinstance(obj_a, type_a) and isinstance(obj_b, type_b):
                return handler, obj_a, obj_b
            if isinstance(obj_b, type_a) and isinstance(obj_a, type_b):
                return handler, obj_b, obj_a

        logger.warning(
            f"No collision handler for ({type(obj_a).__name__}, {type(obj_b).__name__})"
        )
        return None, obj_a, obj_b

    def _handle_bullet_vs_enemy(
        self,
        bullet: Bullet,
        enemy: EnemyTank,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if not bullet.active:
            return False
        if bullet.owner_type != OwnerType.PLAYER:
            return False
        logger.debug(f"Player bullet hit enemy tank (type: {enemy.tank_type})")
        bullet.active = False
        destroyed = enemy.take_damage()
        if destroyed:
            logger.info(f"Enemy tank (type: {enemy.tank_type}) destroyed.")
            enemies_to_remove.append(enemy)
            self._add_score(ENEMY_POINTS.get(enemy.tank_type, 0))
            self._effect_manager.spawn(
                EffectType.LARGE_EXPLOSION,
                float(enemy.rect.centerx),
                float(enemy.rect.centery),
            )
            self._play_explosion()
        return True

    def _handle_bullet_vs_player(
        self,
        bullet: Bullet,
        player: PlayerTank,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if not bullet.active:
            return False
        if bullet.owner_type != OwnerType.ENEMY:
            return False
        logger.debug("Enemy bullet hit player tank.")
        bullet.active = False
        if not player.is_invincible:
            destroyed = player.take_damage()
            if destroyed:
                logger.info("Player tank destroyed.")
                self._effect_manager.spawn(
                    EffectType.LARGE_EXPLOSION,
                    float(player.rect.centerx),
                    float(player.rect.centery),
                )
                self._play_explosion()
                if self._on_player_death is not None:
                    if self._on_player_death(player):
                        self._set_game_state(GameState.GAME_OVER)
                else:
                    self._set_game_state(GameState.GAME_OVER)
            else:
                player.respawn()
        return True

    def _handle_bullet_vs_tile(
        self,
        bullet: Bullet,
        tile: Tile,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if not bullet.active:
            return False
        if not tile.blocks_bullets:
            return False

        logger.debug(f"Bullet hit {tile.type.name} tile at ({tile.x}, {tile.y})")
        bullet.active = False
        self._effect_manager.spawn(
            EffectType.SMALL_EXPLOSION,
            float(bullet.rect.centerx),
            float(bullet.rect.centery),
        )
        if tile.type == TileType.BASE:
            self._play_explosion()
        else:
            self._play_brick_hit()

        if tile.type == TileType.STEEL:
            if bullet.power_bullet:
                self._map.set_tile_type(tile, TileType.EMPTY)
            return True

        if tile.is_destructible:
            self._map.damage_brick(tile, bullet.direction, bullet.rect)
        elif tile.type == TileType.BASE:
            self._map.destroy_base()
            self._set_game_state(GameState.GAME_OVER)
        return True

    def _handle_bullet_vs_bullet(
        self,
        bullet_a: Bullet,
        bullet_b: Bullet,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if not bullet_a.active or not bullet_b.active:
            return False
        if bullet_a == bullet_b:
            return False
        logger.debug("Bullet hit bullet. Both deactivated.")
        bullet_a.active = False
        bullet_b.active = False
        self._play_bullet_hit_bullet()
        return True

    def _handle_player_vs_powerup(
        self,
        player: PlayerTank,
        power_up: PowerUp,
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if self._power_up_manager is None:
            return False
        power_up_type = self._power_up_manager.collect_power_up(power_up)
        if power_up_type is not None:
            self._add_score(POWERUP_COLLECT_POINTS)
            self._play_powerup()
            logger.info(f"Player collected power-up: {power_up_type.value}")
            self._collected_power_up_type = power_up_type
            self._collected_power_up_player = player
        return True

    def consume_collected_power_up(
        self,
    ) -> tuple[Optional[PowerUpType], Optional[PlayerTank]]:
        """Return and clear the collected power-up type and player (one-shot read).

        Returns:
            Tuple of (power_up_type, collecting_player). Both None when nothing
            was collected.
        """
        result_type = self._collected_power_up_type
        result_player = self._collected_power_up_player
        self._collected_power_up_type = None
        self._collected_power_up_player = None
        return result_type, result_player

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
        enemies_to_remove: List[EnemyTank],
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
        enemies_to_remove: List[EnemyTank],
    ) -> bool:
        if tile.blocks_tanks:
            tank.revert_move(tile.rect)
            tank.on_movement_blocked()
            return True
        return False
