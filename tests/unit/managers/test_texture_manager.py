import json
import os

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


class TestSpriteConfigLoading:
    """Test that TextureManager loads sprite coords from JSON config."""

    def test_config_file_exists(self):
        assert os.path.exists("assets/config/sprites.json")

    def test_config_has_all_sprites(self):
        with open("assets/config/sprites.json") as f:
            config = json.load(f)
        assert len(config["sprites"]) >= 70
        assert "player_tank_up_1" in config["sprites"]
        assert "enemy_tank_up_1" in config["sprites"]

    def test_config_has_bullet_rects(self):
        with open("assets/config/sprites.json") as f:
            config = json.load(f)
        assert len(config["bullets"]) == 4
        assert "bullet_up" in config["bullets"]

    def test_config_sprite_grid_format(self):
        with open("assets/config/sprites.json") as f:
            config = json.load(f)
        for name, data in config["sprites"].items():
            assert "grid" in data, f"Sprite '{name}' missing 'grid' key"
            assert len(data["grid"]) == 2, f"Sprite '{name}' grid must have 2 values"

    def test_config_bullet_rect_format(self):
        with open("assets/config/sprites.json") as f:
            config = json.load(f)
        for name, data in config["bullets"].items():
            assert "rect" in data, f"Bullet '{name}' missing 'rect' key"
            assert len(data["rect"]) == 4, f"Bullet '{name}' rect must have 4 values"


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
