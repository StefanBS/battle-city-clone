import pytest
from src.managers.collision_manager import CollisionManager
from src.core.tile import TileType, Tile
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank
from src.core.bullet import Bullet
from src.utils.constants import TILE_SIZE


@pytest.fixture
def collision_manager():
    """Provides a CollisionManager instance."""
    return CollisionManager()


@pytest.fixture
def mock_objects(create_mock_sprite):
    """Provides a dictionary of mock game objects for collision tests."""
    tile_size = TILE_SIZE
    player = create_mock_sprite(
        0, 0, tile_size, tile_size, spec=PlayerTank, owner_type="player"
    )
    enemy1 = create_mock_sprite(
        100, 100, tile_size, tile_size, spec=EnemyTank, owner_type="enemy"
    )
    enemy2 = create_mock_sprite(
        200, 200, tile_size, tile_size, spec=EnemyTank, owner_type="enemy"
    )
    p_bullet1 = create_mock_sprite(
        50, 50, 5, 5, spec=Bullet, owner_type="player", active=True
    )
    p_bullet2 = create_mock_sprite(
        60, 60, 5, 5, spec=Bullet, owner_type="player", active=True
    )
    e_bullet1 = create_mock_sprite(
        150, 150, 5, 5, spec=Bullet, owner_type="enemy", active=True
    )
    e_bullet2 = create_mock_sprite(
        160, 160, 5, 5, spec=Bullet, owner_type="enemy", active=True
    )
    brick1 = create_mock_sprite(
        300, 300, tile_size, tile_size, spec=Tile, type=TileType.BRICK
    )
    steel1 = create_mock_sprite(
        400, 400, tile_size, tile_size, spec=Tile, type=TileType.STEEL
    )
    base = create_mock_sprite(
        500, 500, tile_size, tile_size, spec=Tile, type=TileType.BASE
    )

    return {
        "player": player,
        "enemies": [enemy1, enemy2],
        "p_bullets": [p_bullet1, p_bullet2],
        "e_bullets": [e_bullet1, e_bullet2],
        "bricks": [brick1],
        "steel": [steel1],
        "base": base,
    }


