import pygame
from loguru import logger
from src.utils.constants import (
    TILE_SIZE,
    SUB_TILE_SIZE,
    SOURCE_TILE_SIZE,
    BULLET_SIZE,
    ATLAS_BG_COLOR,
)


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
        self.sub_sprites: dict[str, pygame.Surface] = {}
        self._load_sprites()

    # Tile/tank sprites: 2x2 source tiles (16x16 pixels in the atlas).
    # Coordinates are grid positions in an 8x8-pixel grid.
    _SPRITE_COORDS: dict[str, tuple[int, int]] = {
        # Player tank
        "player_tank_up_1": (0, 0),
        "player_tank_up_2": (2, 0),
        "player_tank_left_1": (4, 0),
        "player_tank_left_2": (6, 0),
        "player_tank_down_1": (8, 0),
        "player_tank_down_2": (10, 0),
        "player_tank_right_1": (12, 0),
        "player_tank_right_2": (14, 0),
        # Enemy tank
        "enemy_tank_up_1": (16, 0),
        "enemy_tank_up_2": (18, 0),
        "enemy_tank_left_1": (20, 0),
        "enemy_tank_left_2": (22, 0),
        "enemy_tank_down_1": (24, 0),
        "enemy_tank_down_2": (26, 0),
        "enemy_tank_right_1": (28, 0),
        "enemy_tank_right_2": (30, 0),
        # Tiles
        "brick": (32, 0),
        "steel": (32, 2),
        "bush": (34, 4),
        "ice": (36, 4),
        "base": (38, 4),
        "base_destroyed": (40, 4),
        "water_1": (32, 6),
        "water_2": (34, 6),
        # Explosions (3 frames: small burst, medium burst, large burst)
        "explosion_1": (32, 16),
        "explosion_2": (34, 16),
        "explosion_3": (36, 16),
    }

    # Bullet sprites: pixel rects (x, y, w, h) in the atlas.
    # Content sits at the bottom of each 8x8 cell, so we extract
    # only the 4x4 region containing the actual bullet pixels.
    _BULLET_RECTS: dict[str, tuple[int, int, int, int]] = {
        "bullet_up": (323, 102, 3, 4),
        "bullet_left": (330, 102, 4, 3),
        "bullet_down": (339, 102, 3, 4),
        "bullet_right": (346, 102, 4, 3),
    }

    def _load_sprites(self):
        """Loads individual sprites from the texture atlas."""
        self._load_tile_sprites()
        self._load_bullet_sprites()

    def _load_bullet_sprites(self):
        """Load bullet sprites cropped to their content region.

        Applies colorkey transparency for the near-black (0,0,1) atlas
        background so bullets render correctly over the game scene.
        """
        for name, (px, py, pw, ph) in self._BULLET_RECTS.items():
            rect = pygame.Rect(px, py, pw, ph)
            try:
                original = self.texture_atlas.subsurface(rect)
                scaled = pygame.transform.scale(
                    original, (BULLET_SIZE, BULLET_SIZE)
                )
                # Apply colorkey for near-black atlas background
                copy = scaled.convert()
                copy.set_colorkey(ATLAS_BG_COLOR)
                result = pygame.Surface(
                    (BULLET_SIZE, BULLET_SIZE), pygame.SRCALPHA
                )
                result.blit(copy, (0, 0))
                self.sprites[name] = result
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not load bullet sprite '{name}': {e}")
                # Bullet sprites are optional — fallback to colored rect

    def _load_tile_sprites(self):
        """Loads 16x16 tile/tank sprites from the texture atlas."""
        sprite_size = SOURCE_TILE_SIZE * 2

        for name, (gx, gy) in self._SPRITE_COORDS.items():
            rect = pygame.Rect(
                gx * SOURCE_TILE_SIZE,
                gy * SOURCE_TILE_SIZE,
                sprite_size,
                sprite_size,
            )

            try:
                original_sprite = self.texture_atlas.subsurface(rect)

                # Always scale the extracted sprite to TILE_SIZE
                scaled_sprite = pygame.transform.scale(
                    original_sprite, (TILE_SIZE, TILE_SIZE)
                )

                self.sprites[name] = scaled_sprite

                # Also store at sub-tile size (native 16x16)
                if SUB_TILE_SIZE != TILE_SIZE:
                    sub_sprite = pygame.transform.scale(
                        original_sprite, (SUB_TILE_SIZE, SUB_TILE_SIZE)
                    )
                    self.sub_sprites[name] = sub_sprite
                else:
                    self.sub_sprites[name] = scaled_sprite
            except ValueError as e:
                logger.error(
                    f"Error loading sprite '{name}' with rect {rect}: {e}. "
                    f"Check coordinates and atlas dimensions."
                )
                # Consider raising the error or returning a default sprite
                raise ValueError(f"Failed to load sprite '{name}'") from e

    def get_sub_sprite(self, name: str) -> pygame.Surface:
        """Retrieve a sprite at sub-tile size (16x16).

        Args:
            name: The name identifier of the sprite.

        Returns:
            The corresponding Pygame Surface at sub-tile size.

        Raises:
            KeyError: If the sprite name is not found.
        """
        try:
            return self.sub_sprites[name]
        except KeyError:
            logger.error(f"Error: Sub-sprite '{name}' not found.")
            raise KeyError(f"Sub-sprite '{name}' not found.") from None

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
            raise KeyError(f"Sprite '{name}' not found.") from None
