import pytest
import pygame
from src.managers.player_input import (
    AXIS_MAX,
    AxisState,
    InputSource,
    PlayerInput,
    classify_axis,
)


@pytest.fixture
def keyboard_input() -> PlayerInput:
    """Fixture providing a keyboard-sourced PlayerInput."""
    return PlayerInput(InputSource.KEYBOARD)


@pytest.fixture
def controller_input() -> PlayerInput:
    """Fixture providing a controller-sourced PlayerInput (instance_id=0)."""
    return PlayerInput(InputSource.CONTROLLER, instance_id=0)


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

    def test_also_handles_controller_events(self, keyboard_input: PlayerInput) -> None:
        """Keyboard source also handles controller events for single-player use."""
        keyboard_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=0,
            )
        )
        assert keyboard_input.get_movement_direction() == (0, -1)

        keyboard_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_A,
                instance_id=0,
            )
        )
        assert keyboard_input.consume_shoot() is True


class TestControllerPlayerInput:
    def test_initial_direction_is_zero(self, controller_input: PlayerInput) -> None:
        """Initial movement direction is (0, 0)."""
        assert controller_input.get_movement_direction() == (0, 0)

    def test_controller_dpad_sets_direction(
        self, controller_input: PlayerInput
    ) -> None:
        """CONTROLLERBUTTONDOWN for DPAD_UP sets direction to (0, -1)."""
        controller_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=0,
            )
        )
        assert controller_input.get_movement_direction() == (0, -1)

    def test_controller_shoot_button(self, controller_input: PlayerInput) -> None:
        """CONTROLLERBUTTONDOWN for A button sets shoot flag."""
        controller_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_A,
                instance_id=0,
            )
        )
        assert controller_input.consume_shoot() is True

    def test_exclusive_mode_ignores_events_from_other_controller(self) -> None:
        """In 2P (exclusive) mode each player listens only to its own device."""
        p0 = PlayerInput(InputSource.CONTROLLER, instance_id=0, exclusive=True)
        p1 = PlayerInput(InputSource.CONTROLLER, instance_id=1, exclusive=True)

        # p0 should ignore events from instance_id=1
        p0.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=1,
            )
        )
        assert p0.get_movement_direction() == (0, 0)

        # p1 should ignore events from instance_id=0
        p1.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=0,
            )
        )
        assert p1.get_movement_direction() == (0, 0)

    def test_exclusive_mode_routes_non_zero_instance_id(self) -> None:
        """Exclusive mode accepts the event when instance_id matches the binding.

        Regression: previously the filter compared against a device index that
        assumed 0-based sequential IDs, so a controller with instance_id=5
        routed incorrectly.
        """
        p = PlayerInput(InputSource.CONTROLLER, instance_id=5, exclusive=True)
        p.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=5,
            )
        )
        assert p.get_movement_direction() == (0, -1)

    def test_non_exclusive_mode_accepts_any_controller(
        self, controller_input: PlayerInput
    ) -> None:
        """In 1P (non-exclusive) mode events from any controller drive the player."""
        controller_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=99,
            )
        )
        assert controller_input.get_movement_direction() == (0, -1)

    def test_also_handles_keyboard_events(
        self, controller_input: PlayerInput
    ) -> None:
        """Non-exclusive controller source also handles keyboard events."""
        controller_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        )
        assert controller_input.get_movement_direction() == (0, -1)
        controller_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        )
        assert controller_input.consume_shoot() is True

    def test_dpad_press_preserves_perpendicular_keyboard_state(
        self, controller_input: PlayerInput
    ) -> None:
        """Pressing dpad on one axis must not clear held keyboard state on the
        perpendicular axis in 1P non-exclusive mode.

        Regression for #138: previously the dpad handler zeroed all four
        directions before setting the new one, silently dropping a held
        keyboard direction whenever the user tapped a perpendicular dpad button.
        """
        controller_input.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT)
        )
        assert controller_input.get_movement_direction() == (-1, 0)

        controller_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
                instance_id=0,
            )
        )

        assert controller_input.get_movement_direction() == (-1, -1)

    def test_dpad_press_clears_opposite_on_same_axis(
        self, controller_input: PlayerInput
    ) -> None:
        """A dpad press on one axis must cancel the opposite direction on the
        same axis (e.g. pressing LEFT cancels RIGHT) so the player doesn't
        stay pinned when the user sweeps across the dpad."""
        controller_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
                instance_id=0,
            )
        )
        assert controller_input.get_movement_direction() == (1, 0)

        controller_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_LEFT,
                instance_id=0,
            )
        )
        assert controller_input.get_movement_direction() == (-1, 0)

    def test_axis_with_deadzone(self, controller_input: PlayerInput) -> None:
        """Axis within deadzone sets no direction; beyond deadzone sets direction."""
        # Within deadzone — no direction
        controller_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERAXISMOTION,
                axis=pygame.CONTROLLER_AXIS_LEFTX,
                value=int(0.3 * AXIS_MAX),
                instance_id=0,
            )
        )
        assert controller_input.get_movement_direction() == (0, 0)

        # Beyond deadzone — sets direction
        controller_input.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERAXISMOTION,
                axis=pygame.CONTROLLER_AXIS_LEFTX,
                value=int(-0.8 * AXIS_MAX),
                instance_id=0,
            )
        )
        assert controller_input.get_movement_direction() == (-1, 0)


