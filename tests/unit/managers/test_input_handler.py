import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.managers.input_handler import InputHandler
from src.utils.constants import MenuAction


@pytest.fixture
def handler() -> InputHandler:
    """Fixture to provide an InputHandler instance for each test."""
    return InputHandler()


def test_initialization(handler: InputHandler) -> None:
    """Test that the handler initializes with empty menu actions."""
    assert handler.consume_menu_actions() == []


def test_ignore_unmapped_keys(handler: InputHandler, key_down_event) -> None:
    """Test that unmapped keys produce no menu actions."""
    handler.handle_event(key_down_event(pygame.K_a))
    assert handler.consume_menu_actions() == []


def test_ignore_other_event_types(handler: InputHandler) -> None:
    """Test that non-KEYDOWN/KEYUP events are ignored."""
    mouse_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
    handler.handle_event(mouse_event)
    assert handler.consume_menu_actions() == []


class TestJoystickInit:
    """Tests for joystick initialization."""

    def test_init_no_joystick(self, handler: InputHandler) -> None:
        """Handler initializes with no joystick when none connected."""
        assert handler.joystick is None

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
    def test_device_added(
        self, mock_joystick_module, handler, joy_device_added_event
    ) -> None:
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
        """JOYDEVICEREMOVED clears joystick."""
        mock_js = MagicMock()
        mock_js.get_instance_id.return_value = 0
        handler.joystick = mock_js
        handler.handle_event(joy_device_removed_event(instance_id=0))
        assert handler.joystick is None

    def test_device_removed_wrong_instance(
        self, handler, joy_device_removed_event
    ) -> None:
        """JOYDEVICEREMOVED with wrong instance_id is ignored."""
        mock_js = MagicMock()
        mock_js.get_instance_id.return_value = 0
        handler.joystick = mock_js
        handler.handle_event(joy_device_removed_event(instance_id=99))
        assert handler.joystick is mock_js  # unchanged


class TestMenuActions:
    """Tests for keyboard menu action production."""

    def test_key_up_produces_menu_up(self, handler, key_down_event) -> None:
        """K_UP produces MenuAction.UP."""
        handler.handle_event(key_down_event(pygame.K_UP))
        assert handler.consume_menu_actions() == [MenuAction.UP]

    def test_key_down_produces_menu_down(self, handler, key_down_event) -> None:
        """K_DOWN produces MenuAction.DOWN."""
        handler.handle_event(key_down_event(pygame.K_DOWN))
        assert handler.consume_menu_actions() == [MenuAction.DOWN]

    def test_key_left_produces_menu_left(self, handler, key_down_event) -> None:
        """K_LEFT produces MenuAction.LEFT."""
        handler.handle_event(key_down_event(pygame.K_LEFT))
        assert handler.consume_menu_actions() == [MenuAction.LEFT]

    def test_key_right_produces_menu_right(self, handler, key_down_event) -> None:
        """K_RIGHT produces MenuAction.RIGHT."""
        handler.handle_event(key_down_event(pygame.K_RIGHT))
        assert handler.consume_menu_actions() == [MenuAction.RIGHT]

    def test_key_return_produces_confirm(self, handler, key_down_event) -> None:
        """K_RETURN produces MenuAction.CONFIRM."""
        handler.handle_event(key_down_event(pygame.K_RETURN))
        assert handler.consume_menu_actions() == [MenuAction.CONFIRM]

    def test_key_r_produces_confirm(self, handler, key_down_event) -> None:
        """K_r produces MenuAction.CONFIRM."""
        handler.handle_event(key_down_event(pygame.K_r))
        assert handler.consume_menu_actions() == [MenuAction.CONFIRM]

    def test_consume_clears_list(self, handler, key_down_event) -> None:
        """Second call to consume_menu_actions returns empty list."""
        handler.handle_event(key_down_event(pygame.K_UP))
        handler.consume_menu_actions()
        assert handler.consume_menu_actions() == []

    def test_multiple_actions_preserved(self, handler, key_down_event) -> None:
        """Multiple actions accumulated before consume are returned in order."""
        handler.handle_event(key_down_event(pygame.K_DOWN))
        handler.handle_event(key_down_event(pygame.K_RETURN))
        assert handler.consume_menu_actions() == [
            MenuAction.DOWN,
            MenuAction.CONFIRM,
        ]

    def test_key_repeat_produces_multiple(self, handler, key_down_event) -> None:
        """Each KEYDOWN event (including repeats) produces a MenuAction."""
        event = key_down_event(pygame.K_UP)
        handler.handle_event(event)
        handler.handle_event(event)
        handler.handle_event(event)
        assert handler.consume_menu_actions() == [
            MenuAction.UP,
            MenuAction.UP,
            MenuAction.UP,
        ]

    def test_reset_clears_menu_actions(self, handler, key_down_event) -> None:
        """reset() clears pending menu actions."""
        handler.handle_event(key_down_event(pygame.K_UP))
        handler.reset()
        assert handler.consume_menu_actions() == []


