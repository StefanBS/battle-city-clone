"""Integration tests for SDL GameController gameplay input."""

import pygame
from src.managers.game_manager import GameManager
from src.managers.player_input import AXIS_MAX
from src.states.game_state import GameState


def _send_event(gm, event):
    """Send event to both input_handler and player_manager."""
    gm.input_handler.handle_event(event)
    gm.player_manager.handle_event(event)


class TestControllerGameplay:
    """Test controller input during gameplay via the SDL GameController API."""

    def test_ctrl_dpad_moves_player(self) -> None:
        """Controller D-pad UP moves the player tank up."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING
        initial_y = gm.player_tank.y

        event = pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN,
            button=pygame.CONTROLLER_BUTTON_DPAD_UP,
            instance_id=0,
        )
        _send_event(gm, event)
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
            value=int(-0.8 * AXIS_MAX),
            instance_id=0,
        )
        _send_event(gm, event)
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
            instance_id=0,
        )
        _send_event(gm, event)
        gm.update()

        assert len(gm.player_manager.get_all_bullets()) > 0

    def test_keyboard_still_works(self) -> None:
        """Keyboard input still works alongside controller."""
        gm = GameManager()
        gm._reset_game()
        gm.state = GameState.RUNNING
        initial_y = gm.player_tank.y

        key_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        _send_event(gm, key_event)
        gm.update()

        assert gm.player_tank.y < initial_y


class TestControllerMenuNavigation:
    """Test controller input in menus."""

    def test_ctrl_dpad_navigates_title_screen(self) -> None:
        """Controller D-pad navigates title screen menu items."""
        gm = GameManager()
        initial_selection = gm._title_menu.selection

        pygame.event.post(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_DPAD_DOWN,
                instance_id=0,
            )
        )
        gm.handle_events()

        assert gm._title_menu.selection != initial_selection

    def test_ctrl_a_confirms_title_selection(self) -> None:
        """Controller A button confirms the selected title screen option."""
        gm = GameManager()
        gm._title_menu.selection = 0  # 1 Player

        pygame.event.post(
            pygame.event.Event(
                pygame.CONTROLLERBUTTONDOWN,
                button=pygame.CONTROLLER_BUTTON_A,
                instance_id=0,
            )
        )
        gm.handle_events()

        assert gm.state != GameState.TITLE_SCREEN
