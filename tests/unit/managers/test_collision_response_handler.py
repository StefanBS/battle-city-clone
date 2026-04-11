import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.collision_response_handler import CollisionResponseHandler
from src.managers.effect_manager import EffectManager
from src.managers.power_up_manager import PowerUpManager
from src.core.bullet import Bullet
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType
from src.core.map import Map
from src.core.power_up import PowerUp
from src.states.game_state import GameState
from src.utils.constants import (
    Direction,
    EffectType,
    TankType,
    TILE_SIZE,
    PowerUpType,
    POWERUP_COLLECT_POINTS,
)


@pytest.fixture
def mock_map():
    mock = MagicMock(spec=Map)
    mock.set_tile_type = MagicMock()
    return mock


@pytest.fixture
def mock_effect_manager():
    return MagicMock(spec=EffectManager)


@pytest.fixture
def mock_add_score():
    return MagicMock()


@pytest.fixture
def handler(mock_map, mock_effect_manager, mock_add_score):
    set_state = MagicMock()
    return CollisionResponseHandler(
        game_map=mock_map,
        set_game_state=set_state,
        effect_manager=mock_effect_manager,
        add_score=mock_add_score,
    )


@pytest.fixture
def mock_bullet():
    b = MagicMock(spec=Bullet)
    b.active = True
    b.owner_type = "player"
    b.owner = MagicMock()
    b.rect = pygame.Rect(0, 0, 2, 2)
    return b


@pytest.fixture
def mock_enemy():
    e = MagicMock(spec=EnemyTank)
    e.owner_type = "enemy"
    e.tank_type = "basic"
    e.take_damage = MagicMock(return_value=False)
    e.on_movement_blocked = MagicMock()
    e.revert_move = MagicMock()
    e.rect = pygame.Rect(0, 0, 32, 32)
    return e


@pytest.fixture
def mock_player():
    p = MagicMock(spec=PlayerTank)
    p.owner_type = "player"
    p.is_invincible = False
    p.take_damage = MagicMock(return_value=False)
    p.respawn = MagicMock()
    p.revert_move = MagicMock()
    p.rect = pygame.Rect(0, 0, 32, 32)
    return p


@pytest.fixture
def mock_tile():
    t = MagicMock(spec=Tile)
    t.type = TileType.BRICK
    t.blocks_tanks = True
    t.blocks_bullets = True
    t.x = 0
    t.y = 0
    t.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
    return t


class TestDispatch:
    def test_lookup_forward_order(self, handler, mock_bullet, mock_enemy):
        """Test registry finds handler with (Bullet, EnemyTank) order."""
        mock_bullet.owner_type = "player"
        handler.process_collisions([(mock_bullet, mock_enemy)])
        assert not mock_bullet.active

    def test_lookup_swapped_order(self, handler, mock_bullet, mock_enemy):
        """Test registry finds handler with (EnemyTank, Bullet) order."""
        mock_bullet.owner_type = "player"
        handler.process_collisions([(mock_enemy, mock_bullet)])
        assert not mock_bullet.active

    def test_unregistered_pair_skipped(self, handler):
        """Test unregistered type pair logs warning and is skipped."""
        obj_a = MagicMock()
        obj_b = MagicMock()
        type(obj_a).__name__ = "Unknown"
        type(obj_b).__name__ = "Unknown"
        # Should not raise
        result = handler.process_collisions([(obj_a, obj_b)])
        assert result == []


