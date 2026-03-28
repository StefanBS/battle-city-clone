import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.texture_manager import TextureManager


@pytest.fixture(scope="session")
def mock_texture_manager():
    """Create a session-scoped mock TextureManager."""
    pygame.init()
    mock_tm = MagicMock(spec=TextureManager)
    mock_tm.get_sprite.return_value = MagicMock(spec=pygame.Surface)
    return mock_tm
