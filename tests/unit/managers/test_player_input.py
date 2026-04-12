import pytest
import pygame
from src.managers.player_input import (
    AXIS_MAX,
    AxisState,
    classify_axis,
)


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


class TestCombinedInput:
    @pytest.fixture
    def combined(self):
        from src.managers.player_input import (
            CombinedInput,
            ControllerInput,
            KeyboardInput,
        )
        return CombinedInput([KeyboardInput(), ControllerInput(instance_id=None)])

    def test_keyboard_event_drives_direction(
        self, combined, key_down_event
    ) -> None:
        combined.handle_event(key_down_event(pygame.K_UP))
        assert combined.get_movement_direction() == (0, -1)

    def test_controller_event_drives_direction(
        self, combined, ctrl_button_down_event
    ) -> None:
        combined.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_LEFT)
        )
        assert combined.get_movement_direction() == (-1, 0)

    def test_merge_keyboard_and_controller_directions(
        self, combined, key_down_event, ctrl_button_down_event
    ) -> None:
        """Regression for #138: held keyboard LEFT + dpad UP → (-1, -1)."""
        combined.handle_event(key_down_event(pygame.K_LEFT))
        combined.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_DPAD_UP)
        )
        assert combined.get_movement_direction() == (-1, -1)

    def test_keyboard_shoot(self, combined, key_down_event) -> None:
        combined.handle_event(key_down_event(pygame.K_SPACE))
        assert combined.consume_shoot() is True

    def test_controller_shoot(self, combined, ctrl_button_down_event) -> None:
        combined.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_A)
        )
        assert combined.consume_shoot() is True

    def test_consume_shoot_drains_all_children(
        self, combined, key_down_event, ctrl_button_down_event
    ) -> None:
        """Both children have a pending shoot — a single consume_shoot must
        drain BOTH flags or a spurious bullet fires next frame."""
        combined.handle_event(key_down_event(pygame.K_SPACE))
        combined.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_A)
        )
        assert combined.consume_shoot() is True
        assert combined.consume_shoot() is False

    def test_clear_pending_shoot_forwards_to_all(
        self, combined, key_down_event, ctrl_button_down_event
    ) -> None:
        combined.handle_event(key_down_event(pygame.K_SPACE))
        combined.handle_event(
            ctrl_button_down_event(pygame.CONTROLLER_BUTTON_A)
        )
        combined.clear_pending_shoot()
        assert combined.consume_shoot() is False


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
