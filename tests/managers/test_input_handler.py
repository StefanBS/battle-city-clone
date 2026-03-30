import pytest
import pygame
from src.managers.input_handler import InputHandler
from src.utils.constants import Direction


@pytest.fixture
def handler() -> InputHandler:
    """Fixture to provide an InputHandler instance for each test."""
    return InputHandler()


def test_initialization(handler: InputHandler) -> None:
    """Test that the handler initializes with all directions False."""
    assert not handler.directions[Direction.UP]
    assert not handler.directions[Direction.DOWN]
    assert not handler.directions[Direction.LEFT]
    assert not handler.directions[Direction.RIGHT]
    assert handler.get_movement_direction() == (0, 0)


def test_keydown_up(handler: InputHandler, key_down_event) -> None:
    """Test handling KEYDOWN for the UP key."""
    event = key_down_event(pygame.K_UP)
    handler.handle_event(event)
    assert handler.directions[Direction.UP]
    assert not handler.directions[Direction.DOWN]
    assert not handler.directions[Direction.LEFT]
    assert not handler.directions[Direction.RIGHT]
    assert handler.get_movement_direction() == (0, -1)


def test_keydown_down(handler: InputHandler, key_down_event) -> None:
    """Test handling KEYDOWN for the DOWN key."""
    event = key_down_event(pygame.K_DOWN)
    handler.handle_event(event)
    assert not handler.directions[Direction.UP]
    assert handler.directions[Direction.DOWN]
    assert not handler.directions[Direction.LEFT]
    assert not handler.directions[Direction.RIGHT]
    assert handler.get_movement_direction() == (0, 1)


def test_keydown_left(handler: InputHandler, key_down_event) -> None:
    """Test handling KEYDOWN for the LEFT key."""
    event = key_down_event(pygame.K_LEFT)
    handler.handle_event(event)
    assert not handler.directions[Direction.UP]
    assert not handler.directions[Direction.DOWN]
    assert handler.directions[Direction.LEFT]
    assert not handler.directions[Direction.RIGHT]
    assert handler.get_movement_direction() == (-1, 0)


def test_keydown_right(handler: InputHandler, key_down_event) -> None:
    """Test handling KEYDOWN for the RIGHT key."""
    event = key_down_event(pygame.K_RIGHT)
    handler.handle_event(event)
    assert not handler.directions[Direction.UP]
    assert not handler.directions[Direction.DOWN]
    assert not handler.directions[Direction.LEFT]
    assert handler.directions[Direction.RIGHT]
    assert handler.get_movement_direction() == (1, 0)


def test_keyup(handler: InputHandler, key_down_event, key_up_event) -> None:
    """Test handling KEYUP after a KEYDOWN."""
    # Press UP
    handler.handle_event(key_down_event(pygame.K_UP))
    assert handler.directions[Direction.UP]
    assert handler.get_movement_direction() == (0, -1)

    # Release UP
    handler.handle_event(key_up_event(pygame.K_UP))
    assert not handler.directions[Direction.UP]
    assert handler.get_movement_direction() == (0, 0)


def test_multiple_keys_down(handler: InputHandler, key_down_event) -> None:
    """Test handling multiple keys pressed simultaneously."""
    handler.handle_event(key_down_event(pygame.K_UP))
    handler.handle_event(key_down_event(pygame.K_LEFT))
    assert handler.directions[Direction.UP]
    assert not handler.directions[Direction.DOWN]
    assert handler.directions[Direction.LEFT]
    assert not handler.directions[Direction.RIGHT]
    assert handler.get_movement_direction() == (-1, -1)


def test_opposite_keys_down(handler: InputHandler, key_down_event) -> None:
    """Test handling opposite keys pressed simultaneously (should cancel out)."""
    handler.handle_event(key_down_event(pygame.K_UP))
    handler.handle_event(key_down_event(pygame.K_DOWN))
    assert handler.directions[Direction.UP]
    assert handler.directions[Direction.DOWN]
    assert handler.get_movement_direction() == (0, 0)  # Up and Down cancel

    handler.handle_event(key_down_event(pygame.K_LEFT))
    handler.handle_event(key_down_event(pygame.K_RIGHT))
    assert handler.directions[Direction.LEFT]
    assert handler.directions[Direction.RIGHT]
    assert handler.get_movement_direction() == (0, 0)  # Left and Right also cancel