class TestBulletVsEnemy:
    def test_player_bullet_damages_enemy(self, handler, mock_bullet, mock_enemy):
        mock_bullet.owner_type = "player"
        handler.process_collisions([(mock_bullet, mock_enemy)])
        assert not mock_bullet.active
        mock_enemy.take_damage.assert_called_once()

    def test_player_bullet_destroys_enemy(self, handler, mock_bullet, mock_enemy):
        mock_bullet.owner_type = "player"
        mock_enemy.take_damage.return_value = True
        enemies = handler.process_collisions([(mock_bullet, mock_enemy)])
        assert mock_enemy in enemies

    def test_enemy_bullet_does_not_damage_enemy(self, handler, mock_enemy):
        """Friendly fire — enemy bullet should not damage enemy."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        handler.process_collisions([(bullet, mock_enemy)])
        mock_enemy.take_damage.assert_not_called()
        assert bullet.active  # Bullet not consumed


class TestBulletVsPlayer:
    def test_enemy_bullet_damages_player(self, handler, mock_player):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        handler.process_collisions([(bullet, mock_player)])
        assert not bullet.active
        mock_player.take_damage.assert_called_once()
        mock_player.respawn.assert_called_once()

    def test_enemy_bullet_kills_player(self, handler, mock_player):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        bullet.rect = pygame.Rect(0, 0, 2, 2)
        mock_player.take_damage.return_value = True
        handler.process_collisions([(bullet, mock_player)])
        handler._set_game_state.assert_called_with(GameState.GAME_OVER)
        mock_player.respawn.assert_not_called()

    def test_bullet_vs_invincible_player(self, handler, mock_player):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        mock_player.is_invincible = True
        handler.process_collisions([(bullet, mock_player)])
        assert not bullet.active
        mock_player.take_damage.assert_not_called()

    def test_player_bullet_does_not_damage_player(self, handler, mock_player):
        """Friendly fire — player bullet should not damage player."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "player"
        bullet.owner = MagicMock()
        handler.process_collisions([(bullet, mock_player)])
        mock_player.take_damage.assert_not_called()
        assert bullet.active


class TestBulletVsTile:
    """Bullet-vs-tile collision tests.

    Each tile is an 8x8 unit rendered at SUB_TILE_SIZE (16x16).
    Full bricks become half-bricks on first hit, then destroyed on second.
    """

    def test_bullet_damages_brick(self, handler, mock_map):
        """Bullet hitting a brick tile calls damage_brick with direction."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.power_bullet = False
        bullet.rect = pygame.Rect(64, 64, 4, 4)
        bullet.direction = Direction.RIGHT
        tile = Tile(
            TileType.BRICK,
            4,
            4,
            blocks_tanks=True,
            blocks_bullets=True,
            is_destructible=True,
        )
        handler.process_collisions([(bullet, tile)])
        assert not bullet.active
        mock_map.damage_brick.assert_called_once_with(tile, "right", bullet.rect)

    def test_bullet_destroys_base(self, handler, mock_map):
        """Bullet hitting base triggers destroy_base and GAME_OVER."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.power_bullet = False
        bullet.rect = pygame.Rect(0, 0, 4, 4)
        bullet.direction = Direction.DOWN
        tile = MagicMock(spec=Tile)
        tile.type = TileType.BASE
        tile.blocks_bullets = True
        tile.is_destructible = False
        tile.x, tile.y = 0, 0
        handler.process_collisions([(bullet, tile)])
        assert not bullet.active
        mock_map.destroy_base.assert_called_once()
        handler._set_game_state.assert_called_with(GameState.GAME_OVER)

    # -- Non-brick tiles --

    def test_bullet_stops_at_steel(self, handler, mock_map):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.power_bullet = False
        bullet.rect = pygame.Rect(0, 0, 2, 2)
        tile = MagicMock(spec=Tile)
        tile.type = TileType.STEEL
        tile.blocks_bullets = True
        tile.x, tile.y = 0, 0
        handler.process_collisions([(bullet, tile)])
        assert not bullet.active
        mock_map.set_tile_type.assert_not_called()


class TestBulletVsBullet:
    def test_both_deactivated(self, handler):
        b1 = MagicMock(spec=Bullet)
        b2 = MagicMock(spec=Bullet)
        b1.active = True
        b1.owner = MagicMock()
        b1.rect = pygame.Rect(0, 0, 2, 2)
        b2.active = True
        b2.owner = MagicMock()
        b2.rect = pygame.Rect(2, 0, 2, 2)
        handler.process_collisions([(b1, b2)])
        assert not b1.active
        assert not b2.active


