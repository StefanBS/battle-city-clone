import pytest
import pygame
from unittest.mock import MagicMock, patch
from src.core.player_tank import PlayerTank
from src.managers.texture_manager import TextureManager
from src.utils.constants import TILE_SIZE


@pytest.fixture(scope="module")
def mock_texture_manager():
    """Create a module-scoped mock TextureManager."""
    pygame.init()
    mock_tm = MagicMock(spec=TextureManager)
    mock_tm.get_sprite.return_value = MagicMock(spec=pygame.Surface)
    yield mock_tm
    pygame.quit()


@pytest.fixture
def player_tank(mock_texture_manager):
    """Fixture to create a PlayerTank instance."""
    with patch("src.managers.input_handler.InputHandler") as MockInputHandler:
        mock_input_handler = MockInputHandler.return_value
        mock_input_handler.get_movement_direction.return_value = (
            0,
            0,
        )  # Default no movement
        tank = PlayerTank(5, 12, TILE_SIZE, mock_texture_manager)
        tank.input_handler = mock_input_handler
        yield tank


def test_player_tank_initialization(player_tank):
    """Test PlayerTank initialization aligns to grid and sets correct defaults."""
    assert player_tank.x == 0
    assert player_tank.y == 0
    assert player_tank.initial_position == (0, 0)
    assert player_tank.lives == 3
    assert player_tank.health == 1
    assert player_tank.invincibility_duration == 3.0
    assert not player_tank.is_invincible  # Should not start invincible


def test_player_tank_respawn(player_tank):
    """Test player tank respawn functionality."""
    initial_lives = player_tank.lives
    initial_health = player_tank.max_health  # Respawn resets to max health
    initial_pos = player_tank.initial_position

    # Simulate taking fatal damage (though PlayerTank doesn't have take_damage directly)
    player_tank.health = player_tank.max_health
    player_tank.lives -= 1

    # Call respawn
    player_tank.respawn()

    assert player_tank.lives == initial_lives - 1
    assert player_tank.health == initial_health
    assert (player_tank.x, player_tank.y) == initial_pos
    assert player_tank.target_position == initial_pos
    assert player_tank.is_invincible
    assert player_tank.invincibility_timer == 0
    assert player_tank.blink_timer == 0
    assert player_tank.direction == "up"  # Should reset direction


def test_player_tank_respawn_no_lives_left(player_tank):
    """Test respawn does nothing if no lives are left."""
    player_tank.lives = 0
    player_tank.health = 0

    # Attempt respawn
    player_tank.respawn()

    assert player_tank.health == 0
    assert player_tank.lives == 0


def test_handle_event_shoot(player_tank):
    """Test handling the shoot event."""
    player_tank.shoot = MagicMock()  # Mock the shoot method
    shoot_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
    player_tank.handle_event(shoot_event)
    player_tank.shoot.assert_called_once()


def test_handle_event_movement_input(player_tank):
    """Test that handle_event calls input_handler."""
    move_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
    player_tank.handle_event(move_event)
    player_tank.input_handler.handle_event.assert_called_with(move_event)


def test_handle_event_invincible(player_tank):
    """Test that events are ignored when invincible."""
    player_tank.is_invincible = True
    player_tank.shoot = MagicMock()
    shoot_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
    move_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)

    # Handle events while invincible
    player_tank.handle_event(shoot_event)
    player_tank.handle_event(move_event)

    # Methods should not have been called
    player_tank.shoot.assert_not_called()
    player_tank.input_handler.handle_event.assert_not_called()


def test_update_movement_direction(player_tank):
    """Test that update changes direction based on input."""
    dt = 0.1

    # Mock movement input and _move
    player_tank.input_handler.get_movement_direction.return_value = (1, 0)  # Move right
    player_tank._move = MagicMock(return_value=True)

    player_tank.update(dt)
    assert player_tank.direction == "right"
    player_tank._move.assert_called_once_with(1, 0)

    player_tank.input_handler.get_movement_direction.return_value = (-1, 0)  # Move left
    player_tank._move.reset_mock()
    player_tank.update(dt)
    assert player_tank.direction == "left"
    player_tank._move.assert_called_once_with(-1, 0)

    player_tank.input_handler.get_movement_direction.return_value = (0, 1)  # Move down
    player_tank._move.reset_mock()
    player_tank.update(dt)
    assert player_tank.direction == "down"
    player_tank._move.assert_called_once_with(0, 1)

    player_tank.input_handler.get_movement_direction.return_value = (0, -1)  # Move up
    player_tank._move.reset_mock()
    player_tank.update(dt)
    assert player_tank.direction == "up"
    player_tank._move.assert_called_once_with(0, -1)


