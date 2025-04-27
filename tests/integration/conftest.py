import pytest
import pygame
from src.managers.game_manager import GameManager
from loguru import logger

# Initialize Pygame non-graphically for testing
# This ensures pygame features are available for all integration tests
try:
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)  # Minimal display init
    logger.info("Pygame initialized for integration tests.")
except pygame.error as e:
    logger.error(f"Pygame initialization failed in conftest: {e}")
    # Decide how to handle this - maybe skip tests or raise error


@pytest.fixture
def game_manager_fixture():
    """Fixture to provide a standard GameManager instance for integration tests."""
    logger.debug("Creating GameManager instance via fixture...")
    # Simply create and return a new GameManager
    # Tests that need specific map setups will modify it directly.
    manager = GameManager()
    logger.debug("GameManager instance created.")
    return manager
