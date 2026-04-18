import os
import pytest
import pygame
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType
from src.managers.game_manager import GameManager
from src.utils.constants import (
    FPS,
    POWERUP_CARRIER_INDICES,
    SUB_TILE_SIZE,
    TILE_SIZE,
    TankType,
)

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
    max_attempts = first_carrier_index + 2
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


def clear_tiles(game_map, positions):
    """Clear tiles at given sub-tile grid positions to EMPTY for test setup."""
    for gx, gy in positions:
        if 0 <= gx < game_map.width and 0 <= gy < game_map.height:
            tile = game_map.get_tile_at(gx, gy)
            if tile and tile.type != TileType.EMPTY:
                game_map.place_tile(gx, gy, Tile(TileType.EMPTY, gx, gy, SUB_TILE_SIZE))


def spawn_enemy_at(
    game,
    grid_x,
    grid_y,
    tank_type=TankType.BASIC,
    direction=None,
    replace=True,
    **enemy_kwargs,
):
    """Spawn a single EnemyTank at the given sub-tile grid position.

    If replace=True (default), replaces any existing enemies with just this one.
    Otherwise, appends to the existing list. Extra kwargs (e.g. difficulty=...)
    are forwarded to EnemyTank. Returns the new EnemyTank so callers can tweak
    attributes (speed, shoot, etc.).
    """
    map_w_px = game.map.width * SUB_TILE_SIZE
    map_h_px = game.map.height * SUB_TILE_SIZE
    enemy = EnemyTank(
        grid_x * SUB_TILE_SIZE,
        grid_y * SUB_TILE_SIZE,
        TILE_SIZE,
        game.texture_manager,
        tank_type,
        map_width_px=map_w_px,
        map_height_px=map_h_px,
        **enemy_kwargs,
    )
    if direction is not None:
        enemy.direction = direction
    if replace:
        game.spawn_manager.enemy_tanks = [enemy]
    else:
        game.spawn_manager.enemy_tanks.append(enemy)
    return enemy


def fire_bullet_from(game, tank):
    """Fire a bullet from `tank` via GameManager._try_shoot and return it."""
    game._try_shoot(tank)
    return next(b for b in game.bullets if b.owner is tank)


def place_player_at(game, x, y, player=None):
    """Place the (first) player at pixel coords, syncing prev_x/prev_y and rect."""
    p = player if player is not None else first_player(game)
    p.set_position(x, y)
    p.prev_x, p.prev_y = x, y
    p.rect.topleft = (round(x), round(y))


def clear_enemies(game, reset_total=True):
    """Reset enemy_tanks, _pending_spawns, and optionally total_enemy_spawns."""
    game.spawn_manager.enemy_tanks = []
    game.spawn_manager._pending_spawns = []
    if reset_total:
        game.spawn_manager.total_enemy_spawns = 0


def tick(game, n=1):
    """Run n update frames."""
    for _ in range(n):
        game.update()


def tick_for(game, seconds):
    """Run update frames totaling approximately `seconds` at FPS dt."""
    tick(game, int(seconds * FPS))


def send_event(game, event):
    """Dispatch an event to both the input handler and the player manager."""
    game.input_handler.handle_event(event)
    game.player_manager.handle_event(event)