class TestPlayerInputConstructor:
    def test_controller_without_instance_id_raises(self) -> None:
        """CONTROLLER source requires instance_id."""
        with pytest.raises(ValueError, match="instance_id is required"):
            PlayerInput(InputSource.CONTROLLER)

    def test_keyboard_without_instance_id_ok(self) -> None:
        """KEYBOARD source does not require instance_id."""
        PlayerInput(InputSource.KEYBOARD)  # no raise


class TestPlayerInputExclusiveMode:
    def test_exclusive_keyboard_ignores_controller(self):
        """In exclusive mode, KEYBOARD source ignores controller events."""
        pi = PlayerInput(InputSource.KEYBOARD, exclusive=True)
        pi.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_A,
                instance_id=0,
            )
        )
        assert pi.consume_shoot() is False

    def test_exclusive_controller_ignores_keyboard(self):
        """In exclusive mode, CONTROLLER source ignores keyboard events."""
        pi = PlayerInput(InputSource.CONTROLLER, instance_id=0, exclusive=True)
        pi.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        assert pi.consume_shoot() is False

    def test_non_exclusive_keyboard_handles_controller(self):
        """Without exclusive mode, KEYBOARD source still handles controller events."""
        pi = PlayerInput(InputSource.KEYBOARD)
        pi.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_A,
                instance_id=0,
            )
        )
        assert pi.consume_shoot() is True

    def test_exclusive_keyboard_handles_keyboard(self):
        """In exclusive mode, KEYBOARD source still handles keyboard events."""
        pi = PlayerInput(InputSource.KEYBOARD, exclusive=True)
        pi.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        assert pi.consume_shoot() is True

    def test_exclusive_controller_handles_controller(self):
        """In exclusive mode, CONTROLLER source still handles controller events."""
        pi = PlayerInput(InputSource.CONTROLLER, instance_id=0, exclusive=True)
        pi.handle_event(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_A,
                instance_id=0,
            )
        )
        assert pi.consume_shoot() is True


class TestControllerInput:
    @pytest.fixture
    def ci(self):
        from src.managers.player_input import ControllerInput
        return ControllerInput(instance_id=0)

    @pytest.fixture
    def ci_any(self):
        from src.managers.player_input import ControllerInput
        return ControllerInput(instance_id=None)

    def test_dpad_up_sets_direction(self, ci, ctrl_button_down_event) -> None:
        ci.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_UP)
        )
        assert ci.get_movement_direction() == (0, -1)

    def test_dpad_release_clears_direction(
        self, ci, ctrl_button_down_event, ctrl_button_up_event
    ) -> None:
        ci.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_UP)
        )
        ci.handle_event(
            ctrl_button_up_event(pygame.CONTROLLER_BUTTON_DPAD_UP)
        )
        assert ci.get_movement_direction() == (0, 0)

    def test_dpad_press_clears_opposite_on_same_axis(
        self, ci, ctrl_button_down_event
    ) -> None:
        """Regression for #138: pressing LEFT while RIGHT held cancels RIGHT."""
        ci.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
        )
        ci.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_LEFT)
        )
        assert ci.get_movement_direction() == (-1, 0)

    def test_dpad_press_preserves_perpendicular_axis(
        self, ci, ctrl_button_down_event
    ) -> None:
        ci.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_LEFT)
        )
        ci.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_UP)
        )
        assert ci.get_movement_direction() == (-1, -1)

    def test_axis_inside_deadzone_is_zero(self, ci, ctrl_axis_event) -> None:
        ci.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        assert ci.get_movement_direction() == (0, 0)

    def test_axis_beyond_positive_deadzone_sets_direction(
        self, ci, ctrl_axis_event
    ) -> None:
        ci.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, 0.8))
        assert ci.get_movement_direction() == (1, 0)

    def test_axis_beyond_negative_deadzone_sets_direction(
        self, ci, ctrl_axis_event
    ) -> None:
        ci.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTY, -0.8))
        assert ci.get_movement_direction() == (0, -1)

    def test_axis_return_to_neutral_clears_direction(
        self, ci, ctrl_axis_event
    ) -> None:
        ci.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, 0.8))
        ci.handle_event(ctrl_axis_event(pygame.CONTROLLER_AXIS_LEFTX, 0.0))
        assert ci.get_movement_direction() == (0, 0)

    def test_shoot_button_a(self, ci, ctrl_button_down_event) -> None:
        ci.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_A))
        assert ci.consume_shoot() is True

    def test_shoot_button_b(self, ci, ctrl_button_down_event) -> None:
        ci.handle_event(ctrl_button_down_event(pygame.CONTROLLER_BUTTON_B))
        assert ci.consume_shoot() is True

    def test_instance_id_filter_rejects_foreign_events(
        self, ci, ctrl_button_down_event
    ) -> None:
        ci.handle_event(
            ctrl_button_down_event(
                pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=99
            )
        )
        assert ci.get_movement_direction() == (0, 0)

    def test_instance_id_none_accepts_any_controller(
        self, ci_any, ctrl_button_down_event
    ) -> None:
        ci_any.handle_event(
            ctrl_button_down_event(
                pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=42
            )
        )
        assert ci_any.get_movement_direction() == (0, -1)

    def test_instance_id_accepts_matching_nonzero(
        self, ctrl_button_down_event
    ) -> None:
        from src.managers.player_input import ControllerInput
        ci = ControllerInput(instance_id=5)
        ci.handle_event(
            ctrl_button_down_event(
                pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=5
            )
        )
        assert ci.get_movement_direction() == (0, -1)

    def test_ignores_keyboard_events(self, ci, key_down_event) -> None:
        ci.handle_event(key_down_event(pygame.K_UP))
        ci.handle_event(key_down_event(pygame.K_SPACE))
        assert ci.get_movement_direction() == (0, 0)
        assert ci.consume_shoot() is False


