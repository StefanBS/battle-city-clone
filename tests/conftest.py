import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.texture_manager import TextureManager


@pytest.fixture(scope="session", autouse=True)
def pygame_init():
    """Initialize pygame once for the entire test session."""
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    yield
    pygame.quit()


@pytest.fixture
def mock_texture_manager():
    """Create a mock TextureManager with a stub get_sprite."""
    mock_tm = MagicMock(spec=TextureManager)
    mock_tm.get_sprite.return_value = MagicMock(spec=pygame.Surface)
    return mock_tm
