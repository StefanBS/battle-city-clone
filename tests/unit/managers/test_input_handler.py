import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.managers.input_handler import InputHandler
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


def _key(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _button(button: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=button, instance_id=0)


@pytest.mark.parametrize(
    ("event", "action"),
    [
        (_key(pygame.K_UP), MenuAction.UP),
        (_key(pygame.K_DOWN), MenuAction.DOWN),
        (_key(pygame.K_LEFT), MenuAction.LEFT),
        (_key(pygame.K_RIGHT), MenuAction.RIGHT),
        (_key(pygame.K_RETURN), MenuAction.CONFIRM),
        (_key(pygame.K_r), MenuAction.CONFIRM),
        (_button(pygame.CONTROLLER_BUTTON_DPAD_UP), MenuAction.UP),
        (_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN), MenuAction.DOWN),
        (_button(pygame.CONTROLLER_BUTTON_DPAD_LEFT), MenuAction.LEFT),
        (_button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT), MenuAction.RIGHT),
        (_button(pygame.CONTROLLER_BUTTON_A), MenuAction.CONFIRM),
        (_button(pygame.CONTROLLER_BUTTON_B), MenuAction.BACK),
    ],
)
def test_key_or_button_produces_menu_action(
    handler: InputHandler, event: pygame.event.Event, action: MenuAction
) -> None:
    handler.handle_event(event)
    assert handler.consume_menu_actions() == [action]


class TestMenuActionsKeyboard:
    """Tests for keyboard menu action production."""

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


class TestMenuActionsAxisEdgeDetection:
    """Tests for analog stick menu action edge detection."""

    def test_axis_crossing_deadzone_produces_action(
        self, handler, ctrl_axis_event
    ) -> None:
        handler.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, -0.8))
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
