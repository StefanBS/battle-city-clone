import pytest
import pygame
from unittest.mock import ANY, patch, MagicMock
from src.managers.spawn_manager import SpawnManager
from src.managers.effect_manager import EffectManager
from src.core.effect import Effect
from src.core.enemy_tank import EnemyTank
from src.utils.constants import EffectType, TILE_SIZE, SUB_TILE_SIZE, TankType

_DEFAULT_COMPOSITION = {
    TankType.BASIC: 18,
    TankType.FAST: 2,
    TankType.POWER: 0,
    TankType.ARMOR: 0,
}


class TestSpawnManager:
    """Unit test cases for the SpawnManager class."""

    SPAWN_POINTS = [
        (3, 1),
        (8, 1),
        (12, 1),
    ]

    @pytest.fixture
    def mock_player_tank(self):
        """Create a mock player tank positioned away from spawn points."""
        player = MagicMock()
        # Place player at the bottom of the map, far from spawn points
        player.rect = pygame.Rect(
            7 * TILE_SIZE,
            14 * TILE_SIZE,
            TILE_SIZE,
            TILE_SIZE,
        )
        return player

    @pytest.fixture
    def mock_game_map(self):
        """Create a mock game map with no collidable tiles."""
        game_map = MagicMock()
        game_map.get_collidable_tiles.return_value = []
        game_map.spawn_points = self.SPAWN_POINTS
        game_map.width_px = 16 * TILE_SIZE
        game_map.height_px = 16 * TILE_SIZE
        game_map.tile_size = SUB_TILE_SIZE
        game_map.grid_to_pixels.side_effect = lambda gx, gy: (
            gx * SUB_TILE_SIZE,
            gy * SUB_TILE_SIZE,
        )
        return game_map

    @pytest.fixture
    def spawn_manager(self, mock_texture_manager, mock_player_tank, mock_game_map):
        """Create a SpawnManager instance for testing."""
        manager = SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=_DEFAULT_COMPOSITION,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
        )
        return manager

    def test_initial_spawn(self, spawn_manager):
        """Test that the constructor spawns one enemy."""
        assert len(spawn_manager.enemy_tanks) == 1
        assert spawn_manager.total_enemy_spawns == 1

    @patch("random.choice")
    def test_spawn_enemy_adds_enemy(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn_enemy adds an enemy tank when the spot is clear."""
        mock_random_choice.return_value = self.SPAWN_POINTS[0]
        mock_game_map.get_collidable_tiles.return_value = []
        # Clear state from initial spawn
        spawn_manager.enemy_tanks = []
        spawn_manager.total_enemy_spawns = 0

        result = spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)

        assert result is True
        assert len(spawn_manager.enemy_tanks) == 1
        assert spawn_manager.total_enemy_spawns == 1

    @patch("random.choice")
    def test_spawn_enemy_respects_max(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn_enemy respects the maximum spawn limit."""
        mock_random_choice.return_value = self.SPAWN_POINTS[0]
        mock_game_map.get_collidable_tiles.return_value = []
        spawn_manager.total_enemy_spawns = spawn_manager.max_enemy_spawns

        initial_enemies = len(spawn_manager.enemy_tanks)
        result = spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)

        assert result is False
        assert len(spawn_manager.enemy_tanks) == initial_enemies

    @patch("random.choice")
    def test_spawn_enemy_avoids_map_collision(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn_enemy avoids spawning on map collision tiles."""
        spawn_point_grid = self.SPAWN_POINTS[0]
        mock_random_choice.return_value = spawn_point_grid
        spawn_x = spawn_point_grid[0] * SUB_TILE_SIZE
        spawn_y = spawn_point_grid[1] * SUB_TILE_SIZE
        colliding_tile = pygame.Rect(spawn_x, spawn_y, TILE_SIZE, TILE_SIZE)
        mock_game_map.get_collidable_tiles.return_value = [colliding_tile]

        initial_enemies = len(spawn_manager.enemy_tanks)
        initial_spawns = spawn_manager.total_enemy_spawns
        result = spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)

        assert result is False
        assert len(spawn_manager.enemy_tanks) == initial_enemies
        assert spawn_manager.total_enemy_spawns == initial_spawns

    @patch("random.choice")
    def test_spawn_enemy_avoids_tank_collision(
        self, mock_random_choice, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn_enemy avoids spawning on other tanks."""
        spawn_point_grid = self.SPAWN_POINTS[0]
        mock_random_choice.return_value = spawn_point_grid
        spawn_x = spawn_point_grid[0] * SUB_TILE_SIZE
        spawn_y = spawn_point_grid[1] * SUB_TILE_SIZE
        mock_game_map.get_collidable_tiles.return_value = []

        existing_enemy = MagicMock(spec=EnemyTank)
        existing_enemy.rect = pygame.Rect(spawn_x, spawn_y, TILE_SIZE, TILE_SIZE)
        existing_enemy.tank_type = "basic"
        spawn_manager.enemy_tanks = [existing_enemy]
        spawn_manager.total_enemy_spawns = 1

        result = spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)

        assert result is False
        assert len(spawn_manager.enemy_tanks) == 1
        assert spawn_manager.total_enemy_spawns == 1

    def test_update_spawns_on_interval(
        self, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that update triggers spawn when timer reaches the interval."""
        spawn_manager.spawn_timer = spawn_manager.spawn_interval

        with patch.object(
            spawn_manager, "spawn_enemy", return_value=True
        ) as mock_spawn:
            spawn_manager.update(0.1, mock_player_tank, mock_game_map)
            mock_spawn.assert_called_once_with(mock_player_tank, mock_game_map)

        # Timer should be reset after successful spawn
        # (We patched spawn_enemy so we check timer logic directly)

    @patch("random.choice")
    def test_update_resets_timer_on_success(
        self,
        mock_random_choice,
        spawn_manager,
        mock_player_tank,
        mock_game_map,
    ):
        """Test that update resets timer when spawn succeeds."""
        # Use a different spawn point than the initial spawn to avoid collision
        mock_random_choice.return_value = self.SPAWN_POINTS[2]
        spawn_manager.spawn_timer = spawn_manager.spawn_interval
        mock_game_map.get_collidable_tiles.return_value = []
        # Clear existing enemies so spawn point is clear
        spawn_manager.enemy_tanks = []
        spawn_manager.total_enemy_spawns = 0

        spawn_manager.update(0.0, mock_player_tank, mock_game_map)

        assert spawn_manager.spawn_timer == pytest.approx(0.0)

    def test_update_no_reset_on_failed_spawn(
        self, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that update does not reset timer if spawn fails."""
        initial_timer = spawn_manager.spawn_interval
        spawn_manager.spawn_timer = initial_timer

        with patch.object(
            spawn_manager, "spawn_enemy", return_value=False
        ) as mock_spawn:
            dt = 0.1
            spawn_manager.update(dt, mock_player_tank, mock_game_map)
            mock_spawn.assert_called_once()

        # Timer should have been incremented by dt, but NOT reset
        expected = initial_timer + dt
        assert spawn_manager.spawn_timer == pytest.approx(expected)

    def test_update_no_spawn_before_interval(
        self, spawn_manager, mock_player_tank, mock_game_map
    ):
        """Test that update doesn't call spawn_enemy before the interval."""
        spawn_manager.spawn_timer = 0.0

        with patch.object(spawn_manager, "spawn_enemy") as mock_spawn:
            spawn_manager.update(0.1, mock_player_tank, mock_game_map)
            mock_spawn.assert_not_called()

    def test_spawn_queue_built_from_composition(
        self, mock_texture_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn queue is built from enemy composition."""
        manager = SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=_DEFAULT_COMPOSITION,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
        )
        # Stage 1: (18, 2, 0, 0) = 20 total
        assert manager.max_enemy_spawns == 20
        assert manager.total_enemy_spawns == 1  # initial spawn

    def test_spawn_uses_queue_types(
        self, mock_texture_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawn queue contains multiple types for mixed compositions."""
        manager = SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition={
                TankType.BASIC: 2,
                TankType.FAST: 5,
                TankType.POWER: 10,
                TankType.ARMOR: 3,
            },
            spawn_interval=5.0,
            player_tank=mock_player_tank,
        )
        types_in_queue = set(manager._spawn_queue)
        assert len(types_in_queue) > 1

    def test_spawn_stops_when_queue_empty(
        self, mock_texture_manager, mock_player_tank, mock_game_map
    ):
        """Test that spawning stops when the queue is depleted."""
        manager = SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=_DEFAULT_COMPOSITION,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
        )
        # Exhaust all 20 spawns
        for _ in range(25):  # more than 20 to test stop
            manager.enemy_tanks = []  # clear to avoid collision
            manager.spawn_enemy(mock_player_tank, mock_game_map)
        assert manager.total_enemy_spawns == 20

    def test_composition_with_all_basic(
        self, mock_texture_manager, mock_player_tank, mock_game_map
    ):
        """Test that an all-basic composition produces 20 enemies."""
        manager = SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition={
                TankType.BASIC: 20,
                TankType.FAST: 0,
                TankType.POWER: 0,
                TankType.ARMOR: 0,
            },
            spawn_interval=5.0,
            player_tank=mock_player_tank,
        )
        assert manager.max_enemy_spawns == 20


