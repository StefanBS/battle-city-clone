"""Integration tests for SDL GameController gameplay input."""

import pygame
import pytest
from src.managers.game_manager import GameManager
from src.managers.player_input import AXIS_MAX
from src.states.game_state import GameState
from tests.integration.conftest import first_player


def _send_event(gm, event):
    """Send event to both input_handler and player_manager."""
    gm.input_handler.handle_event(event)
    gm.player_manager.handle_event(event)


def _up_event(source: str) -> pygame.event.Event:
    if source == "dpad":
        return pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN,
            button=pygame.CONTROLLER_BUTTON_DPAD_UP,
            instance_id=0,
        )
    if source == "stick":
        return pygame.event.Event(
            pygame.CONTROLLERAXISMOTION,
            axis=pygame.CONTROLLER_AXIS_LEFTY,
            value=int(-0.8 * AXIS_MAX),
            instance_id=0,
        )
    if source == "keyboard":
        return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
    raise ValueError(f"Unknown input source: {source}")


class TestControllerGameplay:
    """Test controller input during gameplay via the SDL GameController API."""

    @pytest.mark.parametrize("source", ["dpad", "stick", "keyboard"])
    def test_up_input_moves_player(self, game_manager_fixture, source: str) -> None:
        """D-pad, left stick, and keyboard all move the player tank up."""
        gm = game_manager_fixture
        initial_y = first_player(gm).y

        _send_event(gm, _up_event(source))
        gm.update()

        assert first_player(gm).y < initial_y

    def test_ctrl_a_button_fires_bullet(self, game_manager_fixture) -> None:
        """Controller A button fires a bullet."""
        gm = game_manager_fixture

        event = pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN,
            button=pygame.CONTROLLER_BUTTON_A,
            instance_id=0,
        )
        _send_event(gm, event)
        gm.update()

        assert len(gm.player_manager.get_all_bullets()) > 0


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
