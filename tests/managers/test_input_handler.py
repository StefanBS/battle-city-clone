import pytest
import pygame
from src.managers.input_handler import InputHandler


@pytest.fixture
def handler() -> InputHandler:
    """Fixture to provide an InputHandler instance for each test."""
    return InputHandler()


@pytest.fixture
def key_down_event():
    """Factory fixture to create KEYDOWN events."""

    def _key_down_event(key: int) -> pygame.event.Event:
        return pygame.event.Event(pygame.KEYDOWN, key=key)

    return _key_down_event


@pytest.fixture
def key_up_event():
    """Factory fixture to create KEYUP events."""

    def _key_up_event(key: int) -> pygame.event.Event:
        return pygame.event.Event(pygame.KEYUP, key=key)

    return _key_up_event


def test_initialization(handler: InputHandler) -> None:
    """Test that the handler initializes with all directions False."""
    assert not handler.directions["up"]
    assert not handler.directions["down"]
    assert not handler.directions["left"]
    assert not handler.directions["right"]
    assert handler.get_movement_direction() == (0, 0)


def test_keydown_up(handler: InputHandler, key_down_event) -> None:
    """Test handling KEYDOWN for the UP key."""
    event = key_down_event(pygame.K_UP)
    handler.handle_event(event)
    assert handler.directions["up"]
    assert not handler.directions["down"]
    assert not handler.directions["left"]
    assert not handler.directions["right"]
    assert handler.get_movement_direction() == (0, -1)


def test_keydown_down(handler: InputHandler, key_down_event) -> None:
    """Test handling KEYDOWN for the DOWN key."""
    event = key_down_event(pygame.K_DOWN)
    handler.handle_event(event)
    assert not handler.directions["up"]
    assert handler.directions["down"]
    assert not handler.directions["left"]
    assert not handler.directions["right"]
    assert handler.get_movement_direction() == (0, 1)


def test_keydown_left(handler: InputHandler, key_down_event) -> None:
    """Test handling KEYDOWN for the LEFT key."""
    event = key_down_event(pygame.K_LEFT)
    handler.handle_event(event)
    assert not handler.directions["up"]
    assert not handler.directions["down"]
    assert handler.directions["left"]
    assert not handler.directions["right"]
    assert handler.get_movement_direction() == (-1, 0)


def test_keydown_right(handler: InputHandler, key_down_event) -> None:
    """Test handling KEYDOWN for the RIGHT key."""
    event = key_down_event(pygame.K_RIGHT)
    handler.handle_event(event)
    assert not handler.directions["up"]
    assert not handler.directions["down"]
    assert not handler.directions["left"]
    assert handler.directions["right"]
    assert handler.get_movement_direction() == (1, 0)


def test_keyup(handler: InputHandler, key_down_event, key_up_event) -> None:
    """Test handling KEYUP after a KEYDOWN."""
    # Press UP
    handler.handle_event(key_down_event(pygame.K_UP))
    assert handler.directions["up"]
    assert handler.get_movement_direction() == (0, -1)

    # Release UP
    handler.handle_event(key_up_event(pygame.K_UP))
    assert not handler.directions["up"]
    assert handler.get_movement_direction() == (0, 0)


def test_multiple_keys_down(handler: InputHandler, key_down_event) -> None:
    """Test handling multiple keys pressed simultaneously."""
    handler.handle_event(key_down_event(pygame.K_UP))
    handler.handle_event(key_down_event(pygame.K_LEFT))
    assert handler.directions["up"]
    assert not handler.directions["down"]
    assert handler.directions["left"]
    assert not handler.directions["right"]
    assert handler.get_movement_direction() == (-1, -1)


def test_opposite_keys_down(handler: InputHandler, key_down_event) -> None:
    """Test handling opposite keys pressed simultaneously (should cancel out)."""
    handler.handle_event(key_down_event(pygame.K_UP))
    handler.handle_event(key_down_event(pygame.K_DOWN))
    assert handler.directions["up"]
    assert handler.directions["down"]
    assert handler.get_movement_direction() == (0, 0)  # Up and Down cancel

    handler.handle_event(key_down_event(pygame.K_LEFT))
    handler.handle_event(key_down_event(pygame.K_RIGHT))
    assert handler.directions["left"]
    assert handler.directions["right"]
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
    assert not handler.directions["up"]
    assert handler.directions["left"]
    assert handler.get_movement_direction() == (-1, 0)

    # Release LEFT
    handler.handle_event(key_up_event(pygame.K_LEFT))
    assert not handler.directions["left"]
    assert handler.get_movement_direction() == (0, 0)


def test_ignore_unmapped_keys(
    handler: InputHandler, key_down_event, key_up_event
) -> None:
    """Test that keys not in the mapping are ignored."""
    initial_directions = handler.directions.copy()
    initial_movement = handler.get_movement_direction()

    handler.handle_event(key_down_event(pygame.K_SPACE))  # Unmapped key
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
    assert handler.directions["up"]
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
    assert not handler.directions["up"]
    direction_after_first = handler.directions.copy()

    # Handle the same KEYUP event again
    handler.handle_event(key_up_event(pygame.K_UP))
    assert handler.directions == direction_after_first  # State should not change