def test_key_hold_and_release(
    handler: InputHandler, key_down_event, key_up_event
) -> None:
    """Test pressing, holding, and releasing keys."""
    # Press UP and LEFT
    handler.handle_event(key_down_event(pygame.K_UP))
    handler.handle_event(key_down_event(pygame.K_LEFT))
    assert handler.get_movement_direction() == (-1, -1)

    # Release UP
    handler.handle_event(key_up_event(pygame.K_UP))
    assert not handler.directions[Direction.UP]
    assert handler.directions[Direction.LEFT]
    assert handler.get_movement_direction() == (-1, 0)

    # Release LEFT
    handler.handle_event(key_up_event(pygame.K_LEFT))
    assert not handler.directions[Direction.LEFT]
    assert handler.get_movement_direction() == (0, 0)


def test_ignore_unmapped_keys(
    handler: InputHandler, key_down_event, key_up_event
) -> None:
    """Test that keys not in the mapping are ignored."""
    initial_directions = handler.directions.copy()
    initial_movement = handler.get_movement_direction()

    handler.handle_event(key_down_event(pygame.K_a))  # Unmapped key
    handler.handle_event(key_up_event(pygame.K_a))  # Unmapped key

    assert handler.directions == initial_directions
    assert handler.get_movement_direction() == initial_movement


def test_ignore_other_event_types(handler: InputHandler) -> None:
    """Test that non-KEYDOWN/KEYUP events are ignored."""
    initial_directions = handler.directions.copy()
    initial_movement = handler.get_movement_direction()

    # Simulate a MOUSEBUTTONDOWN event
    mouse_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
    handler.handle_event(mouse_event)

    assert handler.directions == initial_directions
    assert handler.get_movement_direction() == initial_movement


def test_repeated_keydown(handler: InputHandler, key_down_event) -> None:
    """Test that repeated KEYDOWN events for the same key don't change state
    after the first."""
    event = key_down_event(pygame.K_UP)
    handler.handle_event(event)
    assert handler.directions[Direction.UP]
    direction_after_first = handler.directions.copy()

    # Handle the same KEYDOWN event again
    handler.handle_event(event)
    assert handler.directions == direction_after_first  # State should not change


def test_repeated_keyup(handler: InputHandler, key_down_event, key_up_event) -> None:
    """Test that repeated KEYUP events for the same key don't change state
    after the first."""
    # Press and release UP
    handler.handle_event(key_down_event(pygame.K_UP))
    handler.handle_event(key_up_event(pygame.K_UP))
    assert not handler.directions[Direction.UP]
    direction_after_first = handler.directions.copy()

    # Handle the same KEYUP event again
    handler.handle_event(key_up_event(pygame.K_UP))
    assert handler.directions == direction_after_first  # State should not change


def test_shoot_key_default(handler: InputHandler, key_down_event) -> None:
    """Test that space bar triggers shoot_pressed."""
    assert not handler.shoot_pressed
    handler.handle_event(key_down_event(pygame.K_SPACE))
    assert handler.shoot_pressed


def test_consume_shoot(handler: InputHandler, key_down_event) -> None:
    """Test that consume_shoot returns True once then resets."""
    handler.handle_event(key_down_event(pygame.K_SPACE))
    assert handler.consume_shoot() is True
    assert handler.consume_shoot() is False
    assert not handler.shoot_pressed


def test_shoot_key_not_triggered_by_movement(
    handler: InputHandler, key_down_event
) -> None:
    """Test that movement keys don't trigger shoot."""
    handler.handle_event(key_down_event(pygame.K_UP))
    assert not handler.shoot_pressed
