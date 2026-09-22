"""Integration tests for the CPU Partner in "1 Player + CPU" mode.

Real GameManager, real map and tanks; the only setup is clearing tiles and
placing tanks to build a small scenario.
"""

import dataclasses
import random

import pytest
import pygame

from src.core.bullet import Bullet
from src.core.tile import Tile, TileType
from src.managers.game_manager import GameManager
from src.states.game_mode import GameMode
from src.states.game_state import GameState
from src.utils.constants import FPS, SUB_TILE_SIZE, Direction, OwnerType
from tests.integration.conftest import (
    clear_enemies,
    clear_tiles,
    fire_bullet_from,
    place_player_at,
    send_event,
    spawn_enemy_at,
    tick,
)


def start_cpu_game() -> GameManager:
    """Start a GameManager in 1 Player + CPU mode with the game running."""
    pygame.init()
    gm = GameManager()
    gm._game_mode = GameMode.ONE_PLAYER_CPU
    gm._reset_game()
    return gm


@pytest.fixture
def cpu_game():
    """GameManager in 1 Player + CPU mode with the game running."""
    return start_cpu_game()


@pytest.fixture(params=[1, 7, 42, 1234])
def seeded_cpu_game(request):
    """A CPU game started under a fixed random seed; restores the RNG after."""
    state = random.getstate()
    random.seed(request.param)
    yield start_cpu_game()
    random.setstate(state)


def open_field(game) -> None:
    """Clear every tile except the Base and the Base Wall."""
    keep = {(t.x, t.y) for t in game.map.get_tiles_by_type([TileType.BASE])}
    keep |= {(t.x, t.y) for t in game.map.get_base_surrounding_tiles()}
    clear_tiles(
        game.map,
        [
            (x, y)
            for y in range(game.map.height)
            for x in range(game.map.width)
            if (x, y) not in keep
        ],
    )


class TestCpuPartnerSetup:
    def test_cpu_partner_spawns_at_p2_spawn_point(self, cpu_game):
        gm = cpu_game
        p2 = gm.player_manager.get_active_players()[1]
        assert gm.map.player_spawn_2 is not None
        assert (p2.x, p2.y) == gm.map.grid_to_pixels(*gm.map.player_spawn_2)

    def test_keyboard_drives_p1_only(self, cpu_game, key_down_event):
        gm = cpu_game
        clear_enemies(gm)
        gm.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.player_manager.get_active_players()
        p2_start = (p2.x, p2.y)

        send_event(gm, key_down_event(pygame.K_LEFT))
        tick(gm, 10)

        assert p1.direction == Direction.LEFT
        assert (p2.x, p2.y) == p2_start


