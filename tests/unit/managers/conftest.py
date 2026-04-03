import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.texture_manager import TextureManager
from src.utils.paths import resource_path


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
    return TextureManager(resource_path("assets/sprites/sprites.png"))