class TestTankVsTank:
    """Tank-vs-tank collision tests using real tank objects."""

    MAP_PX = 16 * TILE_SIZE

    def _make_player(self, mock_texture_manager, x, y):
        """Create a real PlayerTank at the given position."""
        tank = PlayerTank(
            x,
            y,
            TILE_SIZE,
            mock_texture_manager,
            map_width_px=self.MAP_PX,
            map_height_px=self.MAP_PX,
        )
        return tank

    def _make_enemy(self, mock_texture_manager, x, y):
        """Create a real EnemyTank at the given position."""
        tank = EnemyTank(
            x,
            y,
            TILE_SIZE,
            mock_texture_manager,
            tank_type=TankType.BASIC,
            map_width_px=self.MAP_PX,
            map_height_px=self.MAP_PX,
        )
        return tank

    @staticmethod
    def _simulate_move(tank, dx, dy, dt=1.0 / 60):
        """Move tank and set up prev position as Tank.update() would."""
        tank.prev_x, tank.prev_y = tank.x, tank.y
        tank._move(dx, dy, dt)

    def test_both_moving_toward_each_other(self, handler, mock_texture_manager):
        """Both tanks moving toward each other: both reverted."""
        player = self._make_player(mock_texture_manager, 96, 128)
        enemy = self._make_enemy(mock_texture_manager, 96, 96)
        enemy.direction = Direction.DOWN
        self._simulate_move(player, 0, -1)
        self._simulate_move(enemy, 0, 1)
        handler.process_collisions([(player, enemy)])
        # Both should be snapped back to prev positions
        assert player.x == player.prev_x and player.y == player.prev_y
        assert enemy.x == enemy.prev_x and enemy.y == enemy.prev_y

    def test_only_aggressor_reverted(self, handler, mock_texture_manager):
        """Stationary enemy is not reverted when player moves into it."""
        player = self._make_player(mock_texture_manager, 96, 128)
        enemy = self._make_enemy(mock_texture_manager, 96, 96)
        enemy_pos_before = (enemy.x, enemy.y)
        self._simulate_move(player, 0, -1)
        # Enemy didn't move (prev == current)
        enemy.prev_x, enemy.prev_y = enemy.x, enemy.y
        handler.process_collisions([(player, enemy)])
        assert player.x == player.prev_x and player.y == player.prev_y
        assert (enemy.x, enemy.y) == enemy_pos_before

    def test_perpendicular_tank_not_reverted(self, handler, mock_texture_manager):
        """Enemy moving perpendicular to collision axis keeps its move."""
        player = self._make_player(mock_texture_manager, 96, 128)
        enemy = self._make_enemy(mock_texture_manager, 96, 96)
        enemy.direction = Direction.RIGHT
        self._simulate_move(player, 0, -1)
        self._simulate_move(enemy, 1, 0)
        enemy_pos_after_move = (enemy.x, enemy.y)
        handler.process_collisions([(player, enemy)])
        # Player reverted, enemy kept its perpendicular movement
        assert player.x == player.prev_x and player.y == player.prev_y
        assert (enemy.x, enemy.y) == enemy_pos_after_move

    def test_enemy_vs_enemy_both_moving_toward(self, handler, mock_texture_manager):
        """Two enemies moving toward each other: both reverted."""
        e1 = self._make_enemy(mock_texture_manager, 96, 96)
        e2 = self._make_enemy(mock_texture_manager, 128, 96)
        e1.direction = Direction.RIGHT
        e2.direction = Direction.LEFT
        self._simulate_move(e1, 1, 0)
        self._simulate_move(e2, -1, 0)
        handler.process_collisions([(e1, e2)])
        assert e1.x == e1.prev_x and e1.y == e1.prev_y
        assert e2.x == e2.prev_x and e2.y == e2.prev_y

    def test_pre_existing_overlap_allows_movement(self, handler, mock_texture_manager):
        """When tanks are already overlapping (e.g. from spawn), neither
        should be reverted — both must be free to move apart."""
        e1 = self._make_enemy(mock_texture_manager, 100, 100)
        e2 = self._make_enemy(mock_texture_manager, 100, 100)
        e1.direction = Direction.LEFT
        e2.direction = Direction.RIGHT
        self._simulate_move(e1, -1, 0)
        self._simulate_move(e2, 1, 0)
        e1_pos_after_move = (e1.x, e1.y)
        e2_pos_after_move = (e2.x, e2.y)
        handler.process_collisions([(e1, e2)])
        # Neither should be reverted — they're moving apart
        assert (e1.x, e1.y) == e1_pos_after_move
        assert (e2.x, e2.y) == e2_pos_after_move

    def test_pre_existing_overlap_no_blocked_directions(
        self, handler, mock_texture_manager
    ):
        """Pre-existing overlap should not add blocked directions,
        so tanks don't get permanently stuck."""
        e1 = self._make_enemy(mock_texture_manager, 100, 100)
        e2 = self._make_enemy(mock_texture_manager, 100, 100)
        e1.prev_x, e1.prev_y = e1.x, e1.y
        e2.prev_x, e2.prev_y = e2.x, e2.y
        handler.process_collisions([(e1, e2)])
        assert len(e1._blocked_directions) == 0
        assert len(e2._blocked_directions) == 0

    def test_cornered_enemy_blocked_direction_recorded(
        self, handler, mock_texture_manager, mock_tile
    ):
        """When a cornered enemy gets tile + tank collisions, its
        blocked direction is recorded from the tile hit."""
        mock_tile.type = TileType.STEEL
        mock_tile.rect = pygame.Rect(68, 100, TILE_SIZE, TILE_SIZE)
        enemy = self._make_enemy(mock_texture_manager, 100, 100)
        enemy.direction = Direction.LEFT
        enemy.prev_x, enemy.prev_y = enemy.x, enemy.y
        pusher = self._make_player(mock_texture_manager, 130, 100)
        self._simulate_move(pusher, -1, 0)
        handler.process_collisions(
            [
                (enemy, mock_tile),
                (pusher, enemy),
            ]
        )
        # Enemy's LEFT direction should be recorded as blocked
        assert Direction.LEFT in enemy._blocked_directions