class TestSpawnAnimation:
    """Tests for the spawn animation / pending spawn flow."""

    SPAWN_POINTS = [(3, 1), (8, 1), (12, 1)]

    @pytest.fixture
    def mock_player_tank(self):
        player = MagicMock()
        player.rect = pygame.Rect(7 * TILE_SIZE, 14 * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        return player

    @pytest.fixture
    def mock_game_map(self):
        game_map = MagicMock()
        game_map.get_collidable_tiles.return_value = []
        game_map.spawn_points = self.SPAWN_POINTS
        game_map.width_px = 16 * TILE_SIZE
        game_map.height_px = 16 * TILE_SIZE
        game_map.tile_size = SUB_TILE_SIZE
        game_map.grid_to_pixels.side_effect = lambda gx, gy: (
            gx * SUB_TILE_SIZE,
            gy * SUB_TILE_SIZE,
        )
        return game_map

    @pytest.fixture
    def mock_effect_manager(self):
        em = MagicMock(spec=EffectManager)
        effect = MagicMock(spec=Effect)
        effect.active = True
        em.spawn.return_value = effect
        return em

    @pytest.fixture
    def spawn_manager_with_effects(
        self,
        mock_texture_manager,
        mock_player_tank,
        mock_game_map,
        mock_effect_manager,
    ):
        return SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=_DEFAULT_COMPOSITION,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
            effect_manager=mock_effect_manager,
        )

    def test_spawn_creates_pending_not_immediate(
        self, spawn_manager_with_effects, mock_effect_manager
    ):
        """spawn_enemy() creates a pending spawn, not an immediate tank."""
        sm = spawn_manager_with_effects
        assert len(sm.enemy_tanks) == 0
        assert len(sm._pending_spawns) == 1
        assert sm.total_enemy_spawns == 1
        mock_effect_manager.spawn.assert_called_once_with(EffectType.SPAWN, ANY, ANY)

    def test_update_materializes_when_effect_done(
        self, spawn_manager_with_effects, mock_player_tank, mock_game_map
    ):
        """update() materializes the tank when spawn effect finishes."""
        sm = spawn_manager_with_effects
        assert len(sm._pending_spawns) == 1

        sm._pending_spawns[0].effect.active = False
        sm.update(0.01, mock_player_tank, mock_game_map)

        assert len(sm._pending_spawns) == 0
        assert len(sm.enemy_tanks) == 1

    def test_update_keeps_active_pending_spawns(
        self, spawn_manager_with_effects, mock_player_tank, mock_game_map
    ):
        """update() keeps pending spawns whose effect is still playing."""
        sm = spawn_manager_with_effects
        sm._pending_spawns[0].effect.active = True
        sm.update(0.01, mock_player_tank, mock_game_map)

        assert len(sm._pending_spawns) == 1
        assert len(sm.enemy_tanks) == 0

    def test_all_enemies_defeated_false_with_pending(self, spawn_manager_with_effects):
        """all_enemies_defeated() returns False while spawns are pending."""
        sm = spawn_manager_with_effects
        sm.total_enemy_spawns = sm.max_enemy_spawns
        sm.enemy_tanks = []
        assert not sm.all_enemies_defeated()

    def test_all_enemies_defeated_true_when_clear(self, spawn_manager_with_effects):
        """all_enemies_defeated() returns True when no tanks or pending."""
        sm = spawn_manager_with_effects
        sm.total_enemy_spawns = sm.max_enemy_spawns
        sm.enemy_tanks = []
        sm._pending_spawns = []
        assert sm.all_enemies_defeated()

    @patch("random.choice")
    def test_pending_spawn_blocks_same_location(
        self,
        mock_random_choice,
        spawn_manager_with_effects,
        mock_player_tank,
        mock_game_map,
    ):
        """A new spawn at the same location is blocked by a pending one."""
        sm = spawn_manager_with_effects
        pending = sm._pending_spawns[0]

        # Force next spawn to pick the same point as the pending spawn
        grid_x = pending.x // SUB_TILE_SIZE
        grid_y = pending.y // SUB_TILE_SIZE
        mock_random_choice.return_value = (grid_x, grid_y)

        result = sm.spawn_enemy(mock_player_tank, mock_game_map)
        assert result is False


