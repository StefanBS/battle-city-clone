import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.managers.input_handler import InputHandler
from src.managers.player_input import InputSource, PlayerInput
from src.utils.constants import MenuAction


@pytest.fixture
def handler() -> InputHandler:
    """Fixture providing an InputHandler with no controllers present."""
    with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
        mock_sdl.init.return_value = None
        mock_sdl.is_controller.return_value = False
        with patch("src.managers.input_handler.pygame.joystick") as mock_js:
            mock_js.get_count.return_value = 0
            return InputHandler()


def _mock_controller(instance_id: int, name: str = "Test Controller") -> MagicMock:
    """Build a MagicMock matching the sdl_controller.Controller surface."""
    ctrl = MagicMock()
    ctrl.name = name
    ctrl.as_joystick.return_value.get_instance_id.return_value = instance_id
    return ctrl


def test_initialization(handler: InputHandler) -> None:
    """The handler initializes with empty menu actions."""
    assert handler.consume_menu_actions() == []
    assert handler.controller_instance_ids == []


def test_ignore_unmapped_keys(handler: InputHandler, key_down_event) -> None:
    """Unmapped keys produce no menu actions."""
    handler.handle_event(key_down_event(pygame.K_a))
    assert handler.consume_menu_actions() == []


def test_ignore_other_event_types(handler: InputHandler) -> None:
    """Non-KEYDOWN/CONTROLLER* events are ignored."""
    mouse_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
    handler.handle_event(mouse_event)
    assert handler.consume_menu_actions() == []


class TestControllerInit:
    """Tests for controller initialization on InputHandler construction."""

    def test_init_no_controller(self, handler: InputHandler) -> None:
        """Handler initializes with no controllers when none are connected."""
        assert handler.controller_instance_ids == []

    def test_init_opens_present_controllers(self) -> None:
        """Handler opens every connected SDL GameController at startup."""
        ctrl0 = _mock_controller(instance_id=0, name="Xbox One Controller")
        ctrl1 = _mock_controller(instance_id=5, name="Xbox Series X Controller")
        with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
            mock_sdl.is_controller.return_value = True
            mock_sdl.Controller.side_effect = [ctrl0, ctrl1]
            with patch("src.managers.input_handler.pygame.joystick") as mock_js:
                mock_js.get_count.return_value = 2
                h = InputHandler()
                assert sorted(h.controller_instance_ids) == [0, 5]
                ctrl0.init.assert_called_once()
                ctrl1.init.assert_called_once()

    def test_init_skips_non_controller_devices(self) -> None:
        """Joysticks that SDL doesn't recognize as game controllers are skipped."""
        with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
            mock_sdl.is_controller.return_value = False
            with patch("src.managers.input_handler.pygame.joystick") as mock_js:
                mock_js.get_count.return_value = 1
                h = InputHandler()
                assert h.controller_instance_ids == []
                mock_sdl.Controller.assert_not_called()


