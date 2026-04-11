"""Unit tests for PlayerManager."""

from __future__ import annotations

import pytest
import pygame
from unittest.mock import MagicMock, patch

from src.core.bullet import Bullet
from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.core.tile import Tile
from src.managers.player_input import InputSource, PlayerInput
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
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        players = player_manager.get_active_players()
        assert len(players) == 1
        assert isinstance(players[0], PlayerTank)

    def test_create_players_sets_correct_position(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Player tank is placed at the map's player_spawn coordinates."""
        mock_game_map.player_spawn = (3, 22)
        mock_game_map.tile_size = TILE_SIZE

        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player = player_manager.get_active_players()[0]
        expected_x = 3 * TILE_SIZE
        expected_y = 22 * TILE_SIZE
        assert player.x == expected_x
        assert player.y == expected_y

    def test_create_players_keyboard_when_no_joystick(
        self, player_manager, mock_game_map
    ):
        """Keyboard input source is assigned when no joystick is present."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        assert player_manager._player_inputs[0].source == InputSource.KEYBOARD

    def test_create_players_joystick_when_available(
        self, player_manager, mock_game_map
    ):
        """Joystick input source is assigned when a joystick is detected."""
        with patch("pygame.joystick.get_count", return_value=1):
            player_manager.create_players(mock_game_map)

        assert player_manager._player_inputs[0].source == InputSource.JOYSTICK

    def test_create_players_clears_previous_state(self, player_manager, mock_game_map):
        """Calling create_players() twice resets players, inputs, and bullets."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)
            # Manually add a bullet to the list
            player_manager._bullets.append(MagicMock(spec=Bullet))
            player_manager.create_players(mock_game_map)

        assert len(player_manager._players) == 1
        assert len(player_manager._bullets) == 0

    def test_get_active_players_returns_living(self, player_manager, mock_game_map):
        """get_active_players() filters out dead tanks."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player_manager._players[0].health = 0
        assert player_manager.get_active_players() == []

    def test_get_all_bullets_empty_initially(self, player_manager, mock_game_map):
        """No bullets exist immediately after create_players()."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        assert player_manager.get_all_bullets() == []


# ---------------------------------------------------------------------------
# TestPlayerManagerUpdate
# ---------------------------------------------------------------------------


class TestPlayerManagerUpdate:
    @pytest.fixture(autouse=True)
    def setup(self, player_manager, mock_game_map, mock_texture_manager):
        """Create a single player before each test in this class."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)
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
        self.pm._player_inputs = [PlayerInput(InputSource.KEYBOARD)]

        self.pm.update(0.016, self.game_map)

        player.update.assert_called_once_with(0.016)

    def test_update_skips_dead_player(self):
        """Dead players (health == 0) are skipped entirely."""
        player = MagicMock(spec=PlayerTank)
        player.health = 0
        self.pm._players = [player]
        self.pm._player_inputs = [PlayerInput(InputSource.KEYBOARD)]

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

        pi = PlayerInput(InputSource.KEYBOARD)
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

        pi = PlayerInput(InputSource.KEYBOARD)
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

        pi = PlayerInput(InputSource.KEYBOARD)
        pi.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        self.pm._player_inputs = [pi]

        self.pm.update(0.016, self.game_map)

        player.move.assert_not_called()

    def test_ice_slide_starts_when_on_ice_and_no_valid_input(self, mock_sound_manager):
        """start_slide() is called (and ice sound plays) when on ice with no input."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
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
        self.pm._player_inputs = [PlayerInput(InputSource.KEYBOARD)]  # no keys pressed

        self.pm.update(0.016, self.game_map)

        player.start_slide.assert_called_once()
        self.pm._sound_manager.play_ice_slide.assert_called_once()

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
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)
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
        pi = PlayerInput(InputSource.KEYBOARD)
        pi._shoot_pressed = True  # simulate a shoot press
        self.pm._player_inputs = [pi]

        self.pm.try_shoot()

        player.shoot.assert_called_once()
        assert bullet in self.pm._bullets
        self.pm._sound_manager.play_shoot.assert_called_once()

    def test_try_shoot_no_bullet_without_input(self, mock_sound_manager):
        """try_shoot() does nothing when shoot was not pressed."""
        player = MagicMock(spec=PlayerTank)
        player.health = 1
        player.max_bullets = 1

        self.pm._players = [player]
        self.pm._player_inputs = [PlayerInput(InputSource.KEYBOARD)]

        self.pm.try_shoot()

        player.shoot.assert_not_called()
        self.pm._sound_manager.play_shoot.assert_not_called()

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
        pi = PlayerInput(InputSource.KEYBOARD)
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
        pi = PlayerInput(InputSource.KEYBOARD)
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
        pi = PlayerInput(InputSource.KEYBOARD)
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
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

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
# TestPlayerManagerIsOnIce
# ---------------------------------------------------------------------------


