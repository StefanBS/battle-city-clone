import pygame
from loguru import logger
from src.utils.constants import TILE_SIZE, SOURCE_TILE_SIZE


class TextureManager:
    """Manages loading and accessing game textures."""

    def __init__(self, texture_path: str):
        """
        Initializes the TextureManager.

        Args:
            texture_path: Path to the main texture atlas file.
        """
        try:
            self.texture_atlas: pygame.Surface = pygame.image.load(texture_path).convert_alpha()
        except pygame.error as e:
            logger.error(f"Error loading texture atlas: {e}")
            # Handle error appropriately, maybe raise an exception or exit
            raise SystemExit(f"Error loading texture atlas: {e}") from e

        self.sprites: dict[str, pygame.Surface] = {}
        self._load_sprites()

    def _load_sprites(self):
        """Loads individual sprites from the texture atlas."""

        sprite_coords = {
            "player_tank_up_1": (20, 0),
            "player_tank_right_1": (21, 0),
            "player_tank_down_1": (22, 0),
            "player_tank_left_1": (23, 0),
            "player_tank_up_2": (20, 1),
            "player_tank_right_2": (21, 1),
            "player_tank_down_2": (22, 1),
            "player_tank_left_2": (23, 1),
            "enemy_tank_up_1": (4, 0),
            "enemy_tank_right_1": (5, 0),
            "enemy_tank_down_1": (6, 0),
            "enemy_tank_left_1": (7, 0),
            "enemy_tank_up_2": (4, 1),
            "enemy_tank_right_2": (5, 1),
            "enemy_tank_down_2": (6, 1),
            "enemy_tank_left_2": (7, 1),
        }

        for name, (x, y) in sprite_coords.items():
            rect = pygame.Rect(
                x * SOURCE_TILE_SIZE,
                y * SOURCE_TILE_SIZE,
                SOURCE_TILE_SIZE,
                SOURCE_TILE_SIZE,
            )
            original_sprite = self.texture_atlas.subsurface(rect)
            scaled_sprite = pygame.transform.scale(
                original_sprite, (TILE_SIZE, TILE_SIZE)
            )
            self.sprites[name] = scaled_sprite

    def get_sprite(self, name: str) -> pygame.Surface:
        """
        Retrieves a specific sprite by name.

        Args:
            name: The name identifier of the sprite.

        Returns:
            The corresponding Pygame Surface for the sprite.

        Raises:
            KeyError: If the sprite name is not found.
        """
        try:
            return self.sprites[name]
        except KeyError:
            logger.error(f"Error: Sprite '{name}' not found.")
            # Optionally return a default 'missing' sprite or raise the error
            raise KeyError(f"Sprite '{name}' not found.") from KeyError