class TestControllerHotPlug:
    """Tests for controller hot-plug support."""

    def test_device_added_registers_controller(
        self, handler: InputHandler, ctrl_device_added_event
    ) -> None:
        """CONTROLLERDEVICEADDED opens and registers the new controller."""
        new_ctrl = _mock_controller(instance_id=7)
        with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
            mock_sdl.is_controller.return_value = True
            mock_sdl.Controller.return_value = new_ctrl
            handler.handle_event(ctrl_device_added_event(device_index=0))
            assert handler.controller_instance_ids == [7]

    def test_multiple_adds_tracked_independently(
        self, handler: InputHandler, ctrl_device_added_event
    ) -> None:
        """Adding two controllers registers both by their instance_ids."""
        with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
            mock_sdl.is_controller.return_value = True
            mock_sdl.Controller.side_effect = [
                _mock_controller(instance_id=3),
                _mock_controller(instance_id=9),
            ]
            handler.handle_event(ctrl_device_added_event(device_index=0))
            handler.handle_event(ctrl_device_added_event(device_index=1))
            assert sorted(handler.controller_instance_ids) == [3, 9]

    def test_device_removed_drops_correct_controller(
        self,
        handler: InputHandler,
        ctrl_device_added_event,
        ctrl_device_removed_event,
    ) -> None:
        """CONTROLLERDEVICEREMOVED drops the controller matching instance_id."""
        with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
            mock_sdl.is_controller.return_value = True
            mock_sdl.Controller.side_effect = [
                _mock_controller(instance_id=3),
                _mock_controller(instance_id=9),
            ]
            handler.handle_event(ctrl_device_added_event(device_index=0))
            handler.handle_event(ctrl_device_added_event(device_index=1))
        handler.handle_event(ctrl_device_removed_event(instance_id=3))
        assert handler.controller_instance_ids == [9]

    def test_device_removed_unknown_instance_noop(
        self, handler: InputHandler, ctrl_device_removed_event
    ) -> None:
        """Removing an instance_id the handler doesn't track is a no-op."""
        handler.handle_event(ctrl_device_removed_event(instance_id=999))
        assert handler.controller_instance_ids == []

    def test_device_added_twice_does_not_leak(
        self, handler: InputHandler, ctrl_device_added_event
    ) -> None:
        """Two DEVICEADDED events for the same instance_id don't leak a handle."""
        first = _mock_controller(instance_id=7)
        duplicate = _mock_controller(instance_id=7)
        with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
            mock_sdl.is_controller.return_value = True
            mock_sdl.Controller.side_effect = [first, duplicate]
            handler.handle_event(ctrl_device_added_event(device_index=0))
            handler.handle_event(ctrl_device_added_event(device_index=0))
        # Registry still has one entry, pointing at the first opened handle.
        assert handler.controller_instance_ids == [7]
        # The duplicate was quit()'d so the SDL handle doesn't leak.
        duplicate.quit.assert_called_once()
        first.quit.assert_not_called()

    def test_device_removed_quits_handle(
        self,
        handler: InputHandler,
        ctrl_device_added_event,
        ctrl_device_removed_event,
    ) -> None:
        """CONTROLLERDEVICEREMOVED calls .quit() on the SDL handle."""
        ctrl = _mock_controller(instance_id=7)
        with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
            mock_sdl.is_controller.return_value = True
            mock_sdl.Controller.return_value = ctrl
            handler.handle_event(ctrl_device_added_event(device_index=0))
        handler.handle_event(ctrl_device_removed_event(instance_id=7))
        ctrl.quit.assert_called_once()

    def test_hot_plugged_controller_routes_to_player_input(
        self,
        handler: InputHandler,
        ctrl_device_added_event,
        ctrl_button_down_event,
    ) -> None:
        """End-to-end: DEVICEADDED registers a controller; a BUTTONDOWN event
        with the same instance_id drives a PlayerInput bound to it.

        This covers the full hot-plug path: InputHandler registration +
        PlayerInput routing agreeing on the same instance_id.
        """
        with patch("src.managers.input_handler.sdl_controller") as mock_sdl:
            mock_sdl.is_controller.return_value = True
            mock_sdl.Controller.return_value = _mock_controller(instance_id=42)
            handler.handle_event(ctrl_device_added_event(device_index=0))
        assert handler.controller_instance_ids == [42]

        pi = PlayerInput(InputSource.CONTROLLER, instance_id=42, exclusive=True)
        pi.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_A, instance_id=42)
        )
        assert pi.consume_shoot() is True


class TestControllerButtonUp:
    """Tests for CONTROLLERBUTTONUP handling (direction release)."""

    def test_dpad_up_release_clears_direction(self) -> None:
        """Releasing a held D-pad direction clears it in PlayerInput."""
        pi = PlayerInput(InputSource.CONTROLLER, instance_id=0)
        pi.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=0,
            )
        )
        assert pi.get_movement_direction() == (0, -1)
        pi.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONUP,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=0,
            )
        )
        assert pi.get_movement_direction() == (0, 0)


