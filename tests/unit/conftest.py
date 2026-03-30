import pytest
import pygame


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
