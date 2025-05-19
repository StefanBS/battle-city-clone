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

        # Coordinates are based on a 8x8 grid
        sprite_coords = {
            "player_tank_up_1": (0, 0),
            "player_tank_up_2": (2, 0),
            "player_tank_left_1": (4, 0),
            "player_tank_left_2": (6, 0),
            "player_tank_down_1": (8, 0),
            "player_tank_down_2": (10, 0),
            "player_tank_right_1": (12, 0),
            "player_tank_right_2": (14, 0),
            "enemy_tank_up_1": (16, 0),
            "enemy_tank_up_2": (18, 0),
            "enemy_tank_left_1": (20, 0),
            "enemy_tank_left_2": (22, 0),
            "enemy_tank_down_1": (24, 0),
            "enemy_tank_down_2": (26, 0),
            "enemy_tank_right_1": (28, 0),
            "enemy_tank_right_2": (30, 0),
        }

        # --- Add Tile Coordinates Here ---
        # Coordinates based on 8x8 grid
        tile_coords = {
            "brick": (32, 0),
            "steel": (32, 2),
            "bush": (34, 4),
            "ice": (36, 4),
            "base": (38, 4),
            "base_destroyed": (40, 4),
            "water_1": (32, 6),
            "water_2": (34, 6),
        }

        sprite_coords.update(tile_coords)
        # --- End Tile Coordinates ---

        for name, (x, y) in sprite_coords.items():
            src_x = x * SOURCE_TILE_SIZE
            src_y = y * SOURCE_TILE_SIZE

            # Determine the source dimensions based on sprite name
            if "tank" in name or name in ["base", "base_destroyed", "steel", "bush", "ice", "brick", "water_1", "water_2"]:
                src_width = SOURCE_TILE_SIZE * 2  # 32 pixels
                src_height = SOURCE_TILE_SIZE * 2  # 32 pixels
            else:
                # Handle 8x8 sprites by tiling
                src_width = SOURCE_TILE_SIZE
                src_height = SOURCE_TILE_SIZE
                logger.info(f"Tiling 8x8 sprite '{name}'")

            rect = pygame.Rect(src_x, src_y, src_width, src_height)

            try:
                original_sprite = self.texture_atlas.subsurface(rect)

                # Always scale the extracted sprite to TILE_SIZE
                scaled_sprite = pygame.transform.scale(
                    original_sprite, (TILE_SIZE, TILE_SIZE)
                )

                self.sprites[name] = scaled_sprite
            except ValueError as e:
                logger.error(
                    f"Error loading sprite '{name}' with rect {rect}: {e}. "
                    f"Check coordinates and atlas dimensions."
                )
                # Consider raising the error or returning a default sprite
                raise ValueError(f"Failed to load sprite '{name}'") from e

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