class TestMenuActionsKeyboard:
    """Tests for keyboard menu action production."""

    def test_key_up_produces_menu_up(self, handler, key_down_event) -> None:
        handler.handle_event(key_down_event(pygame.K_UP))
        assert handler.consume_menu_actions() == [MenuAction.UP]

    def test_key_down_produces_menu_down(self, handler, key_down_event) -> None:
        handler.handle_event(key_down_event(pygame.K_DOWN))
        assert handler.consume_menu_actions() == [MenuAction.DOWN]

    def test_key_left_produces_menu_left(self, handler, key_down_event) -> None:
        handler.handle_event(key_down_event(pygame.K_LEFT))
        assert handler.consume_menu_actions() == [MenuAction.LEFT]

    def test_key_right_produces_menu_right(self, handler, key_down_event) -> None:
        handler.handle_event(key_down_event(pygame.K_RIGHT))
        assert handler.consume_menu_actions() == [MenuAction.RIGHT]

    def test_key_return_produces_confirm(self, handler, key_down_event) -> None:
        handler.handle_event(key_down_event(pygame.K_RETURN))
        assert handler.consume_menu_actions() == [MenuAction.CONFIRM]

    def test_key_r_produces_confirm(self, handler, key_down_event) -> None:
        handler.handle_event(key_down_event(pygame.K_r))
        assert handler.consume_menu_actions() == [MenuAction.CONFIRM]

    def test_consume_clears_list(self, handler, key_down_event) -> None:
        handler.handle_event(key_down_event(pygame.K_UP))
        handler.consume_menu_actions()
        assert handler.consume_menu_actions() == []

    def test_multiple_actions_preserved(self, handler, key_down_event) -> None:
        handler.handle_event(key_down_event(pygame.K_DOWN))
        handler.handle_event(key_down_event(pygame.K_RETURN))
        assert handler.consume_menu_actions() == [
            MenuAction.DOWN,
            MenuAction.CONFIRM,
        ]

    def test_key_repeat_produces_multiple(self, handler, key_down_event) -> None:
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
        handler.handle_event(key_down_event(pygame.K_UP))
        handler.reset()
        assert handler.consume_menu_actions() == []


class TestMenuActionsController:
    """Tests for controller menu action production."""

    def test_dpad_up_produces_menu_up(self, handler, ctrl_button_down_event) -> None:
        handler.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_UP))
        assert MenuAction.UP in handler.consume_menu_actions()

    def test_dpad_down_produces_menu_down(
        self, handler, ctrl_button_down_event
    ) -> None:
        handler.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_DOWN)
        )
        assert MenuAction.DOWN in handler.consume_menu_actions()

    def test_dpad_left_produces_menu_left(
        self, handler, ctrl_button_down_event
    ) -> None:
        handler.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_LEFT)
        )
        assert MenuAction.LEFT in handler.consume_menu_actions()

    def test_dpad_right_produces_menu_right(
        self, handler, ctrl_button_down_event
    ) -> None:
        handler.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
        )
        assert MenuAction.RIGHT in handler.consume_menu_actions()

    def test_a_button_produces_confirm(
        self, handler, ctrl_button_down_event
    ) -> None:
        handler.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_A))
        assert MenuAction.CONFIRM in handler.consume_menu_actions()

    def test_b_button_produces_back(self, handler, ctrl_button_down_event) -> None:
        handler.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_B))
        assert MenuAction.BACK in handler.consume_menu_actions()


class TestMenuActionsAxisEdgeDetection:
    """Tests for analog stick menu action edge detection."""

    def test_axis_crossing_deadzone_produces_action(
        self, handler, ctrl_axis_event
    ) -> None:
        handler.handle_event(
            ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.8)
        )
        assert MenuAction.LEFT in handler.consume_menu_actions()

    def test_axis_held_does_not_repeat(self, handler, ctrl_axis_event) -> None:
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.8))
        handler.consume_menu_actions()
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.9))
        assert handler.consume_menu_actions() == []

    def test_axis_return_to_center_no_action(self, handler, ctrl_axis_event) -> None:
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.8))
        handler.consume_menu_actions()
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, 0.1))
        assert handler.consume_menu_actions() == []

    def test_axis_direction_change_produces_new_action(
        self, handler, ctrl_axis_event
    ) -> None:
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.8))
        handler.consume_menu_actions()
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, 0.9))
        assert MenuAction.RIGHT in handler.consume_menu_actions()

    def test_axis_within_deadzone_no_action(self, handler, ctrl_axis_event) -> None:
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        assert handler.consume_menu_actions() == []

    def test_vertical_axis_edge_detection(self, handler, ctrl_axis_event) -> None:
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTY, 0.8))
        assert MenuAction.DOWN in handler.consume_menu_actions()
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTY, 0.9))
        assert handler.consume_menu_actions() == []

    def test_reset_clears_axis_menu_state(self, handler, ctrl_axis_event) -> None:
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.8))
        handler.consume_menu_actions()
        handler.reset()
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.8))
        assert MenuAction.LEFT in handler.consume_menu_actions()
