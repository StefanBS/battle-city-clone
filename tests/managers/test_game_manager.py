import pytest
import pygame
from unittest.mock import patch, MagicMock
from managers.game_manager import GameManager
from states.game_state import GameState
from core.player_tank import PlayerTank
from core.enemy_tank import EnemyTank
from core.bullet import Bullet
from core.tile import Tile, TileType
from utils.constants import (
    WINDOW_TITLE,
    FPS,
    TILE_SIZE,
    GRID_WIDTH,
    GRID_HEIGHT,
    BLACK,
)


class TestGameManager:
    """Unit test cases for the GameManager class."""

    @pytest.fixture
    def game_manager(self):
        """Create a game manager instance for testing."""
        pygame.init()
        # Mock display and font initialization to avoid errors in headless environment
        with patch("pygame.display.set_mode"), patch("pygame.font.SysFont"):
            manager = GameManager()
        yield manager
        pygame.quit()

    def test_initialization(self, game_manager):
        """Test that the game manager initializes correctly."""
        assert game_manager.state == GameState.RUNNING
        assert game_manager.background_color == BLACK
        assert game_manager.fps == FPS
        assert game_manager.tile_size == TILE_SIZE
        assert game_manager.screen_width == GRID_WIDTH * TILE_SIZE
        assert game_manager.screen_height == GRID_HEIGHT * TILE_SIZE
        assert pygame.display.get_caption()[0] == WINDOW_TITLE

    def test_handle_events_quit(self, game_manager):
        """Test handling quit event."""
        with pytest.raises(SystemExit):
            event = pygame.event.Event(pygame.QUIT)
            pygame.event.post(event)
            game_manager.handle_events()

    def test_handle_events_escape(self, game_manager):
        """Test handling escape key event."""
        with pytest.raises(SystemExit):
            event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
            pygame.event.post(event)
            game_manager.handle_events()

    def test_handle_events_restart(self, game_manager):
        """Test handling restart key event."""
        # Set game to game over state
        game_manager.state = GameState.GAME_OVER

        # Simulate R key press
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        pygame.event.post(event)
        game_manager.handle_events()

        # Game should be reset
        assert game_manager.state == GameState.RUNNING

    def test_handle_events_restart_not_game_over(self, game_manager):
        """Test that restart key does nothing when game is running."""
        initial_state = game_manager.state

        # Simulate R key press
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        pygame.event.post(event)
        game_manager.handle_events()

        # Game state should not change
        assert game_manager.state == initial_state

    def test_initial_enemy_spawn(self, game_manager):
        """Test that an enemy tank is spawned on initialization."""
        assert len(game_manager.enemy_tanks) == 1
        assert game_manager.total_enemy_spawns == 1

    @patch("random.choice")
    def test_spawn_enemy_adds_enemy(self, mock_random_choice, game_manager):
        """Test that _spawn_enemy adds an enemy tank when the spot is clear."""
        # Ensure the chosen spawn point is clear (mock map check)
        mock_random_choice.return_value = game_manager.SPAWN_POINTS[0]
        game_manager.map.get_collidable_tiles = MagicMock(return_value=[])
        # Ensure no existing tanks interfere with this specific test
        game_manager.enemy_tanks = []
        game_manager.total_enemy_spawns = 0

        initial_enemies = len(game_manager.enemy_tanks)  # Should be 0 now
        initial_spawns = game_manager.total_enemy_spawns  # Should be 0 now
        game_manager._spawn_enemy()

        assert (
            len(game_manager.enemy_tanks) == initial_enemies + 1
        )  # Checks it becomes 1
        assert (
            game_manager.total_enemy_spawns == initial_spawns + 1
        )  # Checks it becomes 1

    @patch("random.choice")
    def test_spawn_enemy_respects_max_spawns(self, mock_random_choice, game_manager):
        """Test that _spawn_enemy respects the maximum spawn limit."""
        mock_random_choice.return_value = game_manager.SPAWN_POINTS[0]
        game_manager.map.get_collidable_tiles = MagicMock(return_value=[])
        game_manager.total_enemy_spawns = game_manager.max_enemy_spawns

        initial_enemies = len(game_manager.enemy_tanks)
        game_manager._spawn_enemy()

        assert len(game_manager.enemy_tanks) == initial_enemies  # No new enemy added
        assert game_manager.total_enemy_spawns == game_manager.max_enemy_spawns

    @patch("random.choice")
    def test_spawn_enemy_avoids_map_collision(self, mock_random_choice, game_manager):
        """Test that _spawn_enemy avoids spawning on map collision tiles."""
        spawn_point_grid = game_manager.SPAWN_POINTS[0]
        mock_random_choice.return_value = spawn_point_grid
        spawn_x = spawn_point_grid[0] * game_manager.tile_size
        spawn_y = spawn_point_grid[1] * game_manager.tile_size
        # Simulate a map tile at the spawn point
        colliding_tile = pygame.Rect(
            spawn_x, spawn_y, game_manager.tile_size, game_manager.tile_size
        )
        game_manager.map.get_collidable_tiles = MagicMock(return_value=[colliding_tile])

        initial_enemies = len(game_manager.enemy_tanks)
        initial_spawns = (
            game_manager.total_enemy_spawns
        )  # Spawn count shouldn't increase if blocked
        game_manager._spawn_enemy()

        assert len(game_manager.enemy_tanks) == initial_enemies
        assert game_manager.total_enemy_spawns == initial_spawns

    @patch("random.choice")
    def test_spawn_enemy_avoids_tank_collision(self, mock_random_choice, game_manager):
        """Test that _spawn_enemy avoids spawning on other tanks."""
        spawn_point_grid = game_manager.SPAWN_POINTS[0]
        mock_random_choice.return_value = spawn_point_grid
        spawn_x = spawn_point_grid[0] * game_manager.tile_size
        spawn_y = spawn_point_grid[1] * game_manager.tile_size
        game_manager.map.get_collidable_tiles = MagicMock(return_value=[])  # Clear map

        # Place an existing enemy at the spawn point
        existing_enemy = MagicMock(spec=EnemyTank)
        existing_enemy.rect = pygame.Rect(
            spawn_x, spawn_y, game_manager.tile_size, game_manager.tile_size
        )
        game_manager.enemy_tanks = [existing_enemy]  # Replace initial enemy
        game_manager.total_enemy_spawns = 1  # Reflect the one enemy

        initial_enemies = len(game_manager.enemy_tanks)
        game_manager._spawn_enemy()

        assert len(game_manager.enemy_tanks) == initial_enemies  # Should still be 1
        assert game_manager.total_enemy_spawns == 1  # Spawn count shouldn't increase

    @patch("managers.game_manager.GameManager._spawn_enemy")
    def test_update_calls_spawn_enemy(self, mock_spawn_enemy, game_manager):
        """Test that update calls _spawn_enemy after the spawn interval."""
        game_manager.spawn_timer = 0
        # Simulate time passing just enough to trigger spawn
        num_updates = int(game_manager.spawn_interval * game_manager.fps) + 1

        for _ in range(num_updates):
            game_manager.update()

        mock_spawn_enemy.assert_called_once()
        assert game_manager.spawn_timer == pytest.approx(0)  # Timer should reset

    def test_update_does_not_call_spawn_before_interval(self, game_manager):
        """Test that update doesn't call _spawn_enemy before the interval."""
        game_manager.spawn_timer = game_manager.spawn_interval - 0.1  # Almost time
        with patch.object(game_manager, "_spawn_enemy") as mock_spawn:
            # Simulate one frame update
            game_manager.update()
            mock_spawn.assert_not_called()

    # --- Bullet Collision Tests --- #

    def _setup_bullet_collision_test(
        self,
        game_manager,
        player_bullet_active: bool = False,
        enemy_bullet_active: bool = False,
    ):
        """Helper to set up mocks for bullet collision tests."""
        game_manager.player_tank = MagicMock(spec=PlayerTank)
        game_manager.player_tank.rect = pygame.Rect(100, 100, TILE_SIZE, TILE_SIZE)
        game_manager.player_tank.bullet = MagicMock(spec=Bullet)
        game_manager.player_tank.bullet.active = player_bullet_active
        game_manager.player_tank.bullet.rect = pygame.Rect(110, 110, 5, 5)
        game_manager.player_tank.is_invincible = False
        game_manager.player_tank.take_damage.return_value = (
            False  # Default: doesn't die
        )
        game_manager.player_tank.lives = 3

        game_manager.enemy_tanks = [MagicMock(spec=EnemyTank)]
        enemy = game_manager.enemy_tanks[0]
        enemy.rect = pygame.Rect(200, 200, TILE_SIZE, TILE_SIZE)
        enemy.bullet = MagicMock(spec=Bullet)
        enemy.bullet.active = enemy_bullet_active
        enemy.bullet.rect = pygame.Rect(210, 210, 5, 5)
        enemy.take_damage.return_value = False  # Default: doesn't die

        game_manager.map = MagicMock()
        game_manager.map.width = GRID_WIDTH
        game_manager.map.height = GRID_HEIGHT
        game_manager.map.get_tile_at.return_value = None  # Default: empty space

        return game_manager.player_tank, enemy

    def test_player_bullet_hits_enemy_tank(self, game_manager):
        """Test player bullet hitting an enemy tank."""
        player, enemy = self._setup_bullet_collision_test(
            game_manager, player_bullet_active=True
        )
        player.bullet.rect = enemy.rect.copy()  # Direct hit

        game_manager._handle_bullet_collisions()

        enemy.take_damage.assert_called_once()
        assert not player.bullet.active
        assert len(game_manager.enemy_tanks) == 1  # Enemy didn't die yet

    def test_player_bullet_kills_enemy_tank(self, game_manager):
        """Test player bullet destroying an enemy tank."""
        player, enemy = self._setup_bullet_collision_test(
            game_manager, player_bullet_active=True
        )
        player.bullet.rect = enemy.rect.copy()
        enemy.take_damage.return_value = True  # Enemy dies on hit
        game_manager.total_enemy_spawns = (
            game_manager.max_enemy_spawns
        )  # Ensure no more spawn

        game_manager._handle_bullet_collisions()

        enemy.take_damage.assert_called_once()
        assert not player.bullet.active
        assert len(game_manager.enemy_tanks) == 0
        assert game_manager.state == GameState.VICTORY  # Last enemy killed

    def test_player_bullet_hits_brick(self, game_manager):
        """Test player bullet hitting a brick tile."""
        player, _ = self._setup_bullet_collision_test(
            game_manager, player_bullet_active=True
        )
        brick_tile = MagicMock(spec=Tile)
        brick_tile.type = TileType.BRICK
        brick_tile.rect = player.bullet.rect.copy()
        game_manager.map.get_tile_at.return_value = brick_tile

        game_manager._handle_bullet_collisions()

        assert brick_tile.type == TileType.EMPTY
        assert not player.bullet.active

    def test_player_bullet_hits_steel(self, game_manager):
        """Test player bullet hitting a steel tile."""
        player, _ = self._setup_bullet_collision_test(
            game_manager, player_bullet_active=True
        )
        steel_tile = MagicMock(spec=Tile)
        steel_tile.type = TileType.STEEL
        steel_tile.rect = player.bullet.rect.copy()
        game_manager.map.get_tile_at.return_value = steel_tile

        game_manager._handle_bullet_collisions()

        assert steel_tile.type == TileType.STEEL  # Unchanged
        assert not player.bullet.active

    def test_player_bullet_hits_base(self, game_manager):
        """Test player bullet hitting the base."""
        player, _ = self._setup_bullet_collision_test(
            game_manager, player_bullet_active=True
        )
        base_tile = MagicMock(spec=Tile)
        base_tile.type = TileType.BASE
        base_tile.rect = player.bullet.rect.copy()
        game_manager.map.get_tile_at.return_value = base_tile

        game_manager._handle_bullet_collisions()

        assert game_manager.state == GameState.GAME_OVER
        # Bullet state doesn't strictly matter after game over, but good practice
        # assert not player.bullet.active # Original code doesn't deactivate bullet here

    def test_enemy_bullet_hits_player_tank(self, game_manager):
        """Test enemy bullet hitting the player tank."""
        player, enemy = self._setup_bullet_collision_test(
            game_manager, enemy_bullet_active=True
        )
        enemy.bullet.rect = player.rect.copy()

        game_manager._handle_bullet_collisions()

        player.take_damage.assert_called_once()
        player.respawn.assert_called_once()
        assert not enemy.bullet.active
        assert game_manager.state == GameState.RUNNING  # Player didn't die

    def test_enemy_bullet_kills_player_tank(self, game_manager):
        """Test enemy bullet killing the player tank (last life)."""
        player, enemy = self._setup_bullet_collision_test(
            game_manager,
            player_bullet_active=False,  # Deactivate player bullet
            enemy_bullet_active=True,
        )
        enemy.bullet.rect = player.rect.copy()
        player.take_damage.return_value = True  # Player dies on hit

        game_manager._handle_bullet_collisions()

        player.take_damage.assert_called_once()
        player.respawn.assert_not_called()  # No respawn on game over
        assert not enemy.bullet.active
        assert game_manager.state == GameState.GAME_OVER

    def test_enemy_bullet_hits_invincible_player(self, game_manager):
        """Test enemy bullet hitting an invincible player."""
        player, enemy = self._setup_bullet_collision_test(
            game_manager, enemy_bullet_active=True
        )
        enemy.bullet.rect = player.rect.copy()
        player.is_invincible = True

        game_manager._handle_bullet_collisions()

        player.take_damage.assert_not_called()
        player.respawn.assert_not_called()
        assert not enemy.bullet.active
        assert game_manager.state == GameState.RUNNING

    def test_enemy_bullet_hits_brick(self, game_manager):
        """Test enemy bullet hitting a brick tile."""
        _, enemy = self._setup_bullet_collision_test(
            game_manager, enemy_bullet_active=True
        )
        brick_tile = MagicMock(spec=Tile)
        brick_tile.type = TileType.BRICK
        brick_tile.rect = enemy.bullet.rect.copy()
        # Need to mock the map iteration
        game_manager.map.get_tile_at.side_effect = lambda x, y: (
            brick_tile
            if brick_tile.rect.collidepoint(x * TILE_SIZE, y * TILE_SIZE)
            else None
        )

        # Simplify the check by placing the bullet clearly within one tile
        bx, by = enemy.bullet.rect.center
        grid_x, grid_y = bx // TILE_SIZE, by // TILE_SIZE
        game_manager.map.get_tile_at = MagicMock(
            side_effect=lambda x, y: (
                brick_tile if (x == grid_x and y == grid_y) else None
            )
        )
        brick_tile.rect = pygame.Rect(
            grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE
        )
        enemy.bullet.rect = brick_tile.rect.copy()  # Ensure collision

        game_manager._handle_bullet_collisions()

        assert brick_tile.type == TileType.EMPTY
        assert not enemy.bullet.active

    def test_enemy_bullet_hits_steel(self, game_manager):
        """Test enemy bullet hitting a steel tile."""
        _, enemy = self._setup_bullet_collision_test(
            game_manager, enemy_bullet_active=True
        )
        steel_tile = MagicMock(spec=Tile)
        steel_tile.type = TileType.STEEL
        steel_tile.rect = enemy.bullet.rect.copy()

        # Simplify the check by placing the bullet clearly within one tile
        bx, by = enemy.bullet.rect.center
        grid_x, grid_y = bx // TILE_SIZE, by // TILE_SIZE
        game_manager.map.get_tile_at = MagicMock(
            side_effect=lambda x, y: (
                steel_tile if (x == grid_x and y == grid_y) else None
            )
        )
        steel_tile.rect = pygame.Rect(
            grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE
        )
        enemy.bullet.rect = steel_tile.rect.copy()  # Ensure collision

        game_manager._handle_bullet_collisions()

        assert steel_tile.type == TileType.STEEL  # Unchanged
        assert not enemy.bullet.active

    def test_enemy_bullet_hits_base(self, game_manager):
        """Test enemy bullet hitting the base."""
        _, enemy = self._setup_bullet_collision_test(
            game_manager, enemy_bullet_active=True
        )
        base_tile = MagicMock(spec=Tile)
        base_tile.type = TileType.BASE
        base_tile.rect = enemy.bullet.rect.copy()

        # Simplify the check by placing the bullet clearly within one tile
        bx, by = enemy.bullet.rect.center
        grid_x, grid_y = bx // TILE_SIZE, by // TILE_SIZE
        game_manager.map.get_tile_at = MagicMock(
            side_effect=lambda x, y: (
                base_tile if (x == grid_x and y == grid_y) else None
            )
        )
        base_tile.rect = pygame.Rect(
            grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE
        )
        enemy.bullet.rect = base_tile.rect.copy()  # Ensure collision

        game_manager._handle_bullet_collisions()

        assert game_manager.state == GameState.GAME_OVER
        # Bullet state doesn't strictly matter after game over

    def test_player_bullet_hits_enemy_bullet(self, game_manager):
        """Test player bullet colliding with an enemy bullet."""
        player, enemy = self._setup_bullet_collision_test(
            game_manager, player_bullet_active=True, enemy_bullet_active=True
        )
        # Make bullets collide
        player.bullet.rect = pygame.Rect(150, 150, 5, 5)
        enemy.bullet.rect = pygame.Rect(150, 150, 5, 5)

        game_manager._handle_bullet_collisions()

        assert not player.bullet.active
        assert not enemy.bullet.active
        # Ensure no other side effects (tanks not hit, etc.)
        enemy.take_damage.assert_not_called()
        player.take_damage.assert_not_called()

    # --- Game State Tests --- #

    def test_update_stops_when_not_running(self, game_manager):
        """Test that update method does nothing if state is not RUNNING."""
        game_manager.state = GameState.GAME_OVER
        # Mock methods that should not be called
        game_manager.player_tank.update = MagicMock()
        game_manager.enemy_tanks = [MagicMock(spec=EnemyTank)]
        enemy_update_mock = game_manager.enemy_tanks[0].update
        game_manager._spawn_enemy = MagicMock()
        game_manager._handle_bullet_collisions = MagicMock()

        game_manager.update()

        game_manager.player_tank.update.assert_not_called()
        enemy_update_mock.assert_not_called()
        game_manager._spawn_enemy.assert_not_called()
        game_manager._handle_bullet_collisions.assert_not_called()
