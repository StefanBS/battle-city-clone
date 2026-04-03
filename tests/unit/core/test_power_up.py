import pytest
import pygame
from unittest.mock import MagicMock
from src.core.power_up import PowerUp
from src.utils.constants import (
    PowerUpType,
    POWERUP_BLINK_INTERVAL,
    POWERUP_TIMEOUT,
    TILE_SIZE,
)


class TestPowerUp:
    @pytest.fixture
    def power_up(self, mock_texture_manager):
        return PowerUp(100, 200, PowerUpType.HELMET, mock_texture_manager)

    def test_initial_state(self, power_up):
        assert power_up.x == 100
        assert power_up.y == 200
        assert power_up.power_up_type == PowerUpType.HELMET
        assert power_up.active is True
        assert power_up.width == TILE_SIZE
        assert power_up.height == TILE_SIZE

    def test_sprite_lookup(self, mock_texture_manager):
        PowerUp(0, 0, PowerUpType.STAR, mock_texture_manager)
        mock_texture_manager.get_sprite.assert_called_with("powerup_star")

    def test_blink_visibility_cycle(self, power_up):
        surface = MagicMock(spec=pygame.Surface)
        power_up.draw(surface)
        assert surface.blit.called

        power_up.update(POWERUP_BLINK_INTERVAL + 0.01)
        surface.reset_mock()
        power_up.draw(surface)
        assert not surface.blit.called

        power_up.update(POWERUP_BLINK_INTERVAL)
        surface.reset_mock()
        power_up.draw(surface)
        assert surface.blit.called

    def test_timeout_deactivates(self, power_up):
        power_up.update(POWERUP_TIMEOUT + 0.1)
        assert power_up.active is False

    def test_no_deactivation_before_timeout(self, power_up):
        power_up.update(POWERUP_TIMEOUT - 1.0)
        assert power_up.active is True

    def test_collect_returns_type_and_deactivates(self, power_up):
        result = power_up.collect()
        assert result == PowerUpType.HELMET
        assert power_up.active is False

    @pytest.mark.parametrize("ptype", list(PowerUpType))
    def test_collect_each_type(self, mock_texture_manager, ptype):
        pu = PowerUp(0, 0, ptype, mock_texture_manager)
        assert pu.collect() == ptype

    def test_update_noop_after_collect(self, power_up):
        power_up.collect()
        timer_before = power_up.blink_timer
        timeout_before = power_up.timeout_timer
        power_up.update(1.0)
        assert power_up.blink_timer == timer_before
        assert power_up.timeout_timer == timeout_before

    def test_draw_skips_when_inactive(self, power_up):
        power_up.collect()
        surface = MagicMock(spec=pygame.Surface)
        power_up.draw(surface)
        assert not surface.blit.called

    def test_rect_position(self, power_up):
        assert power_up.rect.x == 100
        assert power_up.rect.y == 200
        assert power_up.rect.width == TILE_SIZE
        assert power_up.rect.height == TILE_SIZE
