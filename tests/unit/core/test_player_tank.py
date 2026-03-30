import pytest
import pygame
from unittest.mock import MagicMock
from src.core.player_tank import PlayerTank
from src.utils.constants import Direction, TILE_SIZE, FPS


class TestPlayerTank:
    """Test cases for the PlayerTank class."""

    @pytest.fixture
    def player_tank(self, mock_texture_manager):
        """Fixture to create a PlayerTank instance."""
        return PlayerTank(
            5,
            12,
            TILE_SIZE,
            mock_texture_manager,
            map_width_px=16 * TILE_SIZE,
            map_height_px=16 * TILE_SIZE,
        )

    def test_player_tank_initialization(self, player_tank):
        """Test PlayerTank initialization aligns to grid and sets correct defaults."""
        assert player_tank.x == 0
        assert player_tank.y == 0
        assert player_tank.initial_position == (0, 0)
        assert player_tank.lives == 3
        assert player_tank.health == 1
        assert player_tank.invincibility_duration == 3.0
        assert not player_tank.is_invincible

    def test_player_tank_no_input_handler(self, player_tank):
        """Test that PlayerTank does not own an InputHandler."""
        assert not hasattr(player_tank, "input_handler")

    def test_player_tank_no_handle_event(self, player_tank):
        """Test that PlayerTank does not have a handle_event method."""
        assert not hasattr(player_tank, "handle_event")

    @pytest.mark.parametrize(
        "dx,dy,expected_direction",
        [
            (1, 0, Direction.RIGHT),
            (-1, 0, Direction.LEFT),
            (0, 1, Direction.DOWN),
            (0, -1, Direction.UP),
        ],
    )
    def test_move_sets_direction(self, player_tank, dx, dy, expected_direction):
        """Test that move() sets the correct direction."""
        dt = 1.0 / FPS
        player_tank.prev_x = player_tank.x
        player_tank.prev_y = player_tank.y
        player_tank.move(dx, dy, dt)
        assert player_tank.direction == expected_direction

    def test_move_zero_does_nothing(self, player_tank):
        """Test that move(0, 0) doesn't change direction."""
        dt = 1.0 / FPS
        initial_direction = player_tank.direction
        player_tank.move(0, 0, dt)
        assert player_tank.direction == initial_direction

    def test_player_tank_respawn(self, player_tank):
        """Test player tank respawn functionality."""
        initial_lives = player_tank.lives
        initial_health = player_tank.max_health
        initial_pos = player_tank.initial_position

        player_tank.health = player_tank.max_health
        player_tank.lives -= 1

        player_tank.respawn()

        assert player_tank.lives == initial_lives - 1
        assert player_tank.health == initial_health
        assert (player_tank.x, player_tank.y) == initial_pos
        assert player_tank.is_invincible
        assert player_tank.invincibility_timer == 0
        assert player_tank.blink_timer == 0
        assert player_tank.direction == Direction.UP

    def test_player_tank_respawn_no_lives_left(self, player_tank):
        """Test respawn does nothing if no lives are left."""
        player_tank.lives = 0
        player_tank.health = 0

        player_tank.respawn()

        assert player_tank.health == 0
        assert player_tank.lives == 0

    def test_update_only_calls_super(self, player_tank):
        """Test that update() only calls super().update() — no input logic."""
        dt = 0.1
        initial_x = player_tank.x
        initial_y = player_tank.y

        player_tank.update(dt)

        assert player_tank.x == initial_x
        assert player_tank.y == initial_y

    def test_draw_with_sprite_not_invincible(self, player_tank):
        """Test drawing with sprite when not invincible."""
        mock_surface = MagicMock(spec=pygame.Surface)
        mock_sprite = MagicMock(spec=pygame.Surface)
        player_tank.is_invincible = False
        player_tank.sprite = mock_sprite

        player_tank.draw(mock_surface)

        mock_surface.blit.assert_called_once_with(mock_sprite, player_tank.rect)

    def test_draw_no_sprite_not_invincible(self, player_tank):
        """Test drawing without sprite when not invincible does nothing."""
        mock_surface = MagicMock(spec=pygame.Surface)
        player_tank.is_invincible = False
        player_tank.sprite = None

        player_tank.draw(mock_surface)

        mock_surface.blit.assert_not_called()

    def test_draw_invincible_visible_phase(self, player_tank):
        """Test drawing when invincible during the visible phase of blinking."""
        mock_surface = MagicMock(spec=pygame.Surface)
        mock_sprite = MagicMock(spec=pygame.Surface)
        player_tank.is_invincible = True
        player_tank.blink_timer = player_tank.blink_interval * 0.5
        player_tank.sprite = mock_sprite

        player_tank.draw(mock_surface)

        mock_surface.blit.assert_called_once_with(mock_sprite, player_tank.rect)

    def test_draw_invincible_invisible_phase(self, player_tank):
        """Test drawing when invincible during the invisible phase of blinking."""
        mock_surface = MagicMock(spec=pygame.Surface)
        mock_sprite = MagicMock(spec=pygame.Surface)
        player_tank.is_invincible = True
        player_tank.blink_timer = player_tank.blink_interval * 1.5
        player_tank.sprite = mock_sprite

        player_tank.draw(mock_surface)

        mock_surface.blit.assert_not_called()
