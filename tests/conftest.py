import pytest
import pygame
from unittest.mock import MagicMock
from src.core.tank import Tank
from src.managers.texture_manager import TextureManager
from src.utils.constants import OwnerType, TILE_SIZE


@pytest.fixture
def mock_texture_manager():
    """Create a mock TextureManager with a stub get_sprite."""
    mock_tm = MagicMock(spec=TextureManager)
    mock_tm.get_sprite.return_value = MagicMock(spec=pygame.Surface)
    return mock_tm


@pytest.fixture
def create_tank(mock_texture_manager):
    """Factory fixture to create Tank instances with sensible defaults."""

    def _create(x=0, y=0, **kwargs):
        defaults = dict(
            tile_size=TILE_SIZE,
            owner_type=OwnerType.PLAYER,
            map_width_px=16 * TILE_SIZE,
            map_height_px=16 * TILE_SIZE,
        )
        defaults.update(kwargs)
        return Tank(x, y, mock_texture_manager, **defaults)

    return _create


@pytest.fixture
def key_down_event():
    """Factory fixture to create KEYDOWN events."""

    def _key_down_event(key: int) -> pygame.event.Event:
        return pygame.event.Event(pygame.KEYDOWN, key=key)

    return _key_down_event


@pytest.fixture
def key_up_event():
    """Factory fixture to create KEYUP events."""

    def _key_up_event(key: int) -> pygame.event.Event:
        return pygame.event.Event(pygame.KEYUP, key=key)

    return _key_up_event