class TestMenuActionsController:
    """Tests for controller menu action production."""

    def test_dpad_up_produces_menu_up(self, handler, ctrl_button_down_event) -> None:
        """Controller D-pad UP produces MenuAction.UP."""
        handler.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_UP))
        assert MenuAction.UP in handler.consume_menu_actions()

    def test_dpad_down_produces_menu_down(
        self, handler, ctrl_button_down_event
    ) -> None:
        """Controller D-pad DOWN produces MenuAction.DOWN."""
        handler.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_DOWN))
        assert MenuAction.DOWN in handler.consume_menu_actions()

    def test_dpad_left_produces_menu_left(
        self, handler, ctrl_button_down_event
    ) -> None:
        """Controller D-pad LEFT produces MenuAction.LEFT."""
        handler.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_LEFT))
        assert MenuAction.LEFT in handler.consume_menu_actions()

    def test_dpad_right_produces_menu_right(
        self, handler, ctrl_button_down_event
    ) -> None:
        """Controller D-pad RIGHT produces MenuAction.RIGHT."""
        handler.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
        )
        assert MenuAction.RIGHT in handler.consume_menu_actions()

    def test_a_button_produces_confirm(self, handler, ctrl_button_down_event) -> None:
        """Controller A button produces MenuAction.CONFIRM."""
        handler.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_A))
        assert MenuAction.CONFIRM in handler.consume_menu_actions()

    def test_b_button_produces_back(self, handler, ctrl_button_down_event) -> None:
        """Controller B button produces MenuAction.BACK (Xbox convention)."""
        handler.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_B))
        assert MenuAction.BACK in handler.consume_menu_actions()

    def test_joy_hat_up_produces_menu_up(self, handler, joy_hat_event) -> None:
        """Raw joystick hat UP produces MenuAction.UP."""
        handler.handle_event(joy_hat_event((0, 1)))
        assert MenuAction.UP in handler.consume_menu_actions()

    def test_joy_hat_down_produces_menu_down(self, handler, joy_hat_event) -> None:
        """Raw joystick hat DOWN produces MenuAction.DOWN."""
        handler.handle_event(joy_hat_event((0, -1)))
        assert MenuAction.DOWN in handler.consume_menu_actions()

    def test_joy_hat_left_produces_menu_left(self, handler, joy_hat_event) -> None:
        """Raw joystick hat LEFT produces MenuAction.LEFT."""
        handler.handle_event(joy_hat_event((-1, 0)))
        assert MenuAction.LEFT in handler.consume_menu_actions()

    def test_joy_hat_right_produces_menu_right(self, handler, joy_hat_event) -> None:
        """Raw joystick hat RIGHT produces MenuAction.RIGHT."""
        handler.handle_event(joy_hat_event((1, 0)))
        assert MenuAction.RIGHT in handler.consume_menu_actions()

    def test_joy_button_0_produces_confirm(
        self, handler, joy_button_down_event
    ) -> None:
        """Raw joystick button 0 produces MenuAction.CONFIRM."""
        handler.handle_event(joy_button_down_event(button=0))
        assert MenuAction.CONFIRM in handler.consume_menu_actions()

    def test_joy_button_1_produces_back(
        self, handler, joy_button_down_event
    ) -> None:
        """Raw joystick button 1 produces MenuAction.BACK (Xbox convention)."""
        handler.handle_event(joy_button_down_event(button=1))
        assert MenuAction.BACK in handler.consume_menu_actions()


class TestMenuActionsAxisEdgeDetection:
    """Tests for analog stick menu action edge detection."""

    def test_axis_crossing_deadzone_produces_action(
        self, handler, joy_axis_event
    ) -> None:
        """Axis crossing the deadzone threshold produces a MenuAction."""
        handler.handle_event(joy_axis_event(axis=0, value=-0.8))
        assert MenuAction.LEFT in handler.consume_menu_actions()

    def test_axis_held_does_not_repeat(self, handler, joy_axis_event) -> None:
        """Axis held beyond deadzone does not emit repeated MenuActions."""
        handler.handle_event(joy_axis_event(axis=0, value=-0.8))
        handler.consume_menu_actions()  # clear initial action
        handler.handle_event(joy_axis_event(axis=0, value=-0.9))  # still beyond DZ
        assert handler.consume_menu_actions() == []

    def test_axis_return_to_center_no_action(self, handler, joy_axis_event) -> None:
        """Axis returning within deadzone resets state and emits no action."""
        handler.handle_event(joy_axis_event(axis=0, value=-0.8))
        handler.consume_menu_actions()
        handler.handle_event(joy_axis_event(axis=0, value=0.1))
        assert handler.consume_menu_actions() == []

    def test_axis_direction_change_produces_new_action(
        self, handler, joy_axis_event
    ) -> None:
        """Axis flipping direction without returning to center still emits."""
        handler.handle_event(joy_axis_event(axis=0, value=-0.8))
        handler.consume_menu_actions()
        handler.handle_event(joy_axis_event(axis=0, value=0.9))
        assert MenuAction.RIGHT in handler.consume_menu_actions()

    def test_ctrl_axis_uses_edge_detection(self, handler, ctrl_axis_event) -> None:
        """SDL GameController axis also uses edge detection."""
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.8))
        assert MenuAction.LEFT in handler.consume_menu_actions()
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.9))
        assert handler.consume_menu_actions() == []

    def test_axis_within_deadzone_no_action(self, handler, joy_axis_event) -> None:
        """Axis value within deadzone produces no action."""
        handler.handle_event(joy_axis_event(axis=0, value=0.3))
        assert handler.consume_menu_actions() == []

    def test_vertical_axis_edge_detection(self, handler, joy_axis_event) -> None:
        """Vertical axis also uses edge detection."""
        handler.handle_event(joy_axis_event(axis=1, value=0.8))
        assert MenuAction.DOWN in handler.consume_menu_actions()
        handler.handle_event(joy_axis_event(axis=1, value=0.9))
        assert handler.consume_menu_actions() == []

    def test_reset_clears_axis_menu_state(self, handler, joy_axis_event) -> None:
        """reset() clears axis edge-detection state so re-press emits action."""
        handler.handle_event(joy_axis_event(axis=0, value=-0.8))
        handler.consume_menu_actions()
        handler.reset()
        # After reset, the same axis value should produce a new action
        handler.handle_event(joy_axis_event(axis=0, value=-0.8))
        assert MenuAction.LEFT in handler.consume_menu_actions()
