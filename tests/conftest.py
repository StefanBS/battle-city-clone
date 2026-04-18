import pytest
import pygame
from contextlib import nullcontext
from unittest.mock import MagicMock, patch
from src.core.bullet import Bullet
from src.core.enemy_tank import EnemyTank
from src.core.player_tank import PlayerTank
from src.core.tank import Tank
from src.managers.texture_manager import TextureManager
from src.utils.constants import Direction, OwnerType, TankType, TILE_SIZE


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
def create_enemy_tank(mock_texture_manager):
    """Factory fixture to create EnemyTank instances with sensible defaults.

    By default the EnemyTank __init__ call is wrapped in a patch that pins
    random.choice to Direction.DOWN so test setup is deterministic. Pass
    ``patch_random=False`` to opt out (e.g. for tests that exercise the
    initial direction choice themselves).
    """

    def _create(x=0, y=0, tank_type=TankType.BASIC, patch_random=True, **kwargs):
        defaults = dict(
            tile_size=TILE_SIZE,
            map_width_px=16 * TILE_SIZE,
            map_height_px=16 * TILE_SIZE,
        )
        defaults.update(kwargs)
        tile_size = defaults.pop("tile_size")
        ctx = (
            patch("src.core.enemy_tank.random.choice", return_value=Direction.DOWN)
            if patch_random
            else nullcontext()
        )
        with ctx:
            return EnemyTank(
                x, y, tile_size, mock_texture_manager, tank_type, **defaults
            )

    return _create


@pytest.fixture
def create_player_tank(mock_texture_manager):
    """Factory fixture to create PlayerTank instances with sensible defaults."""

    def _create(x=0, y=0, **kwargs):
        defaults = dict(
            tile_size=TILE_SIZE,
            map_width_px=16 * TILE_SIZE,
            map_height_px=16 * TILE_SIZE,
        )
        defaults.update(kwargs)
        tile_size = defaults.pop("tile_size")
        return PlayerTank(x, y, tile_size, mock_texture_manager, **defaults)

    return _create


@pytest.fixture
def make_bullet():
    """Factory fixture to build MagicMock(spec=Bullet) with sensible defaults.

    Keyword overrides set attributes on the mock, so callers can do e.g.
    ``make_bullet(owner_type=OwnerType.ENEMY, power_bullet=True, rect=...)``.
    """

    def _create(owner_type=OwnerType.PLAYER, **overrides):
        b = MagicMock(spec=Bullet)
        b.active = True
        b.owner_type = owner_type
        b.owner = MagicMock()
        b.rect = pygame.Rect(0, 0, 2, 2)
        b.direction = Direction.UP
        b.power_bullet = False
        for key, value in overrides.items():
            setattr(b, key, value)
        return b

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

    def _ctrl_button_up_event(button: int, instance_id: int = 0) -> pygame.event.Event:
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
