import pytest
import pygame
from src.managers.player_input import InputSource, PlayerInput


@pytest.fixture
def keyboard_input() -> PlayerInput:
    """Fixture providing a keyboard-sourced PlayerInput."""
    return PlayerInput(InputSource.KEYBOARD)


@pytest.fixture
def joystick_input() -> PlayerInput:
    """Fixture providing a joystick-sourced PlayerInput (index 0)."""
    return PlayerInput(InputSource.JOYSTICK, joystick_index=0)


@pytest.fixture
def joystick_input_1() -> PlayerInput:
    """Fixture providing a joystick-sourced PlayerInput (index 1)."""
    return PlayerInput(InputSource.JOYSTICK, joystick_index=1)


class TestKeyboardPlayerInput:
    def test_initial_direction_is_zero(self, keyboard_input: PlayerInput) -> None:
        """Initial movement direction is (0, 0)."""
        assert keyboard_input.get_movement_direction() == (0, 0)

    def test_initial_shoot_is_false(self, keyboard_input: PlayerInput) -> None:
        """Initial shoot flag is False."""
        assert keyboard_input.consume_shoot() is False

    def test_arrow_up_sets_direction(self, keyboard_input: PlayerInput) -> None:
        """K_UP sets direction to (0, -1)."""
        keyboard_input.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        assert keyboard_input.get_movement_direction() == (0, -1)

    def test_arrow_down_sets_direction(self, keyboard_input: PlayerInput) -> None:
        """K_DOWN sets direction to (0, 1)."""
        keyboard_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        )
        assert keyboard_input.get_movement_direction() == (0, 1)

    def test_arrow_left_sets_direction(self, keyboard_input: PlayerInput) -> None:
        """K_LEFT sets direction to (-1, 0)."""
        keyboard_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT)
        )
        assert keyboard_input.get_movement_direction() == (-1, 0)

    def test_arrow_right_sets_direction(self, keyboard_input: PlayerInput) -> None:
        """K_RIGHT sets direction to (1, 0)."""
        keyboard_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
        )
        assert keyboard_input.get_movement_direction() == (1, 0)

    def test_arrow_release_clears_direction(self, keyboard_input: PlayerInput) -> None:
        """KEYUP for arrow key clears the direction."""
        keyboard_input.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        assert keyboard_input.get_movement_direction() == (0, -1)
        keyboard_input.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_UP))
        assert keyboard_input.get_movement_direction() == (0, 0)

    def test_space_sets_shoot(self, keyboard_input: PlayerInput) -> None:
        """SPACE KEYDOWN sets shoot flag."""
        keyboard_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        )
        assert keyboard_input.consume_shoot() is True

    def test_consume_shoot_clears_flag(self, keyboard_input: PlayerInput) -> None:
        """consume_shoot returns True once then False."""
        keyboard_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        )
        assert keyboard_input.consume_shoot() is True
        assert keyboard_input.consume_shoot() is False

    def test_ignores_non_gameplay_keys(self, keyboard_input: PlayerInput) -> None:
        """Non-gameplay keys (e.g. ESCAPE) are ignored."""
        keyboard_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        )
        assert keyboard_input.get_movement_direction() == (0, 0)
        assert keyboard_input.consume_shoot() is False

    def test_also_handles_joystick_events(self, keyboard_input: PlayerInput) -> None:
        """Keyboard source also handles joystick events for single-player use."""
        keyboard_input.handle_event(
            pygame.event.Event(pygame.JOYHATMOTION, value=(0, 1), hat=0, instance_id=0)
        )
        assert keyboard_input.get_movement_direction() == (0, -1)

        keyboard_input.handle_event(
            pygame.event.Event(pygame.JOYBUTTONDOWN, button=0, instance_id=0)
        )
        assert keyboard_input.consume_shoot() is True


class TestJoystickPlayerInput:
    def test_initial_direction_is_zero(self, joystick_input: PlayerInput) -> None:
        """Initial movement direction is (0, 0)."""
        assert joystick_input.get_movement_direction() == (0, 0)

    def test_controller_dpad_sets_direction(self, joystick_input: PlayerInput) -> None:
        """CONTROLLERBUTTONDOWN for DPAD_UP sets direction to (0, -1)."""
        joystick_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                which=0,
            )
        )
        assert joystick_input.get_movement_direction() == (0, -1)

    def test_controller_shoot_button(self, joystick_input: PlayerInput) -> None:
        """CONTROLLERBUTTONDOWN for A button sets shoot flag."""
        joystick_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_A,
                which=0,
            )
        )
        assert joystick_input.consume_shoot() is True

    def test_ignores_events_from_other_joystick(
        self,
        joystick_input: PlayerInput,
        joystick_input_1: PlayerInput,
    ) -> None:
        """Joystick index 0 ignores events from joystick index 1."""
        # JOYHATMOTION with joy=1 should not affect joystick_input (index 0)
        joystick_input.handle_event(
            pygame.event.Event(
                pygame.JOYHATMOTION, value=(0, 1), hat=0, joy=1, instance_id=1
            )
        )
        assert joystick_input.get_movement_direction() == (0, 0)

        # JOYHATMOTION with joy=0 should not affect joystick_input_1 (index 1)
        joystick_input_1.handle_event(
            pygame.event.Event(
                pygame.JOYHATMOTION, value=(0, 1), hat=0, joy=0, instance_id=0
            )
        )
        assert joystick_input_1.get_movement_direction() == (0, 0)

    def test_ignores_keyboard_events(self, joystick_input: PlayerInput) -> None:
        """Joystick source ignores keyboard KEYDOWN events."""
        joystick_input.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        assert joystick_input.get_movement_direction() == (0, 0)
        joystick_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        )
        assert joystick_input.consume_shoot() is False

    def test_axis_with_deadzone(self, joystick_input: PlayerInput) -> None:
        """Axis within deadzone sets no direction; beyond deadzone sets direction."""
        # Within deadzone — no direction
        joystick_input.handle_event(
            pygame.event.Event(
                pygame.JOYAXISMOTION, axis=0, value=0.3, joy=0, instance_id=0
            )
        )
        assert joystick_input.get_movement_direction() == (0, 0)

        # Beyond deadzone — sets direction
        joystick_input.handle_event(
            pygame.event.Event(
                pygame.JOYAXISMOTION, axis=0, value=-0.8, joy=0, instance_id=0
            )
        )
        assert joystick_input.get_movement_direction() == (-1, 0)
