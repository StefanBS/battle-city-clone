"""Unit tests for PlayerManager."""

from __future__ import annotations

import pytest
import pygame
from unittest.mock import MagicMock

from src.core.bullet import Bullet
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.core.tile import Tile
from src.managers.player_input import (
    CombinedInput,
    ControllerInput,
    KeyboardInput,
    PlayerInput,
)
from src.managers.player_manager import PlayerManager
from src.managers.sound_manager import SoundManager
from src.utils.constants import TILE_SIZE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sound_manager():
    """Mock SoundManager."""
    return MagicMock(spec=SoundManager)


@pytest.fixture
def player_manager(mock_texture_manager, mock_sound_manager):
    """PlayerManager with mock dependencies."""
    return PlayerManager(mock_texture_manager, mock_sound_manager)


@pytest.fixture
def mock_game_map():
    """Mock Map with typical spawn / dimension attributes."""
    game_map = MagicMock(spec=Map)
    game_map.player_spawn = (4, 24)
    game_map.width = 26
    game_map.height = 26
    game_map.tile_size = TILE_SIZE
    game_map.grid_to_pixels.side_effect = lambda gx, gy: (
        gx * TILE_SIZE,
        gy * TILE_SIZE,
    )
    # Default: no ice tile under any tank
    game_map.get_tile_at.return_value = None
    return game_map


# ---------------------------------------------------------------------------
# Helper: create a real PlayerTank backed by the mock texture manager
# ---------------------------------------------------------------------------


def _make_player(mock_tm, x=0, y=0, tile_size=TILE_SIZE, map_size_tiles=26):
    """Return a real PlayerTank for use in tests."""
    px = map_size_tiles * tile_size
    return PlayerTank(x, y, tile_size, mock_tm, map_width_px=px, map_height_px=px)


# ---------------------------------------------------------------------------
# TestPlayerManagerCreation
# ---------------------------------------------------------------------------


