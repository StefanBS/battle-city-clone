import pytest
import pygame
from unittest.mock import patch, MagicMock
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


class TestJoystickInit:
    """Tests for joystick initialization."""

    def test_init_no_joystick(self, handler: InputHandler) -> None:
        """Handler initializes with no joystick when none connected."""
        assert handler.joystick is None
        assert all(not v for v in handler.joy_directions.values())

    @patch("src.managers.input_handler.pygame.joystick")
    def test_init_with_joystick(self, mock_joystick_module) -> None:
        """Handler initializes the first joystick when available."""
        mock_js = MagicMock()
        mock_js.get_name.return_value = "Test Controller"
        mock_joystick_module.get_count.return_value = 1
        mock_joystick_module.Joystick.return_value = mock_js
        handler = InputHandler()
        mock_joystick_module.Joystick.assert_called_once_with(0)
        mock_js.init.assert_called_once()
        assert handler.joystick is mock_js


class TestJoystickHotPlug:
    """Tests for joystick hot-plug support."""

    @patch("src.managers.input_handler.pygame.joystick")
    def test_device_added(self, mock_joystick_module, handler, joy_device_added_event) -> None:
        """JOYDEVICEADDED initializes the new joystick."""
        mock_js = MagicMock()
        mock_js.get_name.return_value = "Test Controller"
        mock_joystick_module.Joystick.return_value = mock_js
        handler.handle_event(joy_device_added_event(device_index=0))
        mock_joystick_module.Joystick.assert_called_once_with(0)
        mock_js.init.assert_called_once()
        assert handler.joystick is mock_js

    def test_device_added_ignored_when_already_connected(
        self, handler, joy_device_added_event
    ) -> None:
        """JOYDEVICEADDED is ignored if a joystick is already tracked."""
        mock_js = MagicMock()
        handler.joystick = mock_js
        handler.handle_event(joy_device_added_event(device_index=1))
        assert handler.joystick is mock_js  # unchanged

    def test_device_removed(self, handler, joy_device_removed_event) -> None:
        """JOYDEVICEREMOVED clears joystick and joy_directions."""
        mock_js = MagicMock()
        mock_js.get_instance_id.return_value = 0
        handler.joystick = mock_js
        handler.joy_directions[Direction.UP] = True
        handler.handle_event(joy_device_removed_event(instance_id=0))
        assert handler.joystick is None
        assert all(not v for v in handler.joy_directions.values())

    def test_device_removed_wrong_instance(self, handler, joy_device_removed_event) -> None:
        """JOYDEVICEREMOVED with wrong instance_id is ignored."""
        mock_js = MagicMock()
        mock_js.get_instance_id.return_value = 0
        handler.joystick = mock_js
        handler.handle_event(joy_device_removed_event(instance_id=99))
        assert handler.joystick is mock_js  # unchanged


class TestJoystickReset:
    """Tests for reset clearing joystick state."""

    def test_reset_clears_joy_directions(self, handler) -> None:
        """reset() clears joy_directions alongside keyboard directions."""
        handler.joy_directions[Direction.UP] = True
        assert handler.joy_directions[Direction.UP]
        handler.reset()
        assert all(not v for v in handler.joy_directions.values())
        assert not handler.shoot_pressed


