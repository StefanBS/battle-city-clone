import pytest
import pygame
from unittest.mock import MagicMock, patch
from src.managers.game_manager import GameManager
from src.managers.texture_manager import TextureManager
from src.utils.paths import resource_path


@pytest.fixture
def _mock_game_deps():
    """Mock every external dependency GameManager pulls in at __init__.

    Used by the `game_manager` / `game_manager_at_title` fixtures below.
    Classes that construct GameManager differently (e.g. the curtain
    and powerups tests) build their own instances and do not depend on
    this fixture.
    """
    with (
        patch("pygame.display.set_mode"),
        patch("pygame.font.SysFont"),
        patch("src.managers.game_manager.TextureManager") as MockTM,
        patch("src.managers.game_manager.EffectManager"),
        patch("src.managers.game_manager.Renderer"),
        patch("src.managers.game_manager.SpawnManager"),
        patch("src.managers.game_manager.Map") as MockMap,
        patch("src.managers.game_manager.SettingsManager") as MockSM,
        patch("src.managers.game_manager.PlayerManager") as MockPM,
    ):
        mock_tm_instance = MockTM.return_value
        mock_tm_instance.get_sprite.return_value = MagicMock(spec=pygame.Surface)
        mock_sm_instance = MockSM.return_value
        mock_sm_instance.master_volume = 1.0
        mock_map_instance = MockMap.return_value
        mock_map_instance.width = 16
        mock_map_instance.height = 16
        mock_map_instance.player_spawn = (4, 12)
        mock_map_instance.spawn_points = [(3, 1), (8, 1), (12, 1)]
        mock_pm_instance = MockPM.return_value
        mock_player = MagicMock()
        mock_player.lives = 3
        mock_player.health = 1
        mock_player.x = 128
        mock_player.y = 384
        mock_player.is_moving = False
        mock_pm_instance.get_active_players.return_value = [mock_player]
        mock_pm_instance.score = 0
        mock_pm_instance.get_all_bullets.return_value = []
        yield


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