class TestKeyboardInput:
    @pytest.fixture
    def ki(self):
        from src.managers.player_input import KeyboardInput
        return KeyboardInput()

    def test_initial_direction_zero(self, ki) -> None:
        assert ki.get_movement_direction() == (0, 0)

    def test_initial_shoot_false(self, ki) -> None:
        assert ki.consume_shoot() is False

    def test_arrow_up_sets_direction(self, ki, key_down_event) -> None:
        ki.handle_event(key_down_event(pygame.K_UP))
        assert ki.get_movement_direction() == (0, -1)

    def test_arrow_release_clears_direction(
        self, ki, key_down_event, key_up_event
    ) -> None:
        ki.handle_event(key_down_event(pygame.K_UP))
        ki.handle_event(key_up_event(pygame.K_UP))
        assert ki.get_movement_direction() == (0, 0)

    def test_held_opposite_cancels(self, ki, key_down_event) -> None:
        ki.handle_event(key_down_event(pygame.K_UP))
        ki.handle_event(key_down_event(pygame.K_DOWN))
        assert ki.get_movement_direction() == (0, 0)

    def test_space_sets_shoot(self, ki, key_down_event) -> None:
        ki.handle_event(key_down_event(pygame.K_SPACE))
        assert ki.consume_shoot() is True

    def test_consume_shoot_clears_flag(self, ki, key_down_event) -> None:
        ki.handle_event(key_down_event(pygame.K_SPACE))
        ki.consume_shoot()
        assert ki.consume_shoot() is False

    def test_clear_pending_shoot(self, ki, key_down_event) -> None:
        ki.handle_event(key_down_event(pygame.K_SPACE))
        ki.clear_pending_shoot()
        assert ki.consume_shoot() is False

    def test_ignores_non_gameplay_keys(self, ki, key_down_event) -> None:
        ki.handle_event(key_down_event(pygame.K_a))
        ki.handle_event(key_down_event(pygame.K_ESCAPE))
        assert ki.get_movement_direction() == (0, 0)
        assert ki.consume_shoot() is False

    def test_ignores_controller_events(self, ki, ctrl_button_down_event) -> None:
        ki.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_UP)
        )
        ki.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_A)
        )
        assert ki.get_movement_direction() == (0, 0)
        assert ki.consume_shoot() is False


class TestClassifyAxis:
    def test_neutral_at_zero(self) -> None:
        assert classify_axis(0) is AxisState.NEUTRAL

    def test_neutral_inside_positive_deadzone(self) -> None:
        # AXIS_DEADZONE = 0.5; an int16 just below 0.5 * AXIS_MAX is NEUTRAL
        assert classify_axis(int(0.49 * AXIS_MAX)) is AxisState.NEUTRAL

    def test_neutral_inside_negative_deadzone(self) -> None:
        assert classify_axis(int(-0.49 * AXIS_MAX)) is AxisState.NEUTRAL

    def test_positive_just_above_deadzone(self) -> None:
        assert classify_axis(int(0.51 * AXIS_MAX)) is AxisState.POSITIVE

    def test_negative_just_below_deadzone(self) -> None:
        assert classify_axis(int(-0.51 * AXIS_MAX)) is AxisState.NEGATIVE

    def test_positive_int16_max(self) -> None:
        assert classify_axis(AXIS_MAX) is AxisState.POSITIVE

    def test_negative_int16_min(self) -> None:
        assert classify_axis(-AXIS_MAX) is AxisState.NEGATIVE
