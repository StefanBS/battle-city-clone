import pytest
import pygame
from managers.collision_manager import CollisionManager
from core.tile import TileType


# Define mock classes needed for spec in this file
# (Moved back from conftest.py)
class MockPlayerTank(pygame.sprite.Sprite):
    pass


class MockEnemyTank(pygame.sprite.Sprite):
    pass


class MockBullet(pygame.sprite.Sprite):
    pass


class MockTile(pygame.sprite.Sprite):
    pass


@pytest.fixture
def collision_manager():
    """Provides a CollisionManager instance."""
    pygame.init()  # Pygame needed for Rect
    manager = CollisionManager()
    yield manager
    pygame.quit()


@pytest.fixture
def mock_objects(create_mock_sprite):
    """Provides a dictionary of mock game objects for collision tests."""
    tile_size = 32
    player = create_mock_sprite(0, 0, tile_size, tile_size, spec=MockPlayerTank)
    enemy1 = create_mock_sprite(100, 100, tile_size, tile_size, spec=MockEnemyTank)
    enemy2 = create_mock_sprite(200, 200, tile_size, tile_size, spec=MockEnemyTank)
    p_bullet1 = create_mock_sprite(50, 50, 5, 5, spec=MockBullet, owner_type="player")
    p_bullet2 = create_mock_sprite(60, 60, 5, 5, spec=MockBullet, owner_type="player")
    e_bullet1 = create_mock_sprite(150, 150, 5, 5, spec=MockBullet, owner_type="enemy")
    e_bullet2 = create_mock_sprite(160, 160, 5, 5, spec=MockBullet, owner_type="enemy")
    brick1 = create_mock_sprite(
        300, 300, tile_size, tile_size, spec=MockTile, tile_type=TileType.BRICK
    )
    steel1 = create_mock_sprite(
        400, 400, tile_size, tile_size, spec=MockTile, tile_type=TileType.STEEL
    )
    base = create_mock_sprite(
        500, 500, tile_size, tile_size, spec=MockTile, tile_type=TileType.BASE
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
        p_bullet = mock_objects["p_bullets"][0]
        enemy = mock_objects["enemies"][0]
        p_bullet.rect = enemy.rect.copy()  # Force collision

        collision_manager.check_collisions(
            player_tank=mock_objects["player"],
            player_bullets=[p_bullet],
            enemy_tanks=[enemy],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        assert len(events) == 1
        assert (p_bullet, enemy) in events or (enemy, p_bullet) in events

    def test_player_bullet_vs_destructible_tile(self, collision_manager, mock_objects):
        """Test collision between player bullet and brick tile."""
        p_bullet = mock_objects["p_bullets"][0]
        brick = mock_objects["bricks"][0]
        p_bullet.rect = brick.rect.copy()

        collision_manager.check_collisions(
            player_tank=None,
            player_bullets=[p_bullet],
            enemy_tanks=[],
            enemy_bullets=[],
            destructible_tiles=[brick],
            impassable_tiles=[],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        assert len(events) == 1
        assert (p_bullet, brick) in events or (brick, p_bullet) in events

    def test_enemy_bullet_vs_player_tank(self, collision_manager, mock_objects):
        """Test collision between enemy bullet and player tank."""
        e_bullet = mock_objects["e_bullets"][0]
        player = mock_objects["player"]
        e_bullet.rect = player.rect.copy()

        collision_manager.check_collisions(
            player_tank=player,
            player_bullets=[],
            enemy_tanks=[],
            enemy_bullets=[e_bullet],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        assert len(events) == 1
        assert (e_bullet, player) in events or (player, e_bullet) in events

    def test_enemy_bullet_vs_player_base(self, collision_manager, mock_objects):
        """Test collision between enemy bullet and player base."""
        e_bullet = mock_objects["e_bullets"][0]
        base = mock_objects["base"]
        e_bullet.rect = base.rect.copy()

        collision_manager.check_collisions(
            player_tank=None,
            player_bullets=[],
            enemy_tanks=[],
            enemy_bullets=[e_bullet],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=base,
        )
        events = collision_manager.get_collision_events()
        assert len(events) == 1
        assert (e_bullet, base) in events or (base, e_bullet) in events

    def test_enemy_bullet_vs_destructible_tile(self, collision_manager, mock_objects):
        """Test collision between enemy bullet and brick tile."""
        e_bullet = mock_objects["e_bullets"][0]
        brick = mock_objects["bricks"][0]
        e_bullet.rect = brick.rect.copy()

        collision_manager.check_collisions(
            player_tank=None,
            player_bullets=[],
            enemy_tanks=[],
            enemy_bullets=[e_bullet],
            destructible_tiles=[brick],
            impassable_tiles=[],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        assert len(events) == 1
        assert (e_bullet, brick) in events or (brick, e_bullet) in events

    def test_player_bullet_vs_enemy_bullet(self, collision_manager, mock_objects):
        """Test collision between player bullet and enemy bullet."""
        p_bullet = mock_objects["p_bullets"][0]
        e_bullet = mock_objects["e_bullets"][0]
        p_bullet.rect = e_bullet.rect.copy()

        collision_manager.check_collisions(
            player_tank=None,
            player_bullets=[p_bullet],
            enemy_tanks=[],
            enemy_bullets=[e_bullet],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        assert len(events) == 1
        assert (p_bullet, e_bullet) in events or (e_bullet, p_bullet) in events

    def test_tank_vs_impassable_tile(self, collision_manager, mock_objects):
        """Test collision between player tank and steel tile."""
        player = mock_objects["player"]
        steel = mock_objects["steel"][0]
        player.rect = steel.rect.copy()

        collision_manager.check_collisions(
            player_tank=player,
            player_bullets=[],
            enemy_tanks=[],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[steel],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        assert len(events) == 1
        assert (player, steel) in events or (steel, player) in events

    def test_tank_vs_tank(self, collision_manager, mock_objects):
        """Test collision between player tank and enemy tank."""
        player = mock_objects["player"]
        enemy = mock_objects["enemies"][0]
        player.rect = enemy.rect.copy()

        collision_manager.check_collisions(
            player_tank=player,
            player_bullets=[],
            enemy_tanks=[enemy],
            enemy_bullets=[],
            destructible_tiles=[],
            impassable_tiles=[],
            player_base=None,
        )
        events = collision_manager.get_collision_events()
        # Should have player vs enemy collision
        assert len(events) == 1
        assert (player, enemy) in events or (enemy, player) in events

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