class TestCollisionManager:
    def _assert_single_collision(self, collision_manager, obj_a, obj_b, **check_kwargs):
        """Force overlap between two objects and assert exactly one collision event."""
        obj_a.rect = obj_b.rect.copy()
        defaults = dict(
            player_tank=None,
            player_bullets=[],
            enemy_tanks=[],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
        )
        defaults.update(check_kwargs)
        collision_manager.check_collisions(**defaults)
        events = collision_manager.get_collision_events()
        assert len(events) == 1
        assert (obj_a, obj_b) in events or (obj_b, obj_a) in events

    def test_initialization(self, collision_manager):
        """Test CollisionManager initializes with empty events."""
        assert collision_manager.get_collision_events() == []

    def test_no_collisions(self, collision_manager, mock_objects):
        """Test check_collisions when no objects overlap."""
        collision_manager.check_collisions(
            player_tank=mock_objects["player"],
            player_bullets=mock_objects["p_bullets"],
            enemy_tanks=mock_objects["enemies"],
            enemy_bullets=mock_objects["e_bullets"],
            destructible_tiles=mock_objects["bricks"],
            impassable_tiles=mock_objects["steel"] + [mock_objects["base"]],
            player_base=mock_objects["base"],
        )
        assert collision_manager.get_collision_events() == []

    def test_player_bullet_vs_enemy_tank(self, collision_manager, mock_objects):
        """Test collision between player bullet and enemy tank."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["p_bullets"][0],
            mock_objects["enemies"][0],
            player_tank=mock_objects["player"],
            player_bullets=[mock_objects["p_bullets"][0]],
            enemy_tanks=[mock_objects["enemies"][0]],
        )

    def test_player_bullet_vs_destructible_tile(self, collision_manager, mock_objects):
        """Test collision between player bullet and brick tile."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["p_bullets"][0],
            mock_objects["bricks"][0],
            player_bullets=[mock_objects["p_bullets"][0]],
            destructible_tiles=[mock_objects["bricks"][0]],
        )

    def test_enemy_bullet_vs_player_tank(self, collision_manager, mock_objects):
        """Test collision between enemy bullet and player tank."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["e_bullets"][0],
            mock_objects["player"],
            player_tank=mock_objects["player"],
            enemy_bullets=[mock_objects["e_bullets"][0]],
        )

    def test_enemy_bullet_vs_player_base(self, collision_manager, mock_objects):
        """Test collision between enemy bullet and player base."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["e_bullets"][0],
            mock_objects["base"],
            enemy_bullets=[mock_objects["e_bullets"][0]],
            player_base=mock_objects["base"],
        )

    def test_enemy_bullet_vs_destructible_tile(self, collision_manager, mock_objects):
        """Test collision between enemy bullet and brick tile."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["e_bullets"][0],
            mock_objects["bricks"][0],
            enemy_bullets=[mock_objects["e_bullets"][0]],
            destructible_tiles=[mock_objects["bricks"][0]],
        )

    def test_player_bullet_vs_enemy_bullet(self, collision_manager, mock_objects):
        """Test collision between player bullet and enemy bullet."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["p_bullets"][0],
            mock_objects["e_bullets"][0],
            player_bullets=[mock_objects["p_bullets"][0]],
            enemy_bullets=[mock_objects["e_bullets"][0]],
        )

    def test_tank_vs_impassable_tile(self, collision_manager, mock_objects):
        """Test collision between player tank and steel tile."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["player"],
            mock_objects["steel"][0],
            player_tank=mock_objects["player"],
            impassable_tiles=[mock_objects["steel"][0]],
        )

    def test_tank_vs_tank(self, collision_manager, mock_objects):
        """Test collision between player tank and enemy tank."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["player"],
            mock_objects["enemies"][0],
            player_tank=mock_objects["player"],
            enemy_tanks=[mock_objects["enemies"][0]],
        )

    def test_multiple_collisions(self, collision_manager, mock_objects):
        """Test multiple collisions occurring in one check."""
        p_bullet = mock_objects["p_bullets"][0]
        e_bullet = mock_objects["e_bullets"][0]
        enemy = mock_objects["enemies"][0]
        brick = mock_objects["bricks"][0]

        # p_bullet hits enemy, e_bullet hits brick
        p_bullet.rect = enemy.rect.copy()
        e_bullet.rect = brick.rect.copy()

        collision_manager.check_collisions(
            player_tank=None,
            player_bullets=[p_bullet],
            enemy_tanks=[enemy],
            enemy_bullets=[e_bullet],
            destructible_tiles=[brick],
            impassable_tiles=[],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        assert len(events) == 2
        assert (p_bullet, enemy) in events or (enemy, p_bullet) in events
        assert (e_bullet, brick) in events or (brick, e_bullet) in events

    def test_event_clearing(self, collision_manager, mock_objects):
        """Test that events are cleared on subsequent calls."""
        p_bullet = mock_objects["p_bullets"][0]
        enemy = mock_objects["enemies"][0]
        p_bullet.rect = enemy.rect.copy()

        # First call with collision
        collision_manager.check_collisions(
            player_tank=None,
            player_bullets=[p_bullet],
            enemy_tanks=[enemy],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
        )
        assert len(collision_manager.get_collision_events()) == 1

        # Second call with no collision
        p_bullet.rect.move_ip(1000, 1000)  # Move bullet away
        collision_manager.check_collisions(
            player_tank=None,
            player_bullets=[p_bullet],
            enemy_tanks=[enemy],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
        )
        assert len(collision_manager.get_collision_events()) == 0

    def test_player_bullet_vs_impassable_tile(self, collision_manager, mock_objects):
        """Test collision between player bullet and steel tile."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["p_bullets"][0],
            mock_objects["steel"][0],
            player_bullets=[mock_objects["p_bullets"][0]],
            impassable_tiles=[mock_objects["steel"][0]],
        )

    def test_enemy_bullet_vs_impassable_tile(self, collision_manager, mock_objects):
        """Test collision between enemy bullet and steel tile."""
        self._assert_single_collision(
            collision_manager,
            mock_objects["e_bullets"][0],
            mock_objects["steel"][0],
            enemy_bullets=[mock_objects["e_bullets"][0]],
            impassable_tiles=[mock_objects["steel"][0]],
        )

    def test_duplicate_brick_collision_deduplicated(
        self, collision_manager, mock_objects
    ):
        """Test BRICK in both tile lists produces one event."""
        p_bullet = mock_objects["p_bullets"][0]
        brick = mock_objects["bricks"][0]
        p_bullet.rect = brick.rect.copy()  # Force collision

        # Pass brick in BOTH destructible and impassable lists (as game_manager does)
        collision_manager.check_collisions(
            player_tank=None,
            player_bullets=[p_bullet],
            enemy_tanks=[],
            enemy_bullets=[],
            destructible_tiles=[brick],
            impassable_tiles=[brick],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        # Should only have ONE event, not two
        assert len(events) == 1
        assert (p_bullet, brick) in events or (brick, p_bullet) in events


class TestPowerUpCollision:
    """Tests for player-vs-powerup collision detection."""

    def test_player_powerup_collision_detected(self):
        import pygame

        from unittest.mock import MagicMock

        cm = CollisionManager()
        player = MagicMock()
        player.rect = pygame.Rect(100, 100, 32, 32)
        power_up = MagicMock()
        power_up.rect = pygame.Rect(100, 100, 32, 32)

        cm.check_collisions(
            player_tank=player,
            player_bullets=[],
            enemy_tanks=[],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
            power_up=power_up,
        )
        events = cm.get_collision_events()
        assert len(events) == 1
        assert player in events[0]
        assert power_up in events[0]

    def test_no_collision_when_apart(self):
        import pygame

        from unittest.mock import MagicMock

        cm = CollisionManager()
        player = MagicMock()
        player.rect = pygame.Rect(0, 0, 32, 32)
        power_up = MagicMock()
        power_up.rect = pygame.Rect(200, 200, 32, 32)

        cm.check_collisions(
            player_tank=player,
            player_bullets=[],
            enemy_tanks=[],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
            power_up=power_up,
        )
        events = cm.get_collision_events()
        assert len(events) == 0

    def test_no_collision_when_power_up_none(self):
        import pygame

        from unittest.mock import MagicMock

        cm = CollisionManager()
        player = MagicMock()
        player.rect = pygame.Rect(0, 0, 32, 32)

        cm.check_collisions(
            player_tank=player,
            player_bullets=[],
            enemy_tanks=[],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
            power_up=None,
        )
        events = cm.get_collision_events()
        assert len(events) == 0
