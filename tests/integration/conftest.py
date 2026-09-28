import os
import pytest
import pygame
from src.core.enemy_ai import EnemyAI
from src.core.enemy_tank import EnemyTank
from src.core.tile import Tile, TileType
from src.shell.game_manager import GameManager
from src.states.game_mode import GameMode
from src.states.screen import Screen
from src.utils.constants import (
    Difficulty,
    FPS,
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


# The title menu's modes, top to bottom.
_TITLE_MODES = (GameMode.ONE_PLAYER, GameMode.TWO_PLAYERS, GameMode.ONE_PLAYER_CPU)


def run_until_screen(game, screen, max_frames=600):
    """Run whole frames until the Screen Flow shows `screen`."""
    for _ in range(max_frames):
        if game.flow.screen is screen:
            return
        game.handle_events()
        game.update()
    raise AssertionError(f"never reached {screen.name}; on {game.flow.screen.name}")


def start_game(mode=GameMode.ONE_PLAYER, **game_manager_kwargs):
    """Choose `mode` on the title screen and run until its first Battle steps.

    Extra keyword arguments go to ``GameManager`` (e.g. ``sound_manager=``).
    """
    game = GameManager(**game_manager_kwargs)
    pygame.event.clear()
    for _ in range(_TITLE_MODES.index(mode)):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    run_until_screen(game, Screen.RUNNING)
    return game


def reach_next_stage(game):
    """End the running Battle in Victory and run until the next Stage's Battle steps."""
    use_up_roster(game)
    tick(game)
    assert game.flow.screen is Screen.VICTORY
    run_until_screen(game, Screen.RUNNING)


@pytest.fixture
def game_manager_fixture():
    """A GameManager in 1 Player mode, with the first Battle about to step."""
    pygame.init()
    return start_game()


def first_player(game):
    """Return the first active player tank, assuming one exists.

    Most integration tests are single-player and just want \"the\" player;
    this centralises the get_active_players()[0] lookup.
    """
    return game.battle.scene().players[0]


def score_of(game, player_id=1):
    """A Player's score so far in the running Battle."""
    return game.battle.carried_progress[player_id].score


def total_score(game):
    """Every Player's score so far in the running Battle, added up."""
    return sum(p.score for p in game.battle.carried_progress.values())


def use_roster(game, composition, carrier_indices=(), spawn_interval=None):
    """Give the running Battle a fresh Roster, with nothing Spawning yet.

    An empty ``composition`` means no Enemy will come: the Roster counts as
    used up, so the Battle ends in Victory once the battlefield is clear.
    ``carrier_indices`` says which Enemies, by draw order, are Carriers. The
    next Enemy starts Spawning after ``spawn_interval`` (the map's by default).
    """
    game.battle.replace_roster(
        composition,
        carrier_indices=tuple(carrier_indices),
        spawn_interval=spawn_interval,
    )


def hold_roster(game, composition):
    """Give the running Battle a Roster none of whose Enemies ever come on their own.

    The Battle goes on, since the Roster is not used up; a test brings an
    Enemy in with ``start_spawning``.
    """
    use_roster(game, composition, spawn_interval=float("inf"))


def let_spawning_enemies_appear(game, max_ticks=120):
    """Step the Battle until every Spawning Enemy has Appeared.

    Real frames run, so tanks and bullets move too. Callers hold the Roster,
    so no new spawn starts meanwhile. The frame after the last animation ends
    brings its Enemy onto the battlefield.
    """
    dt = 1.0 / FPS
    battle = game.battle
    for _ in range(max_ticks):
        no_animation_left = not battle.scene().effects
        battle.step(dt)
        if no_animation_left:
            break


def spawn_carrier(game):
    """Bring a Carrier onto a battlefield with no other Enemy, and return it."""
    game.battle.clear_enemies()
    use_roster(game, {TankType.BASIC: 1}, carrier_indices=(0,))
    assert game.battle.start_spawning()
    let_spawning_enemies_appear(game)
    (carrier,) = game.battle.scene().enemies
    return carrier


def clear_tiles(game_map, positions):
    """Clear tiles at given sub-tile grid positions to EMPTY for test setup."""
    for gx, gy in positions:
        if 0 <= gx < game_map.width and 0 <= gy < game_map.height:
            tile = game_map.get_tile_at(gx, gy)
            if tile and tile.type != TileType.EMPTY:
                game_map.place_tile(gx, gy, Tile(TileType.EMPTY, gx, gy, SUB_TILE_SIZE))


def spawn_enemy_at(game, grid_x, grid_y, *args, **kwargs):
    """Spawn a single EnemyTank, paired with its EnemyAI, at a sub-tile grid position.

    Takes the same arguments as ``spawn_enemy_with_ai`` and returns the new
    EnemyTank so callers can tweak attributes (speed, shoot, etc.).
    """
    enemy, _ = spawn_enemy_with_ai(game, grid_x, grid_y, *args, **kwargs)
    return enemy


def spawn_enemy_with_ai(
    game,
    grid_x,
    grid_y,
    tank_type=TankType.BASIC,
    direction=None,
    replace=True,
    difficulty=Difficulty.NORMAL,
    fires=True,
    turns=True,
    **enemy_kwargs,
):
    """Spawn a single EnemyTank at a sub-tile grid position and return (enemy, ai).

    If replace=True (default), replaces any existing enemies with just this one.
    Otherwise, appends to the existing list. ``difficulty`` goes to the EnemyAI;
    ``fires=False`` makes it never shoot and ``turns=False`` makes it never turn
    on its own timer (it still turns away when blocked). Extra kwargs (e.g.
    is_carrier=...) are forwarded to EnemyTank.
    """
    map_w_px = game.battle.map.width * SUB_TILE_SIZE
    map_h_px = game.battle.map.height * SUB_TILE_SIZE
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
        game.battle.clear_enemies()
    base = game.battle.map.get_base()
    ai = EnemyAI(
        enemy,
        difficulty=difficulty,
        base_position=(
            (float(base.rect.centerx), float(base.rect.centery))
            if base is not None
            else None
        ),
        shoot_interval=None if fires else float("inf"),
        direction_change_interval=None if turns else float("inf"),
    )
    game.battle.add_enemy(enemy, ai)
    return enemy, ai


class _FireInPlace:
    """A TankIntent that stands still and fires."""

    def get_movement_direction(self):
        return (0, 0)

    def consume_shoot(self):
        return True


def fire_bullet_from(game, tank):
    """Step `tank` one frame in place with a shot queued; return its bullet.

    The shot respects the Bullet Cap, so at the cap this returns the bullet
    already in flight.
    """
    game.battle.step_tank(tank, _FireInPlace(), 1.0 / FPS)
    return next(b for b in game.battle.scene().bullets if b.owner is tank)


def place_ice_patch(game, grid_x, grid_y, width=4, height=4):
    """Place a patch of ice tiles at the given sub-tile grid position."""
    for dy in range(height):
        for dx in range(width):
            tile = game.battle.map.get_tile_at(grid_x + dx, grid_y + dy)
            if tile is not None:
                game.battle.map.set_tile_type(tile, TileType.ICE)


def place_player_at(game, x, y, player=None):
    """Place the (first) player at pixel coords, syncing prev_x/prev_y and rect."""
    p = player if player is not None else first_player(game)
    p.set_position(x, y)
    p.prev_x, p.prev_y = x, y
    p.rect.topleft = (round(x), round(y))


def clear_enemies(game):
    """Clear the battlefield of Enemies, with one still to come that never does."""
    game.battle.clear_enemies()
    hold_roster(game, {TankType.BASIC: 1})


def use_up_roster(game):
    """Clear the battlefield with no Enemy left to come: the Battle can be won."""
    game.battle.clear_enemies()
    use_roster(game, {})


def tick(game, n=1):
    """Run n update frames."""
    for _ in range(n):
        game.update()


def tick_for(game, seconds):
    """Run update frames totaling approximately `seconds` at FPS dt."""
    tick(game, int(seconds * FPS))


def send_event(game, event):
    """Dispatch an event to both the input handler and the Battle's Players."""
    game.input_handler.handle_event(event)
    game.battle.handle_event(event)