class TestPlayerManagerIsOnIce:
    def test_not_on_ice_when_no_tile(self, player_manager, mock_game_map):
        """Returns False when get_tile_at returns None."""
        mock_game_map.get_tile_at.return_value = None

        player = MagicMock(spec=PlayerTank)
        player.x = 0
        player.y = 0
        player.width = TILE_SIZE
        player.height = TILE_SIZE

        assert player_manager._is_on_ice(player, mock_game_map) is False

    def test_not_on_ice_when_tile_not_slidable(self, player_manager, mock_game_map):
        """Returns False when tile.is_slidable is False."""
        brick_tile = MagicMock(spec=Tile)
        brick_tile.is_slidable = False
        mock_game_map.get_tile_at.return_value = brick_tile

        player = MagicMock(spec=PlayerTank)
        player.x = 0
        player.y = 0
        player.width = TILE_SIZE
        player.height = TILE_SIZE

        assert player_manager._is_on_ice(player, mock_game_map) is False

    def test_on_ice_when_tile_is_slidable(self, player_manager, mock_game_map):
        """Returns True when tile.is_slidable is True."""
        ice_tile = MagicMock(spec=Tile)
        ice_tile.is_slidable = True
        mock_game_map.get_tile_at.return_value = ice_tile

        player = MagicMock(spec=PlayerTank)
        player.x = 0
        player.y = 0
        player.width = TILE_SIZE
        player.height = TILE_SIZE

        assert player_manager._is_on_ice(player, mock_game_map) is True

    def test_tile_lookup_uses_tank_centre(self, player_manager, mock_game_map):
        """The tile is looked up at the tank's centre, not origin."""
        mock_game_map.get_tile_at.return_value = None
        mock_game_map.tile_size = TILE_SIZE

        player = MagicMock(spec=PlayerTank)
        player.x = float(2 * TILE_SIZE)
        player.y = float(3 * TILE_SIZE)
        player.width = TILE_SIZE
        player.height = TILE_SIZE

        player_manager._is_on_ice(player, mock_game_map)

        expected_grid_x = (2 * TILE_SIZE + TILE_SIZE // 2) // TILE_SIZE
        expected_grid_y = (3 * TILE_SIZE + TILE_SIZE // 2) // TILE_SIZE
        mock_game_map.get_tile_at.assert_called_once_with(
            expected_grid_x, expected_grid_y
        )


# ---------------------------------------------------------------------------
# TestPlayerManagerStatePreservation
# ---------------------------------------------------------------------------


class TestPlayerManagerStatePreservation:
    def test_preserve_and_restore_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Preserved lives are restored onto a new player tank."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player_manager._players[0].lives = 5
        player_manager.preserve_state()

        # Simulate stage transition: create fresh tanks
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player_manager.restore_state()

        assert player_manager._players[0].lives == 5

    def test_preserve_and_restore_star_level(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Preserved star_level is restored onto a new player tank."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player_manager._players[0].restore_star_level(2)
        player_manager.preserve_state()

        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player_manager.restore_state()

        assert player_manager._players[0].star_level == 2

    def test_restore_with_no_preserved_state(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """restore_state() with empty preserved state does not crash."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

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
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player = player_manager._players[0]
        player.lives = 0
        player.health = 0

        result = player_manager.handle_player_death(player)

        assert result is True

    def test_handle_death_no_lives_but_health_positive(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Edge case: lives = 0 but health > 0 — is_game_over returns False."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

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
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player = player_manager._players[0]
        player.health = 1
        player.lives = 2

        assert player_manager.is_game_over() is False

    def test_game_over_when_dead_no_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns True when the player is dead with no lives."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player = player_manager._players[0]
        player.health = 0
        player.lives = 0

        assert player_manager.is_game_over() is True

    def test_not_game_over_when_has_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns False when the player is dead but has lives left."""
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

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
        with patch("pygame.joystick.get_count", return_value=0):
            player_manager.create_players(mock_game_map)

        player_manager.add_score(500)
        player_manager._bullets.append(MagicMock(spec=Bullet))
        player_manager._preserved_state = {0: {"lives": 3, "star_level": 1}}

        player_manager.reset()

        assert player_manager._players == []
        assert player_manager._player_inputs == []
        assert player_manager._bullets == []
        assert player_manager.score == 0
        assert player_manager._preserved_state == {}