class TestPlayerManagerCreation:
    def test_initial_players_empty(self, player_manager):
        """No players exist before create_players() is called."""
        assert player_manager.get_active_players() == []

    def test_initial_bullets_empty(self, player_manager):
        """No bullets exist before create_players() is called."""
        assert player_manager.get_all_bullets() == []

    def test_create_players_single_player(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """create_players() produces exactly one active player."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        players = player_manager.get_active_players()
        assert len(players) == 1
        assert isinstance(players[0], PlayerTank)

    def test_create_players_sets_correct_position(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Player tank is placed at the map's player_spawn coordinates."""
        mock_game_map.player_spawn = (3, 22)
        mock_game_map.tile_size = TILE_SIZE

        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager.get_active_players()[0]
        expected_x = 3 * TILE_SIZE
        expected_y = 22 * TILE_SIZE
        assert player.x == expected_x
        assert player.y == expected_y

    def test_create_players_1p_is_combined_input(
        self, player_manager, mock_game_map
    ) -> None:
        """1P always wraps keyboard + non-filtering controller in CombinedInput.

        Uses ControllerInput(instance_id=None) regardless of whether a
        controller is currently plugged in, so hot-plugging Just Works.
        """
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        pi = player_manager._player_inputs[0]
        assert isinstance(pi, CombinedInput)
        assert len(pi._inputs) == 2
        assert isinstance(pi._inputs[0], KeyboardInput)
        assert isinstance(pi._inputs[1], ControllerInput)
        assert pi._inputs[1].instance_id is None

    def test_create_players_1p_combined_ignores_instance_ids(
        self, player_manager, mock_game_map
    ) -> None:
        player_manager.create_players(mock_game_map, controller_instance_ids=[7])
        pi = player_manager._player_inputs[0]
        assert isinstance(pi, CombinedInput)
        assert pi._inputs[1].instance_id is None

    def test_create_players_clears_previous_state(self, player_manager, mock_game_map):
        """Calling create_players() twice resets players, inputs, and bullets."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        # Manually add a bullet to the list
        player_manager._bullets.append(MagicMock(spec=Bullet))
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        assert len(player_manager._players) == 1
        assert len(player_manager._bullets) == 0

    def test_get_active_players_returns_living(self, player_manager, mock_game_map):
        """get_active_players() filters out dead tanks."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager._players[0].health = 0
        assert player_manager.get_active_players() == []

    def test_get_all_bullets_empty_initially(self, player_manager, mock_game_map):
        """No bullets exist immediately after create_players()."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        assert player_manager.get_all_bullets() == []


# ---------------------------------------------------------------------------
# TestPlayerManagerUpdate
# ---------------------------------------------------------------------------


class TestPlayerManagerUpdate:
    @pytest.fixture(autouse=True)
    def setup(self, player_manager, mock_game_map, mock_texture_manager):
        """Create a single player before each test in this class."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        self.pm = player_manager
        self.game_map = mock_game_map

    def test_update_calls_player_update(self):
        """player.update(dt) is called for each living player."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.on_ice = False
        player.is_sliding = False
        player.direction = MagicMock()
        player.direction.delta = (0, 0)
        player.x = 0.0
        player.y = 0.0
        player.width = TILE_SIZE
        player.height = TILE_SIZE
        self.pm._players = [player]
        # Pair with a keyboard input that has no keys pressed
        self.pm._player_inputs = [KeyboardInput()]

        self.pm.update(0.016, self.game_map)

        player.update.assert_called_once_with(0.016)

    def test_update_skips_dead_player(self):
        """Dead players (health == 0) are skipped entirely."""
        player = MagicMock(spec=PlayerTank)
        player.health = 0
        self.pm._players = [player]
        self.pm._player_inputs = [KeyboardInput()]

        self.pm.update(0.016, self.game_map)

        player.update.assert_not_called()

    def test_movement_applied_on_valid_input(self, mock_texture_manager):
        """Player.move() is called when a valid (non-diagonal) direction is active."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.on_ice = False
        player.is_sliding = False
        player.direction = MagicMock()
        player.direction.delta = (0, -1)
        player.x = 0.0
        player.y = 0.0
        player.width = TILE_SIZE
        player.height = TILE_SIZE
        self.pm._players = [player]

        pi = KeyboardInput()
        pi.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        self.pm._player_inputs = [pi]

        self.pm.update(0.016, self.game_map)

        player.move.assert_called_once_with(0, -1, 0.016)

    def test_diagonal_input_does_not_move(self):
        """Diagonal input (dx and dy both non-zero) is rejected."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.on_ice = False
        player.is_sliding = False
        player.direction = MagicMock()
        player.direction.delta = (0, 0)
        player.x = 0.0
        player.y = 0.0
        player.width = TILE_SIZE
        player.height = TILE_SIZE
        self.pm._players = [player]

        pi = KeyboardInput()
        # Press both UP and RIGHT simultaneously
        pi.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        pi.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        self.pm._player_inputs = [pi]

        self.pm.update(0.016, self.game_map)

        player.move.assert_not_called()

    def test_sliding_player_does_not_move_via_input(self):
        """A player that is_sliding does not receive a move() call."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.on_ice = False
        player.is_sliding = True
        player.direction = MagicMock()
        player.direction.delta = (0, -1)
        player.x = 0.0
        player.y = 0.0
        player.width = TILE_SIZE
        player.height = TILE_SIZE
        self.pm._players = [player]

        pi = KeyboardInput()
        pi.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        self.pm._player_inputs = [pi]

        self.pm.update(0.016, self.game_map)

        player.move.assert_not_called()

    def test_ice_slide_starts_when_on_ice_and_no_valid_input(self, mock_sound_manager):
        """start_slide() is called (and ice sound plays) when on ice with no input."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.is_frozen = False
        player.is_sliding = False
        player.direction = MagicMock()
        player.direction.delta = (0, -1)

        # Simulate ice tile under tank
        ice_tile = MagicMock(spec=Tile)
        ice_tile.is_slidable = True
        self.game_map.get_tile_at.return_value = ice_tile
        player.start_slide.return_value = True

        # Mock width/height for centre calculation
        player.x = 0
        player.y = 0
        player.width = TILE_SIZE
        player.height = TILE_SIZE

        self.pm._players = [player]
        self.pm._player_inputs = [KeyboardInput()]  # no keys pressed

        self.pm.update(0.016, self.game_map)

        player.start_slide.assert_called_once()
        self.pm._sound_manager.play.assert_called_once_with("ice_slide")

    def test_bullets_updated_during_update(self):
        """Active bullets have update(dt) called."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        self.pm._bullets = [bullet]

        self.pm.update(0.016, self.game_map)

        bullet.update.assert_called_once_with(0.016)

    def test_inactive_bullets_pruned_after_update(self):
        """Inactive bullets are removed from the internal list after update."""
        bullet = MagicMock(spec=Bullet)
        bullet.active = False
        self.pm._bullets = [bullet]

        self.pm.update(0.016, self.game_map)

        assert self.pm._bullets == []


# ---------------------------------------------------------------------------
# TestPlayerManagerShooting
# ---------------------------------------------------------------------------


class TestPlayerManagerShooting:
    @pytest.fixture(autouse=True)
    def setup(self, player_manager, mock_game_map):
        """Create a single player before each test in this class."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        self.pm = player_manager

    def test_try_shoot_creates_bullet(self, mock_sound_manager):
        """try_shoot() appends a bullet and plays the shoot sound."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.max_bullets = 1

        bullet = MagicMock(spec=Bullet)
        bullet.active = True
        bullet.owner = player
        player.shoot.return_value = bullet

        self.pm._players = [player]
        pi = KeyboardInput()
        pi._shoot_pressed = True  # simulate a shoot press
        self.pm._player_inputs = [pi]

        self.pm.try_shoot()

        player.shoot.assert_called_once()
        assert bullet in self.pm._bullets
        self.pm._sound_manager.play.assert_called_once_with("shoot")

    def test_try_shoot_no_bullet_without_input(self, mock_sound_manager):
        """try_shoot() does nothing when shoot was not pressed."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.max_bullets = 1

        self.pm._players = [player]
        self.pm._player_inputs = [KeyboardInput()]

        self.pm.try_shoot()

        player.shoot.assert_not_called()
        self.pm._sound_manager.play.assert_not_called()

    def test_try_shoot_respects_max_bullets(self):
        """No new bullet is created when max_bullets are already active."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.max_bullets = 1

        existing_bullet = MagicMock(spec=Bullet)
        existing_bullet.active = True
        existing_bullet.owner = player
        self.pm._bullets = [existing_bullet]

        self.pm._players = [player]
        pi = KeyboardInput()
        pi._shoot_pressed = True
        self.pm._player_inputs = [pi]

        self.pm.try_shoot()

        player.shoot.assert_not_called()

    def test_try_shoot_skips_dead_player(self):
        """Dead players cannot shoot."""
        player = MagicMock(spec=PlayerTank)
        player.health = 0
        player.max_bullets = 1

        self.pm._players = [player]
        pi = KeyboardInput()
        pi._shoot_pressed = True
        self.pm._player_inputs = [pi]

        self.pm.try_shoot()

        player.shoot.assert_not_called()

    def test_try_shoot_none_bullet_not_appended(self):
        """If player.shoot() returns None the bullet list is unchanged."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.max_bullets = 1
        player.shoot.return_value = None

        self.pm._players = [player]
        pi = KeyboardInput()
        pi._shoot_pressed = True
        self.pm._player_inputs = [pi]

        self.pm.try_shoot()

        assert self.pm._bullets == []


# ---------------------------------------------------------------------------
# TestPlayerManagerHandleEvent
# ---------------------------------------------------------------------------


class TestPlayerManagerHandleEvent:
    def test_handle_event_forwarded_to_player_input(
        self, player_manager, mock_game_map
    ):
        """handle_event() propagates the event to the PlayerInput."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        pi = MagicMock(spec=PlayerInput)
        player_manager._player_inputs = [pi]

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        player_manager.handle_event(event)

        pi.handle_event.assert_called_once_with(event)


# ---------------------------------------------------------------------------
# TestPlayerManagerScore
# ---------------------------------------------------------------------------


class TestPlayerManagerScore:
    def test_initial_score_zero(self, player_manager):
        """Score is 0 immediately after construction."""
        assert player_manager.score == 0

    def test_add_score_increments(self, player_manager):
        """add_score(100) raises the score to 100."""
        player_manager.add_score(100)
        assert player_manager.score == 100

    def test_add_score_accumulates(self, player_manager):
        """Multiple add_score() calls accumulate correctly."""
        player_manager.add_score(200)
        player_manager.add_score(300)
        assert player_manager.score == 500


# ---------------------------------------------------------------------------
# TestPlayerManagerStatePreservation
# ---------------------------------------------------------------------------


class TestPlayerManagerStatePreservation:
    def test_preserve_and_restore_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Preserved lives are restored onto a new player tank."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager._players[0].lives = 5
        player_manager.preserve_state()

        # Simulate stage transition: create fresh tanks
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.restore_state()

        assert player_manager._players[0].lives == 5

    def test_preserve_and_restore_star_level(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Preserved star_level is restored onto a new player tank."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager._players[0].restore_star_level(2)
        player_manager.preserve_state()

        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.restore_state()

        assert player_manager._players[0].star_level == 2

    def test_restore_with_no_preserved_state(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """restore_state() with empty preserved state does not crash."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        # _preserved_state is empty by default — should not raise
        player_manager.restore_state()

        # Player remains in default state
        assert player_manager._players[0].lives >= 0


# ---------------------------------------------------------------------------
# TestPlayerManagerDeathHandling
# ---------------------------------------------------------------------------


class TestPlayerManagerDeathHandling:
    def test_handle_death_with_lives_respawns(self, player_manager, mock_game_map):
        """handle_player_death calls respawn() and returns False when lives remain."""
        player = MagicMock(spec=PlayerTank)
        player.lives = 2
        player.health = 0

        result = player_manager.handle_player_death(player)

        player.respawn.assert_called_once()
        assert result is False

    def test_handle_death_no_lives_returns_game_over(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """handle_player_death returns True when the last player is eliminated."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager._players[0]
        player.lives = 0
        player.health = 0

        result = player_manager.handle_player_death(player)

        assert result is True

    def test_handle_death_no_lives_but_health_positive(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Edge case: lives = 0 but health > 0 — is_game_over returns False."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager._players[0]
        player.lives = 0
        player.health = 1  # unusual state: out of lives but not fully dead

        result = player_manager.handle_player_death(player)

        # health > 0 means is_game_over() returns False
        assert result is False


# ---------------------------------------------------------------------------
# TestPlayerManagerGameOver
# ---------------------------------------------------------------------------


class TestPlayerManagerGameOver:
    def test_not_game_over_when_alive(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns False when the player is still alive."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager._players[0]
        player.health = 1
        player.lives = 2

        assert player_manager.is_game_over() is False

    def test_game_over_when_dead_no_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns True when the player is dead with no lives."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager._players[0]
        player.health = 0
        player.lives = 0

        assert player_manager.is_game_over() is True

    def test_not_game_over_when_has_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns False when the player is dead but has lives left."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager._players[0]
        player.health = 0
        player.lives = 1  # dead this frame but can still respawn

        assert player_manager.is_game_over() is False


# ---------------------------------------------------------------------------
# TestPlayerManagerReset
# ---------------------------------------------------------------------------


class TestPlayerManagerReset:
    def test_reset_clears_all_state(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """reset() clears players, inputs, bullets, score, and preserved state."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.add_score(500)
        player_manager._bullets.append(MagicMock(spec=Bullet))
        player_manager._preserved_state = {0: {"lives": 3, "star_level": 1}}

        player_manager.reset()

        assert player_manager._players == []
        assert player_manager._player_inputs == []
        assert player_manager._bullets == []
        assert player_manager.score == 0
        assert player_manager._preserved_state == {}


# ---------------------------------------------------------------------------
# TestPlayerManagerTwoPlayerCreation
# ---------------------------------------------------------------------------


class TestPlayerManagerTwoPlayerCreation:
    def test_create_two_players(self, player_manager, mock_game_map):
        """create_players(two_player_mode=True) produces two active players."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], two_player_mode=True
        )
        players = player_manager.get_active_players()
        assert len(players) == 2

    def test_player2_has_player_id_2(self, player_manager, mock_game_map):
        """Second player has player_id=2."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], two_player_mode=True
        )
        assert player_manager._players[0].player_id == 1
        assert player_manager._players[1].player_id == 2

    def test_player2_at_spawn_2_position(self, player_manager, mock_game_map):
        """Player 2 spawns at player_spawn_2 coordinates."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], two_player_mode=True
        )
        p2 = player_manager._players[1]
        assert p2.x == 16 * TILE_SIZE
        assert p2.y == 24 * TILE_SIZE

    def test_2p_one_controller_input(self, player_manager, mock_game_map):
        """2P + 1 controller: P1=keyboard, P2=controller bound by instance_id."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[4], two_player_mode=True
        )
        assert isinstance(player_manager._player_inputs[0], KeyboardInput)
        assert isinstance(player_manager._player_inputs[1], ControllerInput)
        assert player_manager._player_inputs[1].instance_id == 4

    def test_2p_two_controllers_both_controller(self, player_manager, mock_game_map):
        """2P + 2 controllers: each player bound to its own instance_id."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[8, 12], two_player_mode=True
        )
        assert isinstance(player_manager._player_inputs[0], ControllerInput)
        assert player_manager._player_inputs[0].instance_id == 8
        assert isinstance(player_manager._player_inputs[1], ControllerInput)
        assert player_manager._player_inputs[1].instance_id == 12

    def test_2p_two_controllers_non_sequential_instance_ids(
        self, player_manager, mock_game_map
    ):
        """Regression: non-sequential instance_ids (e.g. 0 and 5) route correctly.

        Previously PlayerInput stored a device index that assumed 0-based
        sequential IDs, so plugging a second controller later whose SDL
        instance_id wasn't 1 broke per-player routing.
        """
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0, 5], two_player_mode=True
        )
        assert player_manager._player_inputs[0].instance_id == 0
        assert player_manager._player_inputs[1].instance_id == 5

    def test_2p_fallback_spawn_when_no_spawn_2(self, player_manager, mock_game_map):
        """When player_spawn_2 is absent, derive P2 position from P1."""
        mock_game_map.player_spawn_2 = None
        mock_game_map.player_spawn = (8, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], two_player_mode=True
        )
        p2 = player_manager._players[1]
        assert p2.x == (8 + 8) * TILE_SIZE
        assert p2.y == 24 * TILE_SIZE

    def test_2p_per_player_scores(self, player_manager, mock_game_map):
        """Per-player scores start at 0 and accumulate independently."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], two_player_mode=True
        )
        player_manager.add_score(100, player_id=1)
        player_manager.add_score(200, player_id=2)
        assert player_manager.get_score(1) == 100
        assert player_manager.get_score(2) == 200
        assert player_manager.score == 300

    def test_1p_add_score_backward_compatible(self, player_manager, mock_game_map):
        """add_score() without player_id works for 1P."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        player_manager.add_score(100)
        assert player_manager.score == 100

    def test_2p_no_controllers_both_keyboard(self, player_manager, mock_game_map):
        """2P + 0 controllers: both players fall back to keyboard (degenerate).

        This mode is not playable (P1 and P2 both fight for arrow keys) but
        must not crash; the UI guards against entering it.
        """
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[], two_player_mode=True
        )

        assert isinstance(player_manager._player_inputs[0], KeyboardInput)
        assert isinstance(player_manager._player_inputs[1], KeyboardInput)


