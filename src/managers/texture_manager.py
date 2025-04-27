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
            self.texture_atlas: pygame.Surface = pygame.image.load(
                texture_path
            ).convert_alpha()
        except pygame.error as e:
            logger.error(f"Error loading texture atlas: {e}")
            # Handle error appropriately, maybe raise an exception or exit
            raise SystemExit(f"Error loading texture atlas: {e}") from e

        self.sprites: dict[str, pygame.Surface] = {}
        self._load_sprites()

    def _load_sprites(self):
        """Loads individual sprites from the texture atlas."""

        # Coordinates are based on a 16x16 grid
        sprite_coords = {
            "player_tank_up_1": (40, 0),
            "player_tank_right_1": (42, 0),
            "player_tank_down_1": (44, 0),
            "player_tank_left_1": (46, 0),
            "player_tank_up_2": (40, 2),
            "player_tank_right_2": (42, 2),
            "player_tank_down_2": (44, 2),
            "player_tank_left_2": (46, 2),
            "enemy_tank_up_1": (8, 0),
            "enemy_tank_right_1": (10, 0),
            "enemy_tank_down_1": (12, 0),
            "enemy_tank_left_1": (14, 0),
            "enemy_tank_up_2": (8, 2),
            "enemy_tank_right_2": (10, 2),
            "enemy_tank_down_2": (12, 2),
            "enemy_tank_left_2": (14, 2),
        }

        # --- Add Tile Coordinates Here ---
        # Coordinates based on 16x16 grid
        tile_coords = {
            "brick": (58, 0),  # Placeholder
            "steel": (58, 2),  # Placeholder
            "bush": (58, 4),  # Placeholder
            "ice": (58, 6),  # Placeholder
            "base": (59, 0),
            "base_destroyed": (59, 2),
            "water_1": (58, 10),  # Water frame 1
            "water_2": (58, 11),  # Water frame 2
        }

        sprite_coords.update(tile_coords)
        # --- End Tile Coordinates ---

        for name, (x, y) in sprite_coords.items():
            src_x = x * SOURCE_TILE_SIZE
            src_y = y * SOURCE_TILE_SIZE

            # Determine the source dimensions based on sprite name
            if "tank" in name or name in ["base", "base_destroyed"]:
                src_width = SOURCE_TILE_SIZE * 2  # 32 pixels
                src_height = SOURCE_TILE_SIZE * 2  # 32 pixels
            elif name in []:  # This condition is now empty
                src_width = SOURCE_TILE_SIZE  # 16 pixels
                src_height = SOURCE_TILE_SIZE * 2  # 32 pixels
            elif name in ["steel", "bush", "ice", "brick", "water_1", "water_2"]:
                src_width = SOURCE_TILE_SIZE  # 16 pixels
                src_height = SOURCE_TILE_SIZE  # 16 pixels
            else:
                # Default assumption for any other unforeseen sprites
                src_width = SOURCE_TILE_SIZE
                src_height = SOURCE_TILE_SIZE
                logger.warning(
                    f"Assuming 16x16 source size for unrecognized sprite '{name}'"
                )

            rect = pygame.Rect(src_x, src_y, src_width, src_height)

            try:
                original_sprite = self.texture_atlas.subsurface(rect)
                # Scale the extracted sprite to the final game TILE_SIZE
                scaled_sprite = pygame.transform.scale(
                    original_sprite, (TILE_SIZE, TILE_SIZE)
                )
                self.sprites[name] = scaled_sprite
            except ValueError as e:
                logger.error(
                    f"Error loading sprite '{name}' with rect {rect}: {e}. "
                    f"Check coordinates and atlas dimensions."
                )

                return None

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
