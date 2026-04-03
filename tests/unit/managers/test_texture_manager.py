import pytest
import pygame
from unittest.mock import patch, MagicMock
from src.managers.texture_manager import TextureManager


class TestPowerUpSprites:
    """Test that power-up and red enemy tank sprites are loaded."""

    POWERUP_SPRITE_NAMES = [
        "powerup_helmet",
        "powerup_clock",
        "powerup_shovel",
        "powerup_star",
        "powerup_bomb",
        "powerup_extra_life",
        "powerup_gun",
    ]

    RED_TANK_SPRITE_NAMES = [
        "enemy_tank_red_up_1",
        "enemy_tank_red_up_2",
        "enemy_tank_red_left_1",
        "enemy_tank_red_left_2",
        "enemy_tank_red_down_1",
        "enemy_tank_red_down_2",
        "enemy_tank_red_right_1",
        "enemy_tank_red_right_2",
    ]

    @pytest.mark.parametrize("name", POWERUP_SPRITE_NAMES)
    def test_powerup_sprite_loaded(self, real_texture_manager, name):
        sprite = real_texture_manager.get_sprite(name)
        assert sprite is not None

    @pytest.mark.parametrize("name", RED_TANK_SPRITE_NAMES)
    def test_red_tank_sprite_loaded(self, real_texture_manager, name):
        sprite = real_texture_manager.get_sprite(name)
        assert sprite is not None


class TestPlayerTierSprites:
    TIER_SPRITE_NAMES = [
        f"player_tank_tier{tier}_{direction}_{frame}"
        for tier in [1, 2, 3]
        for direction in ["up", "down", "left", "right"]
        for frame in [1, 2]
    ]

    @pytest.mark.parametrize("name", TIER_SPRITE_NAMES)
    def test_tier_sprite_loaded(self, real_texture_manager, name):
        sprite = real_texture_manager.get_sprite(name)
        assert sprite is not None


class TestTextureManagerErrors:
    """Tests for TextureManager error handling paths."""

    def test_init_missing_atlas_raises_system_exit(self):
        """Test that missing atlas file raises SystemExit."""
        with patch("pygame.image.load", side_effect=pygame.error("file not found")):
            with pytest.raises(SystemExit, match="Error loading texture atlas"):
                TextureManager("nonexistent.png")

    def test_get_sprite_unknown_name_raises_key_error(self):
        """Test that unknown sprite name raises KeyError."""
        with patch("pygame.image.load") as mock_load:
            mock_atlas = MagicMock(spec=pygame.Surface)
            mock_load.return_value.convert_alpha.return_value = mock_atlas
            mock_subsurface = MagicMock(spec=pygame.Surface)
            mock_atlas.subsurface.return_value = mock_subsurface
            with patch("pygame.transform.scale", return_value=mock_subsurface):
                tm = TextureManager("fake.png")

        with pytest.raises(KeyError, match="not found"):
            tm.get_sprite("nonexistent_sprite")

    def test_load_sprites_invalid_rect_raises_value_error(self):
        """Test that invalid sprite rect raises ValueError."""
        with patch("pygame.image.load") as mock_load:
            mock_atlas = MagicMock(spec=pygame.Surface)
            mock_load.return_value.convert_alpha.return_value = mock_atlas
            mock_atlas.subsurface.side_effect = ValueError("invalid rect")

            with pytest.raises(ValueError, match="Failed to load sprite"):
                TextureManager("fake.png")
