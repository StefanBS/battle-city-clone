import pytest
import pygame
from unittest.mock import MagicMock

# Import necessary types for the helper
from src.core.tile import Tile, TileType
from src.core.bullet import Bullet
from src.core.player_tank import PlayerTank
from src.core.enemy_tank import EnemyTank


# Turn the helper into a fixture so it can be injected
@pytest.fixture
def create_mock_sprite():
    # Define the function that the fixture will return
    def _create_mock_sprite_func(
        x,
        y,
        w,
        h,
        spec=None,
        owner_type=None,
        active=True,
        is_invincible=False,
        lives=3,
        tile_type=None,  # Added tile_type back as parameter
        **kwargs,  # Accept arbitrary keyword arguments
    ):
        # Using spec for better type checking in tests
        sprite = MagicMock(spec=spec if spec else object)
        sprite.rect = pygame.Rect(x, y, w, h)

        # Assign common attributes directly based on spec or args
        if spec is Bullet:
            sprite.owner_type = owner_type if owner_type else "unknown"
            sprite.active = active
        elif spec is PlayerTank:
            sprite.is_invincible = is_invincible
            sprite.lives = lives
            sprite.owner_type = "player"  # PlayerTank should always have this
            # Mock methods if spec is PlayerTank
            sprite.take_damage = MagicMock(return_value=False)
            sprite.respawn = MagicMock()
        elif spec is EnemyTank:
            sprite.owner_type = "enemy"  # EnemyTank should always have this
            # Mock methods if spec is EnemyTank
            sprite.take_damage = MagicMock(return_value=False)
        elif spec is Tile:
            # Set tile type if provided, otherwise default (or leave unset?)
            # Let's default to EMPTY if not specified for Tiles
            sprite.type = tile_type if tile_type is not None else TileType.EMPTY

        # Allow overriding specific attributes if needed
        if owner_type is not None:
            sprite.owner_type = owner_type
        if hasattr(sprite, "active"):  # Check if attribute exists from spec
            sprite.active = active
        if hasattr(sprite, "is_invincible"):
            sprite.is_invincible = is_invincible
        if hasattr(sprite, "lives"):
            sprite.lives = lives
        if hasattr(sprite, "type") and tile_type is not None:
            sprite.type = tile_type  # Allow overriding TileType

        # Assign any additional keyword arguments as attributes
        for key, value in kwargs.items():
            setattr(sprite, key, value)

        return sprite

    # The fixture returns the function itself
    return _create_mock_sprite_func


# Mock classes removed from here, moved back to test file
# class MockPlayerTank(pygame.sprite.Sprite):
#     pass
# class MockEnemyTank(pygame.sprite.Sprite):
#     pass
# class MockBullet(pygame.sprite.Sprite):
#     pass
# class MockTile(pygame.sprite.Sprite):
#     pass
