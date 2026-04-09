"""Integration tests for controller/gamepad support."""

import pygame
from src.managers.game_manager import GameManager
from src.states.game_state import GameState


class TestControllerGameplay:
    """Test controller input during gameplay with SDL GameController API."""

    def test_ctrl_dpad_moves_player(self) -> None:
        """Controller D-pad UP moves the player tank up."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING
        initial_y = gm.player_tank.y

        event = pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN,
            button=pygame.CONTROLLER_BUTTON_DPAD_UP,
        )
        gm.input_handler.handle_event(event)
        gm.update()

        assert gm.player_tank.y < initial_y

    def test_ctrl_stick_moves_player(self) -> None:
        """Controller left stick UP moves the player tank up."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING
        initial_y = gm.player_tank.y

        event = pygame.event.Event(
            pygame.CONTROLLERAXISMOTION,
            axis=pygame.CONTROLLER_AXIS_LEFTY,
            value=-0.8,
        )
        gm.input_handler.handle_event(event)
        gm.update()

        assert gm.player_tank.y < initial_y

    def test_ctrl_a_button_fires_bullet(self) -> None:
        """Controller A button fires a bullet."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING

        event = pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN,
            button=pygame.CONTROLLER_BUTTON_A,
        )
        gm.input_handler.handle_event(event)
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


class TestRawJoystickGameplay:
    """Test raw joystick input (fallback for unrecognized controllers)."""

    def test_hat_moves_player(self) -> None:
        """Raw joystick hat moves the player tank."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING
        initial_y = gm.player_tank.y

        event = pygame.event.Event(
            pygame.JOYHATMOTION, value=(0, 1), hat=0, instance_id=0
        )
        gm.input_handler.handle_event(event)
        gm.update()

        assert gm.player_tank.y < initial_y

    def test_raw_button_fires_bullet(self) -> None:
        """Raw joystick button 0 fires a bullet."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING

        event = pygame.event.Event(pygame.JOYBUTTONDOWN, button=0, instance_id=0)
        gm.input_handler.handle_event(event)
        gm.update()

        assert len(gm.bullets) > 0


class TestControllerMenuNavigation:
    """Test controller input in menus."""

    def test_ctrl_dpad_navigates_title_screen(self) -> None:
        """Controller D-pad navigates title screen menu items."""
        gm = GameManager()
        initial_selection = gm._title_selection

        event = pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN,
            button=pygame.CONTROLLER_BUTTON_DPAD_DOWN,
        )
        gm.input_handler.handle_event(event)
        actions = gm.input_handler.consume_menu_actions()
        for action in actions:
            gm._handle_title_input(action)

        assert gm._title_selection != initial_selection

    def test_ctrl_a_confirms_title_selection(self) -> None:
        """Controller A button confirms the selected title screen option."""
        gm = GameManager()
        gm._title_selection = 0  # 1 Player

        event = pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN,
            button=pygame.CONTROLLER_BUTTON_A,
        )
        gm.input_handler.handle_event(event)
        actions = gm.input_handler.consume_menu_actions()
        for action in actions:
            gm._handle_title_input(action)

        assert gm.state != GameState.TITLE_SCREEN

    def test_keyboard_r_returns_from_game_over(self) -> None:
        """Keyboard R produces MenuAction.CONFIRM in Game Over."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.GAME_OVER

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
        gm.input_handler.handle_event(event)
        gm._process_menu_actions()

        assert gm.state == GameState.TITLE_SCREEN
