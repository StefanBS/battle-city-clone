import pytest
import pygame
from unittest.mock import MagicMock
from src.managers.effect_manager import EffectManager
from src.managers.texture_manager import TextureManager
from src.utils.constants import EffectType


@pytest.fixture
def mock_texture_manager():
    tm = MagicMock(spec=TextureManager)

    def get_sprite(name):
        return pygame.Surface((32, 32))

    tm.get_sprite.side_effect = get_sprite
    return tm


@pytest.fixture
def effect_manager(mock_texture_manager):
    return EffectManager(mock_texture_manager)


class TestEffectManager:
    def test_starts_empty(self, effect_manager):
        assert len(effect_manager.effects) == 0

    def test_spawn_small_explosion(self, effect_manager):
        effect_manager.spawn(EffectType.SMALL_EXPLOSION, 100.0, 200.0)
        assert len(effect_manager.effects) == 1
        effect = effect_manager.effects[0]
        assert effect.x == 100.0
        assert effect.y == 200.0
        assert effect.active is True
        assert len(effect.frames) == 3

    def test_small_explosion_frames_are_32x32(self, effect_manager):
        effect_manager.spawn(EffectType.SMALL_EXPLOSION, 0, 0)
        for frame in effect_manager.effects[0].frames:
            assert frame.get_size() == (32, 32)

    def test_spawn_large_explosion(self, effect_manager):
        effect_manager.spawn(EffectType.LARGE_EXPLOSION, 50.0, 75.0)
        assert len(effect_manager.effects) == 1
        effect = effect_manager.effects[0]
        assert len(effect.frames) == 5

    def test_large_explosion_last_two_frames_are_64x64(self, effect_manager):
        effect_manager.spawn(EffectType.LARGE_EXPLOSION, 0, 0)
        frames = effect_manager.effects[0].frames
        # First 3 frames are 32x32
        for f in frames[:3]:
            assert f.get_size() == (32, 32)
        # Last 2 frames are 64x64
        for f in frames[3:]:
            assert f.get_size() == (64, 64)

    def test_update_removes_inactive_effects(self, effect_manager):
        effect_manager.spawn(EffectType.SMALL_EXPLOSION, 0, 0)
        effect_manager.update(1.0)
        assert len(effect_manager.effects) == 0

    def test_update_keeps_active_effects(self, effect_manager):
        effect_manager.spawn(EffectType.SMALL_EXPLOSION, 0, 0)
        effect_manager.update(0.01)
        assert len(effect_manager.effects) == 1

    def test_multiple_effects(self, effect_manager):
        effect_manager.spawn(EffectType.SMALL_EXPLOSION, 0, 0)
        effect_manager.spawn(EffectType.LARGE_EXPLOSION, 50, 50)
        assert len(effect_manager.effects) == 2

    def test_draw_does_not_raise(self, effect_manager):
        surface = pygame.Surface((256, 256))
        effect_manager.spawn(EffectType.SMALL_EXPLOSION, 100, 100)
        effect_manager.draw(surface)

    def test_spawn_at_rect_centers_on_rect(self, effect_manager):
        rect = pygame.Rect(100, 200, 32, 32)
        effect_manager.spawn_at_rect(EffectType.SMALL_EXPLOSION, rect)
        assert len(effect_manager.effects) == 1
        effect = effect_manager.effects[0]
        assert effect.x == 116.0  # centerx of (100, 200, 32, 32)
        assert effect.y == 216.0  # centery