class TestTankVsTile:
    def test_player_reverted_on_blocking_tile(self, handler, mock_player, mock_tile):
        mock_tile.type = TileType.STEEL
        mock_tile.blocks_tanks = True
        handler.process_collisions([(mock_player, mock_tile)])
        mock_player.revert_move.assert_called_once_with(mock_tile.rect)

    def test_enemy_reverted_and_wall_hit(self, handler, mock_enemy, mock_tile):
        mock_tile.type = TileType.STEEL
        mock_tile.blocks_tanks = True
        handler.process_collisions([(mock_enemy, mock_tile)])
        mock_enemy.revert_move.assert_called_once_with(mock_tile.rect)
        mock_enemy.on_movement_blocked.assert_called_once()

    def test_non_blocking_tile_does_not_revert(self, handler, mock_player, mock_tile):
        mock_tile.type = TileType.BUSH
        mock_tile.blocks_tanks = False
        handler.process_collisions([(mock_player, mock_tile)])
        mock_player.revert_move.assert_not_called()


class TestTracking:
    def test_processed_bullet_not_reprocessed(self, handler, mock_enemy):
        """Same bullet in two events should only be processed once."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "player"
        bullet.owner = MagicMock()
        enemy2 = MagicMock(spec=EnemyTank)
        enemy2.take_damage = MagicMock(return_value=False)
        enemy2.owner_type = "enemy"
        handler.process_collisions(
            [
                (bullet, mock_enemy),
                (bullet, enemy2),
            ]
        )
        # Only first enemy should be damaged
        mock_enemy.take_damage.assert_called_once()
        enemy2.take_damage.assert_not_called()

    def test_reverted_tank_not_re_reverted(self, handler, mock_player):
        """Tank hitting two tiles should only revert once."""
        tile1 = MagicMock(spec=Tile)
        tile1.type = TileType.STEEL
        tile1.blocks_tanks = True
        tile1.x, tile1.y = 0, 0
        tile1.rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        tile2 = MagicMock(spec=Tile)
        tile2.type = TileType.BRICK
        tile2.blocks_tanks = True
        tile2.x, tile2.y = 32, 0
        tile2.rect = pygame.Rect(32, 0, TILE_SIZE, TILE_SIZE)
        handler.process_collisions(
            [
                (mock_player, tile1),
                (mock_player, tile2),
            ]
        )
        mock_player.revert_move.assert_called_once()


class TestExplosionEffects:
    def test_bullet_vs_brick_spawns_small_explosion(
        self, handler, mock_map, mock_effect_manager
    ):
        tile = Tile(
            TileType.BRICK,
            4,
            4,
            blocks_tanks=True,
            blocks_bullets=True,
            is_destructible=True,
        )
        mock_map.get_tile_at.return_value = Tile(TileType.EMPTY, 4, 5)
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.direction = Direction.RIGHT
        bullet.rect = pygame.Rect(64, 66, 2, 2)
        handler.process_collisions([(bullet, tile)])
        mock_effect_manager.spawn.assert_called_once_with(
            EffectType.SMALL_EXPLOSION, 65.0, 67.0
        )

    def test_bullet_vs_steel_spawns_small_explosion(self, handler, mock_effect_manager):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.power_bullet = False
        bullet.rect = pygame.Rect(50, 50, 2, 2)
        tile = MagicMock(spec=Tile)
        tile.type = TileType.STEEL
        tile.blocks_bullets = True
        tile.is_destructible = False
        tile.x, tile.y = 0, 0
        handler.process_collisions([(bullet, tile)])
        mock_effect_manager.spawn.assert_called_once_with(
            EffectType.SMALL_EXPLOSION, 51.0, 51.0
        )

    def test_bullet_vs_base_spawns_small_explosion(
        self, handler, mock_map, mock_effect_manager
    ):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = MagicMock()
        bullet.rect = pygame.Rect(50, 50, 2, 2)
        tile = MagicMock(spec=Tile)
        tile.type = TileType.BASE
        tile.blocks_bullets = True
        tile.is_destructible = False
        tile.x, tile.y = 0, 0
        handler.process_collisions([(bullet, tile)])
        mock_effect_manager.spawn.assert_called_once_with(
            EffectType.SMALL_EXPLOSION, 51.0, 51.0
        )

    def test_enemy_destroyed_spawns_large_explosion(self, handler, mock_effect_manager):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "player"
        bullet.owner = MagicMock()
        bullet.rect = pygame.Rect(50, 50, 2, 2)
        enemy = MagicMock(spec=EnemyTank)
        enemy.owner_type = "enemy"
        enemy.tank_type = "basic"
        enemy.take_damage = MagicMock(return_value=True)
        enemy.rect = pygame.Rect(100, 100, 32, 32)
        handler.process_collisions([(bullet, enemy)])
        mock_effect_manager.spawn.assert_called_once_with(
            EffectType.LARGE_EXPLOSION, 116.0, 116.0
        )

    def test_bullet_vs_bullet_no_explosion(self, handler, mock_effect_manager):
        b1 = MagicMock(spec=Bullet)
        b1.active = True
        b1.owner = MagicMock()
        b1.rect = pygame.Rect(50, 50, 2, 2)
        b2 = MagicMock(spec=Bullet)
        b2.active = True
        b2.owner = MagicMock()
        b2.rect = pygame.Rect(52, 50, 2, 2)
        handler.process_collisions([(b1, b2)])
        mock_effect_manager.spawn.assert_not_called()

    def test_player_destroyed_spawns_large_explosion(
        self, handler, mock_player, mock_effect_manager
    ):
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner_type = "enemy"
        bullet.owner = MagicMock()
        bullet.rect = pygame.Rect(50, 50, 2, 2)
        mock_player.take_damage.return_value = True
        mock_player.rect = pygame.Rect(100, 100, 32, 32)
        handler.process_collisions([(bullet, mock_player)])
        mock_effect_manager.spawn.assert_called_once_with(
            EffectType.LARGE_EXPLOSION, 116.0, 116.0
        )


class TestScoring:
    @pytest.mark.parametrize(
        "tank_type,expected_points",
        [
            (TankType.BASIC, 100),
            (TankType.FAST, 200),
            (TankType.POWER, 300),
            (TankType.ARMOR, 400),
        ],
    )
    def test_enemy_destroyed_awards_points(
        self,
        handler,
        mock_bullet,
        mock_enemy,
        mock_add_score,
        tank_type,
        expected_points,
    ):
        """Destroying an enemy awards points based on tank type."""
        mock_enemy.tank_type = tank_type
        mock_enemy.take_damage.return_value = True
        handler.process_collisions([(mock_bullet, mock_enemy)])
        mock_add_score.assert_called_once_with(expected_points)

    def test_enemy_damaged_not_destroyed_no_points(
        self, handler, mock_bullet, mock_enemy, mock_add_score
    ):
        """Damaging but not destroying an enemy awards no points."""
        mock_enemy.take_damage.return_value = False
        handler.process_collisions([(mock_bullet, mock_enemy)])
        mock_add_score.assert_not_called()


class TestPlayerVsPowerUp:
    """Tests for player-vs-powerup collision handling."""

    @pytest.fixture
    def mock_power_up_manager(self):
        manager = MagicMock(spec=PowerUpManager)
        manager.collect_power_up.return_value = PowerUpType.HELMET
        return manager

    @pytest.fixture
    def handler_with_powerup(
        self, mock_map, mock_effect_manager, mock_power_up_manager
    ):
        score_tracker = {"score": 0}

        def add_score(pts):
            score_tracker["score"] += pts

        h = CollisionResponseHandler(
            game_map=mock_map,
            set_game_state=MagicMock(),
            effect_manager=mock_effect_manager,
            add_score=add_score,
            power_up_manager=mock_power_up_manager,
        )
        return h, score_tracker, mock_power_up_manager

    @pytest.fixture
    def mock_player(self):
        return MagicMock(spec=PlayerTank)

    @pytest.fixture
    def mock_power_up(self):
        return MagicMock(spec=PowerUp)

    def test_player_collects_power_up(
        self, handler_with_powerup, mock_player, mock_power_up
    ):
        handler, score_tracker, pu_manager = handler_with_powerup
        handler.process_collisions([(mock_player, mock_power_up)])
        pu_manager.collect_power_up.assert_called_once_with(mock_power_up)
        assert score_tracker["score"] == POWERUP_COLLECT_POINTS

    def test_power_up_not_collected_without_manager(
        self, mock_map, mock_effect_manager, mock_player, mock_power_up
    ):
        handler = CollisionResponseHandler(
            game_map=mock_map,
            set_game_state=MagicMock(),
            effect_manager=mock_effect_manager,
        )
        result = handler.process_collisions([(mock_player, mock_power_up)])
        assert result == []

    def test_collected_type_stored(
        self, handler_with_powerup, mock_player, mock_power_up
    ):
        handler, score_tracker, pu_manager = handler_with_powerup
        handler.process_collisions([(mock_player, mock_power_up)])
        assert handler.consume_collected_power_up() == PowerUpType.HELMET

    def test_consume_clears_stored_type(
        self, handler_with_powerup, mock_player, mock_power_up
    ):
        handler, score_tracker, pu_manager = handler_with_powerup
        handler.process_collisions([(mock_player, mock_power_up)])
        result = handler.consume_collected_power_up()
        assert result == PowerUpType.HELMET
        assert handler.consume_collected_power_up() is None

    def test_consume_returns_none_when_empty(self, handler_with_powerup):
        handler, score_tracker, pu_manager = handler_with_powerup
        assert handler.consume_collected_power_up() is None


class TestPowerBulletVsSteel:
    @pytest.fixture
    def power_bullet(self):
        b = MagicMock(spec=Bullet)
        b.active = True
        b.owner_type = "player"
        b.power_bullet = True
        b.rect = pygame.Rect(100, 100, 4, 4)
        b.direction = Direction.RIGHT
        return b

    @pytest.fixture
    def normal_bullet(self):
        b = MagicMock(spec=Bullet)
        b.active = True
        b.owner_type = "player"
        b.power_bullet = False
        b.rect = pygame.Rect(100, 100, 4, 4)
        b.direction = Direction.RIGHT
        return b

    @pytest.fixture
    def steel_tile(self):
        t = MagicMock(spec=Tile)
        t.type = TileType.STEEL
        t.blocks_bullets = True
        t.x = 6
        t.y = 6
        t.rect = pygame.Rect(96, 96, 16, 16)
        return t

    def test_power_bullet_destroys_steel(
        self, handler, power_bullet, steel_tile, mock_map
    ):
        handler.process_collisions([(power_bullet, steel_tile)])
        mock_map.set_tile_type.assert_called()
        assert not power_bullet.active

    def test_normal_bullet_blocked_by_steel(
        self, handler, normal_bullet, steel_tile, mock_map
    ):
        handler.process_collisions([(normal_bullet, steel_tile)])
        mock_map.set_tile_type.assert_not_called()
        assert not normal_bullet.active

    def test_power_bullet_does_not_change_base_behavior(
        self, handler, power_bullet, mock_map
    ):
        base_tile = MagicMock(spec=Tile)
        base_tile.type = TileType.BASE
        base_tile.blocks_bullets = True
        base_tile.is_destructible = False
        base_tile.x = 8
        base_tile.y = 14
        base_tile.rect = pygame.Rect(128, 224, 16, 16)
        handler.process_collisions([(power_bullet, base_tile)])
        assert not power_bullet.active
