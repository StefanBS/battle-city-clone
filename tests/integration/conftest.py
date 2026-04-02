import os
import pytest
import pygame
from src.managers.game_manager import GameManager
from loguru import logger

# Use a virtual framebuffer so integration tests don't open real windows.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
# Disable audio to prevent hangs on CI runners without audio devices.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Initialize pygame at import time so tests that construct GameManager
# directly (without the fixture) still have a working pygame subsystem.
pygame.init()


@pytest.fixture
def game_manager_fixture():
    """Fixture to provide a standard GameManager instance for integration tests."""
    pygame.init()
    manager = GameManager()
    return manager