class TestJoystickHat:
    """Tests for D-pad (hat) input handling."""

    def test_hat_up(self, handler, joy_hat_event) -> None:
        """Hat UP sets joy_directions UP."""
        handler.handle_event(joy_hat_event((0, 1)))
        assert handler.joy_directions[Direction.UP]
        assert not handler.joy_directions[Direction.DOWN]

    def test_hat_down(self, handler, joy_hat_event) -> None:
        """Hat DOWN sets joy_directions DOWN."""
        handler.handle_event(joy_hat_event((0, -1)))
        assert handler.joy_directions[Direction.DOWN]

    def test_hat_left(self, handler, joy_hat_event) -> None:
        """Hat LEFT sets joy_directions LEFT."""
        handler.handle_event(joy_hat_event((-1, 0)))
        assert handler.joy_directions[Direction.LEFT]

    def test_hat_right(self, handler, joy_hat_event) -> None:
        """Hat RIGHT sets joy_directions RIGHT."""
        handler.handle_event(joy_hat_event((1, 0)))
        assert handler.joy_directions[Direction.RIGHT]

    def test_hat_release(self, handler, joy_hat_event) -> None:
        """Hat (0,0) clears all joy_directions."""
        handler.handle_event(joy_hat_event((0, 1)))
        assert handler.joy_directions[Direction.UP]
        handler.handle_event(joy_hat_event((0, 0)))
        assert all(not v for v in handler.joy_directions.values())

    def test_hat_diagonal_prefers_vertical(self, handler, joy_hat_event) -> None:
        """Diagonal hat values pick vertical axis (NES behavior)."""
        handler.handle_event(joy_hat_event((1, 1)))
        assert handler.joy_directions[Direction.UP]
        assert not handler.joy_directions[Direction.RIGHT]

        handler.handle_event(joy_hat_event((-1, -1)))
        assert handler.joy_directions[Direction.DOWN]
        assert not handler.joy_directions[Direction.LEFT]

    def test_hat_merges_with_keyboard(
        self, handler, key_down_event, joy_hat_event
    ) -> None:
        """get_movement_direction merges keyboard and joystick (OR logic)."""
        handler.handle_event(key_down_event(pygame.K_UP))
        handler.handle_event(joy_hat_event((1, 0)))
        dx, dy = handler.get_movement_direction()
        # keyboard UP (-1 dy) + joystick RIGHT (+1 dx)
        assert dx == 1
        assert dy == -1

    def test_hat_direction_replaces_previous(self, handler, joy_hat_event) -> None:
        """New hat direction replaces previous (only one joy direction active)."""
        handler.handle_event(joy_hat_event((0, 1)))
        assert handler.joy_directions[Direction.UP]
        handler.handle_event(joy_hat_event((1, 0)))
        assert handler.joy_directions[Direction.RIGHT]
        assert not handler.joy_directions[Direction.UP]


class TestJoystickAxis:
    """Tests for analog stick (axis) input handling."""

    def test_axis_left(self, handler, joy_axis_event) -> None:
        """Left stick pushed left sets LEFT direction."""
        handler.handle_event(joy_axis_event(axis=0, value=-0.8))
        assert handler.joy_directions[Direction.LEFT]

    def test_axis_right(self, handler, joy_axis_event) -> None:
        """Left stick pushed right sets RIGHT direction."""
        handler.handle_event(joy_axis_event(axis=0, value=0.8))
        assert handler.joy_directions[Direction.RIGHT]

    def test_axis_up(self, handler, joy_axis_event) -> None:
        """Left stick pushed up sets UP direction."""
        handler.handle_event(joy_axis_event(axis=1, value=-0.8))
        assert handler.joy_directions[Direction.UP]

    def test_axis_down(self, handler, joy_axis_event) -> None:
        """Left stick pushed down sets DOWN direction."""
        handler.handle_event(joy_axis_event(axis=1, value=0.8))
        assert handler.joy_directions[Direction.DOWN]

    def test_axis_deadzone_no_direction(self, handler, joy_axis_event) -> None:
        """Axis value within deadzone does not set direction."""
        handler.handle_event(joy_axis_event(axis=0, value=0.3))
        assert not handler.joy_directions[Direction.RIGHT]
        assert not handler.joy_directions[Direction.LEFT]

    def test_axis_return_to_center_releases(self, handler, joy_axis_event) -> None:
        """Axis returning within deadzone releases the direction."""
        handler.handle_event(joy_axis_event(axis=0, value=-0.8))
        assert handler.joy_directions[Direction.LEFT]
        handler.handle_event(joy_axis_event(axis=0, value=0.1))
        assert not handler.joy_directions[Direction.LEFT]

    def test_axis_ignores_non_stick_axes(self, handler, joy_axis_event) -> None:
        """Axes beyond 0 and 1 (triggers, right stick) are ignored."""
        handler.handle_event(joy_axis_event(axis=2, value=1.0))
        assert all(not v for v in handler.joy_directions.values())
