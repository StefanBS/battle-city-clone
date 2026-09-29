"""Integration tests for the explosion effect lifecycle.

Verifies the full flow: collision triggers effect spawn, effect
plays through frames over multiple updates, and is cleaned up.
"""

import pygame

from src.core.tile import TileType
from src.battle.outcomes import PlayerDestroyed
from src.states.screen import Screen
from src.utils.constants import FPS
from tests.integration.conftest import (
    clear_enemies,
    fire_bullet_from,
    first_player,
    run_until_screen,
    tick,
)


class TestEffectLifecycle:
    """Test that explosions spawn, animate, and clean up through the Battle."""

    def test_bullet_tile_collision_spawns_and_expires_effect(self, battle):
        """A bullet hitting a steel tile spawns an effect that expires."""
        dt = 1.0 / FPS

        steel_tiles = battle.map.get_tiles_by_type([TileType.STEEL])
        if not steel_tiles:
            steel_tiles = battle.map.get_tiles_by_type([TileType.BRICK])
        assert steel_tiles, "Need at least one destructible/steel tile"
        target = steel_tiles[0]

        player = first_player(battle)
        player.x = float(target.rect.centerx)
        player.y = float(target.rect.bottom + 10)
        player.rect.topleft = (round(player.x), round(player.y))

        # Clear enemies so they don't interfere (e.g., shoot the player instead).
        clear_enemies(battle)

        fire_bullet_from(battle, player)

        effect_spawned = False
        for _ in range(30):
            tick(battle)
            if battle.scene().effects:
                effect_spawned = True
                break

        assert effect_spawned, (
            "Expected an explosion effect after bullet-tile collision"
        )
        assert len(battle.scene().effects) >= 1

        for _ in range(60):
            battle.step(dt)
            if not battle.scene().effects:
                break

        assert len(battle.scene().effects) == 0, (
            "Effect should have expired after playing through all frames"
        )

    def test_effects_do_not_outlive_a_new_game(self, game_manager_fixture):
        """A new game leaves no effect from the game before behind."""
        gm = game_manager_fixture

        gm.battle.apply_outcomes([PlayerDestroyed(first_player(gm.battle))])
        assert len(gm.battle.scene().effects) == 2

        # Pause, choose Title Screen, then 1 Player.
        for key in (pygame.K_ESCAPE, pygame.K_DOWN, pygame.K_DOWN, pygame.K_RETURN):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        gm.handle_events()
        assert gm.flow.screen is Screen.TITLE_SCREEN
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        run_until_screen(gm, Screen.RUNNING)

        # Only the new Battle's first Enemy's spawn animation plays.
        assert len(gm.battle.scene().effects) == 1