class TestSpawnManagerCarrier:
    """Tests for carrier index marking in SpawnManager."""

    SPAWN_POINTS = TestSpawnManager.SPAWN_POINTS

    @pytest.fixture
    def mock_player_tank(self):
        player = MagicMock()
        player.rect = pygame.Rect(7 * TILE_SIZE, 14 * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        return player

    @pytest.fixture
    def mock_game_map(self):
        game_map = MagicMock()
        game_map.get_collidable_tiles.return_value = []
        game_map.spawn_points = self.SPAWN_POINTS
        game_map.width_px = 16 * TILE_SIZE
        game_map.height_px = 16 * TILE_SIZE
        game_map.tile_size = SUB_TILE_SIZE
        game_map.grid_to_pixels.side_effect = lambda gx, gy: (
            gx * SUB_TILE_SIZE,
            gy * SUB_TILE_SIZE,
        )
        return game_map

    @pytest.fixture
    def spawn_manager(self, mock_texture_manager, mock_player_tank, mock_game_map):
        return SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=_DEFAULT_COMPOSITION,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
        )

    def test_fourth_enemy_is_carrier(
        self, spawn_manager, mock_player_tank, mock_game_map
    ):
        # Initial spawn was enemy 0 (index 0). Spawn indices 1, 2, 3.
        # Clear enemy_tanks between spawns to avoid collision blocking.
        spawn_manager.enemy_tanks = []
        spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)
        spawn_manager.enemy_tanks = []
        spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)
        spawn_manager.enemy_tanks = []
        spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)
        # The 4th tank (index 3) should be the carrier
        carrier_tanks = [t for t in spawn_manager.enemy_tanks if t.is_carrier]
        assert len(carrier_tanks) == 1

    def test_non_carrier_indices(self, spawn_manager, mock_player_tank, mock_game_map):
        # Spawn indices 1 and 2 — neither should be a carrier.
        spawn_manager.enemy_tanks = []
        spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)
        spawn_manager.enemy_tanks = []
        spawn_manager.spawn_enemy(mock_player_tank, mock_game_map)
        # Enemies at indices 1 and 2 should not be carriers
        carrier_tanks = [t for t in spawn_manager.enemy_tanks if t.is_carrier]
        assert len(carrier_tanks) == 0

    def test_carrier_survives_pending_spawn_path(
        self, mock_texture_manager, mock_player_tank, mock_game_map
    ):
        mock_effect_manager = MagicMock(spec=EffectManager)
        mock_effect = MagicMock(spec=Effect)
        mock_effect.active = True
        mock_effect_manager.spawn.return_value = mock_effect

        manager = SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=_DEFAULT_COMPOSITION,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
            effect_manager=mock_effect_manager,
        )
        # Materialize spawns 0, 1, 2 immediately, then spawn index 3 (carrier)
        # via the pending path. Clear pending+tanks between to avoid collisions.
        for _ in range(2):
            mock_effect.active = False
            manager.update(0.0, mock_player_tank, mock_game_map)
            manager.enemy_tanks = []
            mock_effect.active = True
            manager.spawn_enemy(mock_player_tank, mock_game_map)
        # Now materialize spawns so far, then spawn the carrier (index 3)
        mock_effect.active = False
        manager.update(0.0, mock_player_tank, mock_game_map)
        manager.enemy_tanks = []
        mock_effect.active = True
        manager.spawn_enemy(mock_player_tank, mock_game_map)
        # Complete the carrier's pending spawn animation
        mock_effect.active = False
        manager.update(0.0, mock_player_tank, mock_game_map)
        carrier_tanks = [t for t in manager.enemy_tanks if t.is_carrier]
        assert len(carrier_tanks) == 1


