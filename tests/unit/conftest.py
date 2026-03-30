import os
import pytest
import pygame

# Use a virtual framebuffer so unit tests don't open real windows.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


@pytest.fixture(scope="session", autouse=True)
def pygame_init():
    """Initialize pygame once for the unit test session.

    Scoped to tests/unit/ only — integration tests manage their own
    pygame lifecycle via GameManager.
    """
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    yield
    pygame.quit()
