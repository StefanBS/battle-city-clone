import os
import pytest
import pygame
from src.managers.game_manager import GameManager
from src.utils.constants import FPS, POWERUP_CARRIER_INDICES

# Use a virtual framebuffer so integration tests don't open real windows.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
# Disable audio to prevent hangs on CI runners without audio devices.
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Initialize pygame at import time so tests that construct GameManager
# directly (without the fixture) still have a working pygame subsystem.
pygame.init()


@pytest.fixture
def game_manager_fixture():
    """Fixture to provide a standard GameManager instance for integration tests."""
    pygame.init()
    manager = GameManager()
    # Start the game (skip title screen)
    manager._reset_game()
    return manager


def first_player(game):
    """Return the first active player tank, assuming one exists.

    Most integration tests are single-player and just want \"the\" player;
    this centralises the get_active_players()[0] lookup.
    """
    return game.player_manager.get_active_players()[0]


def flush_pending_spawns(game, max_ticks=120):
    """Tick effect updates until all pending spawn animations finish.

    This is needed because SpawnManager uses spawn animations (EffectManager),
    so tanks only appear in enemy_tanks once the animation completes.

    NOTE: Accesses SpawnManager private internals (_pending_spawns,
    _materialize_enemy) because the public API (update) also advances the
    spawn timer and may trigger additional spawns. If SpawnManager internals
    change, this helper must be updated accordingly.
    """
    dt = 1.0 / FPS
    sm = game.spawn_manager
    em = game.effect_manager
    for _ in range(max_ticks):
        if not sm._pending_spawns:
            break
        em.update(dt)
        still_pending = []
        for pending in sm._pending_spawns:
            if not pending.effect.active:
                sm._materialize_enemy(
                    pending.x, pending.y, pending.tank_type, pending.is_carrier
                )
            else:
                still_pending.append(pending)
        sm._pending_spawns = still_pending


def spawn_carrier(game):
    """Spawn enemies until a carrier appears, return the carrier.

    Clears active enemies between spawn attempts to avoid blocking
    the small test map's spawn points.
    """
    first_carrier_index = POWERUP_CARRIER_INDICES[0]
    max_attempts = (first_carrier_index + 1) * 5
    for _ in range(max_attempts):
        if game.spawn_manager.total_enemy_spawns > first_carrier_index:
            break
        game.spawn_manager.enemy_tanks = []
        game.spawn_manager._pending_spawns = []
        game.spawn_manager.spawn_enemy(
            game.player_manager.get_active_players(), game.map
        )
        flush_pending_spawns(game)
    carriers = [e for e in game.spawn_manager.enemy_tanks if e.is_carrier]
    assert carriers, "No carrier found"
    return carriers[0]
