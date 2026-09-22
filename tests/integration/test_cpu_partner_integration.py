"""Integration tests for the CPU Partner in "1 Player + CPU" mode.

Real GameManager, real map and tanks; the only setup is clearing tiles and
placing tanks to build a small scenario.
"""

import dataclasses

import pytest
import pygame

from src.core.tile import TileType
from src.managers.game_manager import GameManager
from src.states.game_mode import GameMode
from src.states.game_state import GameState
from src.utils.constants import FPS, SUB_TILE_SIZE, Direction
from tests.integration.conftest import (
    clear_enemies,
    clear_tiles,
    fire_bullet_from,
    place_player_at,
    send_event,
    spawn_enemy_at,
    tick,
)


@pytest.fixture
def cpu_game():
    """GameManager in 1 Player + CPU mode with the game running."""
    pygame.init()
    gm = GameManager()
    gm._game_mode = GameMode.ONE_PLAYER_CPU
    gm._reset_game()
    return gm


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
