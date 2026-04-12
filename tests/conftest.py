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


@pytest.fixture
def ctrl_button_down_event():
    """Factory fixture to create CONTROLLERBUTTONDOWN events."""

    def _ctrl_button_down_event(
        button: int, instance_id: int = 0
    ) -> pygame.event.Event:
        return pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN, button=button, instance_id=instance_id
        )

    return _ctrl_button_down_event


@pytest.fixture
def ctrl_button_up_event():
    """Factory fixture to create CONTROLLERBUTTONUP events."""

    def _ctrl_button_up_event(
        button: int, instance_id: int = 0
    ) -> pygame.event.Event:
        return pygame.event.Event(
            pygame.CONTROLLERBUTTONUP, button=button, instance_id=instance_id
        )

    return _ctrl_button_up_event


@pytest.fixture
def ctrl_axis_event():
    """Factory fixture to create CONTROLLERAXISMOTION events.

    ``value`` is a float in [-1.0, 1.0] that is converted to the int16 range
    that pygame uses for real CONTROLLERAXISMOTION events.
    """

    def _ctrl_axis_event(
        axis: int, value: float, instance_id: int = 0
    ) -> pygame.event.Event:
        return pygame.event.Event(
            pygame.CONTROLLERAXISMOTION,
            axis=axis,
            value=int(value * 32767),
            instance_id=instance_id,
        )

    return _ctrl_axis_event


@pytest.fixture
def ctrl_device_added_event():
    """Factory fixture to create CONTROLLERDEVICEADDED events."""

    def _ctrl_device_added_event(device_index: int = 0) -> pygame.event.Event:
        return pygame.event.Event(
            pygame.CONTROLLERDEVICEADDED, device_index=device_index
        )

    return _ctrl_device_added_event


@pytest.fixture
def ctrl_device_removed_event():
    """Factory fixture to create CONTROLLERDEVICEREMOVED events."""

    def _ctrl_device_removed_event(instance_id: int = 0) -> pygame.event.Event:
        return pygame.event.Event(
            pygame.CONTROLLERDEVICEREMOVED, instance_id=instance_id
        )

    return _ctrl_device_removed_event