# ---------------------------------------------------------------------------
# TestPlayerManagerTwoPlayerDeath
# ---------------------------------------------------------------------------


class TestPlayerManagerTwoPlayerDeath:
    @pytest.fixture
    def two_player_pm(self, player_manager, mock_game_map):
        """Create a 2P PlayerManager."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], two_player_mode=True
        )
        return player_manager

    def test_dead_player_does_not_borrow_from_partner(self, two_player_pm):
        """Each player has their own life pool — no transfers between players."""
        p1 = two_player_pm._players[0]
        p2 = two_player_pm._players[1]
        p1.lives = 0
        p1.health = 0
        p2.lives = 3

        result = two_player_pm.handle_player_death(p1)

        assert result is False  # game continues because p2 is still alive
        assert p2.lives == 3  # untouched
        assert p1.lives == 0  # stays dead

    def test_game_over_when_last_player_dies(self, two_player_pm):
        """Game ends when the surviving player loses their last life."""
        p1 = two_player_pm._players[0]
        p2 = two_player_pm._players[1]
        p1.lives = 0
        p1.health = 0
        p2.lives = 0
        p2.health = 0

        assert two_player_pm.handle_player_death(p2) is True

    def test_game_over_only_when_both_eliminated(self, two_player_pm):
        """is_game_over() is True only when both players are dead with 0 lives."""
        p1 = two_player_pm._players[0]
        p2 = two_player_pm._players[1]

        p1.lives = 0
        p1.health = 0
        p2.lives = 2
        p2.health = 1
        assert two_player_pm.is_game_over() is False

        p2.lives = 0
        p2.health = 0
        assert two_player_pm.is_game_over() is True
