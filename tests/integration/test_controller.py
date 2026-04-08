"""Integration tests for controller/gamepad support."""

import pygame
from src.managers.game_manager import GameManager
from src.states.game_state import GameState


class TestControllerGameplay:
    """Test controller input during gameplay."""

    def test_dpad_moves_player(self) -> None:
        """D-pad hat input moves the player tank."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING
        initial_y = gm.player_tank.y

        hat_event = pygame.event.Event(
            pygame.JOYHATMOTION, value=(0, 1), hat=0, instance_id=0
        )
        gm.input_handler.handle_event(hat_event)
        gm.update()

        assert gm.player_tank.y < initial_y

    def test_stick_moves_player(self) -> None:
        """Analog stick input moves the player tank."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING
        initial_y = gm.player_tank.y

        axis_event = pygame.event.Event(
            pygame.JOYAXISMOTION, axis=1, value=-0.8, instance_id=0
        )
        gm.input_handler.handle_event(axis_event)
        gm.update()

        assert gm.player_tank.y < initial_y

    def test_button_fires_bullet(self) -> None:
        """Controller button fires a bullet."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING

        button_event = pygame.event.Event(pygame.JOYBUTTONDOWN, button=0, instance_id=0)
        gm.input_handler.handle_event(button_event)
        gm.update()

        assert len(gm.bullets) > 0

    def test_keyboard_still_works(self) -> None:
        """Keyboard input still works alongside controller."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING
        initial_y = gm.player_tank.y

        key_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        gm.input_handler.handle_event(key_event)
        gm.update()

        assert gm.player_tank.y < initial_y


class TestControllerMenuNavigation:
    """Test controller input in menus."""

    def test_dpad_navigates_title_screen(self) -> None:
        """D-pad navigates title screen menu items."""
        gm = GameManager()
        initial_selection = gm._title_selection

        hat_down = pygame.event.Event(
            pygame.JOYHATMOTION, value=(0, -1), hat=0, instance_id=0
        )
        translated = gm._translate_joy_event(hat_down)
        gm._handle_title_input(translated)

        assert gm._title_selection != initial_selection

    def test_button_confirms_title_selection(self) -> None:
        """A button confirms the selected title screen option."""
        gm = GameManager()
        gm._title_selection = 0  # 1 Player

        btn = pygame.event.Event(pygame.JOYBUTTONDOWN, button=0, instance_id=0)
        translated = gm._translate_joy_event(btn)
        gm._handle_title_input(translated)

        assert gm.state != GameState.TITLE_SCREEN
