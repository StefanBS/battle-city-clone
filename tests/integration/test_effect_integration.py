"""Integration tests for the explosion effect lifecycle.

Verifies the full flow: collision triggers effect spawn, effect
plays through frames over multiple updates, and is cleaned up.
"""

from src.core.tile import TileType
from src.utils.constants import EffectType, FPS
from tests.integration.conftest import first_player


class TestEffectLifecycle:
    """Test that explosions spawn, animate, and clean up through GameManager."""

    def test_bullet_tile_collision_spawns_and_expires_effect(
        self, game_manager_fixture
    ):
        """A bullet hitting a steel tile spawns an effect that expires."""
        gm = game_manager_fixture
        dt = 1.0 / FPS

        steel_tiles = gm.map.get_tiles_by_type([TileType.STEEL])
        if not steel_tiles:
            steel_tiles = gm.map.get_tiles_by_type([TileType.BRICK])
        assert steel_tiles, "Need at least one destructible/steel tile"
        target = steel_tiles[0]

        player = first_player(gm)
        player.x = float(target.rect.centerx)
        player.y = float(target.rect.bottom + 10)
        player.rect.topleft = (round(player.x), round(player.y))

        # Clear enemies so they don't interfere (e.g., shoot the player instead).
        gm.spawn_manager.enemy_tanks.clear()

        bullet = player.shoot()
        assert bullet is not None
        gm.bullets.append(bullet)

        effect_spawned = False
        for _ in range(30):
            gm.update()
            if gm.effect_manager.effects:
                effect_spawned = True
                break

        assert effect_spawned, (
            "Expected an explosion effect after bullet-tile collision"
        )
        assert len(gm.effect_manager.effects) >= 1

        for _ in range(60):
            gm.effect_manager.update(dt)
            if not gm.effect_manager.effects:
                break

        assert len(gm.effect_manager.effects) == 0, (
            "Effect should have expired after playing through all frames"
        )

    def test_effect_manager_reset_on_game_reset(self, game_manager_fixture):
        """Resetting the game creates a fresh EffectManager."""
        gm = game_manager_fixture

        gm.effect_manager.spawn(EffectType.SMALL_EXPLOSION, 100.0, 100.0)
        old_effect_manager = gm.effect_manager

        gm._reset_game()

        assert gm.effect_manager is not old_effect_manager