class TestWorldView:
    def test_reflects_the_battlefield(self, cpu_game):
        gm = cpu_game
        enemy = spawn_enemy_at(gm, 4, 6, direction=Direction.LEFT)
        bullet = fire_bullet_from(gm, enemy)

        view = gm._world_view().for_player(2)

        assert view.own_player is not None
        assert view.own_player.player_id == 2
        assert [(e.x, e.y, e.direction) for e in view.enemies] == [
            (4 * SUB_TILE_SIZE, 6 * SUB_TILE_SIZE, Direction.LEFT)
        ]
        assert [(b.x, b.y) for b in view.bullets] == [(bullet.x, bullet.y)]
        assert view.enemy_spawn_points == tuple(gm.map.spawn_points)
        base = gm.map.get_base()
        assert (base.x, base.y) in view.base_cells
        wall = gm.map.get_base_surrounding_tiles()[0]
        assert (wall.x, wall.y) in view.base_wall_cells
        assert view.tiles[wall.y][wall.x] is wall.type

    def test_reports_tank_and_bullet_speeds(self, cpu_game):
        gm = cpu_game
        enemy = spawn_enemy_at(gm, 4, 6)
        p2 = gm.player_manager.players[1]

        view = gm._world_view().for_player(2)

        assert view.enemies[0].speed == enemy.speed
        assert view.own_player.bullet_speed == p2.bullet_speed

    def test_reports_half_bricks(self, cpu_game):
        gm = cpu_game
        brick = gm.map.get_tiles_by_type([TileType.BRICK])[0]
        gm.map.damage_brick(brick, Direction.UP, brick.rect)

        view = gm._world_view()

        assert (brick.x, brick.y) in view.half_brick_cells
        assert view.tiles[brick.y][brick.x] is TileType.BRICK

    def test_is_a_snapshot_not_live_objects(self, cpu_game):
        gm = cpu_game
        enemy = spawn_enemy_at(gm, 4, 6)
        view = gm._world_view()

        enemy.set_position(100, 100)
        p2 = gm.player_manager.players[1]
        p2.set_position(0, 0)

        assert (view.enemies[0].x, view.enemies[0].y) == (
            4 * SUB_TILE_SIZE,
            6 * SUB_TILE_SIZE,
        )
        assert (view.players[1].x, view.players[1].y) != (0, 0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            view.enemies[0].x = 0  # type: ignore[misc]


class TestCpuPartnerHunt:
    def test_kills_lone_stationary_enemy_in_open_space(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.player_manager.get_active_players()
        place_player_at(gm, 0, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 4, 6)
        enemy.speed = 0
        enemy.shoot_interval = float("inf")

        for _ in range(10 * FPS):
            tick(gm)
            if enemy not in gm.spawn_manager.enemy_tanks:
                break

        assert enemy not in gm.spawn_manager.enemy_tanks
        assert gm.player_manager.get_score(2) > 0
        assert gm.player_manager.get_score(1) == 0

    def test_still_hunts_after_stage_change(self, cpu_game):
        gm = cpu_game
        gm._on_victory_finished()
        gm.state = GameState.RUNNING
        open_field(gm)
        clear_enemies(gm)
        gm.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.player_manager.get_active_players()
        place_player_at(gm, 0, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 16, 4)
        enemy.speed = 0
        enemy.shoot_interval = float("inf")

        tick(gm, 3 * FPS)

        assert enemy not in gm.spawn_manager.enemy_tanks


def set_tiles(game_map, positions, tile_type) -> None:
    """Turn the tiles at the given sub-tile grid positions into ``tile_type``."""
    for gx, gy in positions:
        game_map.set_tile_type(game_map.get_tile_at(gx, gy), tile_type)


class TestCpuPartnerPathfinding:
    def test_kills_enemy_walled_in_by_steel_and_brick(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.spawn_manager.spawn_interval = float("inf")
        # The Enemy sits in the top-left corner, walled in by steel below
        # and by brick on its right. Lining up from below leads nowhere.
        set_tiles(gm.map, [(x, y) for x in range(10) for y in (8, 9)], TileType.STEEL)
        set_tiles(gm.map, [(x, y) for x in (8, 9) for y in range(8)], TileType.BRICK)
        p1, p2 = gm.player_manager.get_active_players()
        place_player_at(gm, 24 * SUB_TILE_SIZE, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 4, 4)
        enemy.speed = 0
        enemy.shoot_interval = float("inf")

        for _ in range(15 * FPS):
            tick(gm)
            if enemy not in gm.spawn_manager.enemy_tanks:
                break

        assert enemy not in gm.spawn_manager.enemy_tanks
        assert gm.player_manager.get_score(2) > 0


class TestCpuPartnerFiringPosition:
    def test_kills_enemy_it_can_only_shoot_across_water(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.spawn_manager.spawn_interval = float("inf")
        # A moat of water two sub-tiles wide rings the Enemy: no tank can
        # reach it, but a bullet flies straight across.
        moat = [
            (x, y)
            for x in range(2, 8)
            for y in range(2, 8)
            if not (4 <= x <= 5 and 4 <= y <= 5)
        ]
        set_tiles(gm.map, moat, TileType.WATER)
        p1, p2 = gm.player_manager.get_active_players()
        place_player_at(gm, 24 * SUB_TILE_SIZE, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 4, 4)
        enemy.speed = 0
        enemy.shoot_interval = float("inf")

        for _ in range(10 * FPS):
            tick(gm)
            if enemy not in gm.spawn_manager.enemy_tanks:
                break

        assert enemy not in gm.spawn_manager.enemy_tanks
        assert gm.player_manager.get_score(2) > 0


def fire_enemy_bullet_at(gm, player) -> None:
    """Fire an Enemy bullet straight down onto an unprotected `player`."""
    player.is_invincible = False
    gx, gy = int(player.x // SUB_TILE_SIZE), int(player.y // SUB_TILE_SIZE)
    enemy = spawn_enemy_at(gm, gx, gy - 4, direction=Direction.DOWN)
    enemy.speed = 0
    enemy.shoot_interval = float("inf")
    fire_bullet_from(gm, enemy)


class TestCpuPartnerGameOver:
    @pytest.fixture
    def arena(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.player_manager.players
        place_player_at(gm, 4 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE, player=p1)
        place_player_at(gm, 20 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE, player=p2)
        return gm

    def test_game_over_when_human_out_and_cpu_partner_alive(self, arena):
        gm = arena
        p1, p2 = gm.player_manager.players
        p1.lives = 1
        p2.lives = 3
        fire_enemy_bullet_at(gm, p1)

        tick(gm, FPS)

        assert p1.lives == 0
        assert p2.lives == 3
        assert gm.state in (GameState.GAME_OVER, GameState.GAME_OVER_ANIMATION)


class TestCpuPartnerHud:
    @staticmethod
    def hud_labels(gm) -> set[str]:
        gm.renderer._text_cache.clear()
        gm.render()
        return {text for _, text, _ in gm.renderer._text_cache}

    def test_shows_cpu_out_once_eliminated(self, cpu_game):
        p2 = cpu_game.player_manager.players[1]
        p2.lives = 0
        p2.health = 0
        labels = self.hud_labels(cpu_game)
        assert "CPU: OUT" in labels
        assert not any(label.startswith("P2") for label in labels)


class TestCpuPartnerHoldFireSoak:
    SOAK_SECONDS = 90

    def test_player_bullets_never_hit_base_or_base_wall(self, seeded_cpu_game):
        gm = seeded_cpu_game
        p1 = gm.player_manager.players[0]
        protected = {(t.x, t.y) for t in gm.map.get_tiles_by_type([TileType.BASE])}
        protected |= {
            (t.x, t.y) for t in gm.map.get_base_surrounding_tiles(include_empty=True)
        }

        # Record every Player bullet that hits a protected tile, then let the
        # real handler respond as usual.
        forbidden_hits: list[tuple[int, int]] = []
        handlers = gm.collision_response_handler._handlers
        real_handler = handlers[(Bullet, Tile)]

        def recording_handler(bullet, tile, enemies_to_remove):
            if (
                bullet.owner_type is OwnerType.PLAYER
                and tile.blocks_bullets
                and (tile.x, tile.y) in protected
            ):
                forbidden_hits.append((tile.x, tile.y))
            return real_handler(bullet, tile, enemies_to_remove)

        handlers[(Bullet, Tile)] = recording_handler

        for _ in range(self.SOAK_SECONDS * FPS):
            # Keep the idle Human Player in the game so the soak runs its full
            # length; only the CPU Partner acts.
            p1.lives = max(p1.lives, 2)
            tick(gm)
            if gm.state is not GameState.RUNNING:
                break

        assert forbidden_hits == []
        assert gm.player_manager.get_score(2) > 0