def test_update_no_movement_input(player_tank):
    """Test that update doesn't change direction or move without input."""
    dt = 0.1
    initial_direction = player_tank.direction
    player_tank.input_handler.get_movement_direction.return_value = (
        0,
        0,
    )  # No movement
    player_tank._move = MagicMock()

    player_tank.update(dt)

    assert player_tank.direction == initial_direction
    player_tank._move.assert_not_called()


def test_update_invincible(player_tank):
    """Test that update does nothing (movement/shooting) when invincible."""
    player_tank.is_invincible = True
    dt = 0.1
    player_tank.input_handler.get_movement_direction.return_value = (
        1,
        0,
    )  # Try to move right
    player_tank._move = MagicMock()
    player_tank.update(dt)

    player_tank._move.assert_not_called()
    assert player_tank.direction == "up"


@patch("pygame.draw.rect")
def test_draw_no_sprite_not_invincible(mock_draw_rect, player_tank):
    """Test drawing without sprite when not invincible."""
    mock_surface = MagicMock(spec=pygame.Surface)
    player_tank.is_invincible = False
    player_tank.sprite = None  # Ensure no sprite

    player_tank.draw(mock_surface)

    mock_draw_rect.assert_called_once_with(mock_surface, (0, 255, 0), player_tank.rect)


def test_draw_with_sprite_not_invincible(player_tank):
    """Test drawing with sprite when not invincible."""
    mock_surface = MagicMock(spec=pygame.Surface)
    mock_sprite = MagicMock(spec=pygame.Surface)
    player_tank.is_invincible = False
    player_tank.sprite = mock_sprite

    player_tank.draw(mock_surface)

    # Assert that blit was called on the mock_surface instance
    mock_surface.blit.assert_called_once_with(mock_sprite, player_tank.rect)


@patch("pygame.draw.rect")
def test_draw_invincible_visible_phase(mock_draw_rect, player_tank):
    """Test drawing when invincible during the visible phase of blinking."""
    mock_surface = MagicMock(spec=pygame.Surface)
    player_tank.is_invincible = True
    player_tank.blink_timer = (
        player_tank.blink_interval * 0.5
    )  # Middle of visible phase

    # Test with sprite
    mock_sprite = MagicMock(spec=pygame.Surface)
    player_tank.sprite = mock_sprite
    player_tank.draw(mock_surface)
    # Assert call on mock_surface
    mock_surface.blit.assert_called_once_with(mock_sprite, player_tank.rect)
    mock_draw_rect.assert_not_called()

    # Test without sprite
    # Reset mock_surface for the next call check
    mock_surface.reset_mock()
    mock_draw_rect.reset_mock()
    player_tank.sprite = None
    player_tank.draw(mock_surface)
    mock_draw_rect.assert_called_once_with(mock_surface, (0, 255, 0), player_tank.rect)
    # Assert no call on mock_surface
    mock_surface.blit.assert_not_called()


@patch("pygame.draw.rect")
def test_draw_invincible_invisible_phase(mock_draw_rect, player_tank):
    """Test drawing when invincible during the invisible phase of blinking."""
    mock_surface = MagicMock(spec=pygame.Surface)
    player_tank.is_invincible = True
    player_tank.blink_timer = (
        player_tank.blink_interval * 1.5
    )  # Middle of invisible phase

    # Test with sprite
    mock_sprite = MagicMock(spec=pygame.Surface)
    player_tank.sprite = mock_sprite
    player_tank.draw(mock_surface)
    # Assert no call on mock_surface
    mock_surface.blit.assert_not_called()  # Should not draw sprite
    mock_draw_rect.assert_not_called()  # Should not draw rect

    # Test without sprite
    # Reset mocks for the next call check
    mock_surface.reset_mock()
    mock_draw_rect.reset_mock()
    player_tank.sprite = None
    player_tank.draw(mock_surface)
    # Assert no call on mock_surface
    mock_surface.blit.assert_not_called()
    mock_draw_rect.assert_not_called()


@patch("pygame.draw.rect")
def test_draw_bullet(mock_draw_rect, player_tank):
    """Test that the bullet's draw method is called."""
    mock_surface = MagicMock(spec=pygame.Surface)
    mock_bullet = MagicMock()
    mock_bullet.active = True
    player_tank.bullet = mock_bullet

    player_tank.draw(mock_surface)

    # Assert bullet draw was called (assuming tank itself is drawn)
    mock_bullet.draw.assert_called_once_with(mock_surface)

    # Assert bullet draw is not called if inactive
    # Reset relevant mocks before the next call
    mock_draw_rect.reset_mock()  # Reset the draw rect mock
    mock_surface.reset_mock()  # Reset surface mock if tank drawing happened
    mock_bullet.reset_mock()
    mock_bullet.active = False
    player_tank.draw(mock_surface)
    mock_bullet.draw.assert_not_called()
