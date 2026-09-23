import pytest
import pygame
from unittest.mock import MagicMock, patch
from src.managers.game_manager import GameManager
from src.managers.texture_manager import TextureManager
from src.utils.paths import resource_path


@pytest.fixture
def _mock_game_deps():
    """Mock every external dependency GameManager pulls in.

    Used by the `game_manager` / `game_manager_at_title` fixtures below. The
    Battle is mocked as a whole: its frame rules are covered in
    test_battle.py. Yields the mocked Battle class so tests can check how
    each Battle was built. Classes that construct GameManager differently
    (e.g. the curtain tests) build their own instances and do not depend on
    this fixture.
    """
    with (
        patch("pygame.display.set_mode"),
        patch("pygame.font.SysFont"),
        patch("src.managers.game_manager.TextureManager"),
        patch("src.managers.game_manager.Renderer"),
        patch("src.managers.game_manager.Map"),
        patch("src.managers.game_manager.SettingsManager") as MockSM,
        patch("src.managers.game_manager.Battle") as MockBattle,
    ):
        mock_sm_instance = MockSM.return_value
        mock_sm_instance.master_volume = 1.0
        MockBattle.return_value.step.return_value = None
        yield MockBattle


@pytest.fixture
def game_manager(_mock_game_deps):
    """GameManager with game started (past title screen)."""
    manager = GameManager()
    manager._reset_game()
    return manager


@pytest.fixture
def game_manager_at_title(_mock_game_deps):
    """GameManager at the title screen (no _reset_game)."""
    return GameManager()


@pytest.fixture
def create_mock_sprite():
    """Factory fixture to create mock game objects with a rect."""

    def _create(x, y, w, h, spec=None, **attrs):
        sprite = MagicMock(spec=spec if spec else object)
        sprite.rect = pygame.Rect(x, y, w, h)
        for key, value in attrs.items():
            setattr(sprite, key, value)
        return sprite

    return _create


@pytest.fixture(scope="session")
def real_texture_manager(pygame_init):
    # Ensure display is initialized (session-scoped fixtures may run
    # after pygame.quit() in another conftest or before set_mode)
    if not pygame.display.get_surface():
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
    return TextureManager(resource_path("assets/sprites/sprites.png"))