class TestSpawnManagerCustomCarriers:
    """Tests for custom powerup_carrier_indices parameter."""

    SPAWN_POINTS = TestSpawnManager.SPAWN_POINTS

    @pytest.fixture
    def mock_player_tank(self):
        player = MagicMock()
        player.rect = pygame.Rect(7 * TILE_SIZE, 14 * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        return player

    @pytest.fixture
    def mock_game_map(self):
        game_map = MagicMock()
        game_map.get_collidable_tiles.return_value = []
        game_map.spawn_points = self.SPAWN_POINTS
        game_map.width_px = 16 * TILE_SIZE
        game_map.height_px = 16 * TILE_SIZE
        game_map.tile_size = SUB_TILE_SIZE
        game_map.grid_to_pixels.side_effect = lambda gx, gy: (
            gx * SUB_TILE_SIZE,
            gy * SUB_TILE_SIZE,
        )
        return game_map

    def test_custom_carrier_indices_used(
        self, mock_texture_manager, mock_player_tank, mock_game_map
    ):
        """SpawnManager uses custom carrier indices instead of default."""
        # Set carrier at index 1 (the 2nd enemy spawned)
        manager = SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=_DEFAULT_COMPOSITION,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
            powerup_carrier_indices=(1,),
        )
        # Initial spawn is index 0 (not a carrier)
        assert not manager.enemy_tanks[0].is_carrier

        # Next spawn is index 1 (should be a carrier)
        manager.enemy_tanks = []
        manager.spawn_enemy(mock_player_tank, mock_game_map)
        carrier_tanks = [t for t in manager.enemy_tanks if t.is_carrier]
        assert len(carrier_tanks) == 1

    def test_default_carrier_indices_when_not_provided(
        self, mock_texture_manager, mock_player_tank, mock_game_map
    ):
        """SpawnManager falls back to POWERUP_CARRIER_INDICES when not provided."""
        from src.utils.constants import POWERUP_CARRIER_INDICES

        manager = SpawnManager(
            texture_manager=mock_texture_manager,
            game_map=mock_game_map,
            enemy_composition=_DEFAULT_COMPOSITION,
            spawn_interval=5.0,
            player_tank=mock_player_tank,
        )
        assert manager._powerup_carrier_indices == POWERUP_CARRIER_INDICES
