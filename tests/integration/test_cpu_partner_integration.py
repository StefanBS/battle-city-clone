"""Integration tests for the CPU Partner in "1 Player + CPU" mode.

A real Battle, map and tanks; the only setup is clearing tiles and placing
tanks to build a small scenario. Going on to the next Stage and the HUD run
through the whole game.
"""

import dataclasses
import random

import pytest
import pygame

from src.core.tile import TileType
from src.world_view.footprint import Footprint, blocks_spawn_point
from src.states.game_mode import GameMode
from src.states.battle_result import BattleResult
from src.utils.constants import (
    CPU_PARTNER_AMBUSH_DISTANCE,
    FPS,
    SUB_TILE_SIZE,
    Direction,
    OwnerType,
    PowerUpType,
)
from tests.integration.conftest import (
    clear_enemies,
    clear_tiles,
    fire_bullet_from,
    make_battle,
    place_player_at,
    spawn_enemy_at,
    start_game,
    tick,
    score_of,
    reach_next_stage,
)


@pytest.fixture
def cpu_battle():
    """The first Battle of a 1 Player + CPU game, about to step."""
    return make_battle(GameMode.ONE_PLAYER_CPU)


@pytest.fixture(params=[1, 7, 42, 1234])
def seeded_cpu_battle(request):
    """A CPU Battle built under a fixed random seed; restores the RNG after."""
    state = random.getstate()
    random.seed(request.param)
    yield make_battle(GameMode.ONE_PLAYER_CPU)
    random.setstate(state)


@pytest.fixture
def cpu_game():
    """A GameManager in 1 Player + CPU mode with the first Battle about to step."""
    pygame.init()
    return start_game(GameMode.ONE_PLAYER_CPU)


def open_field(battle) -> None:
    """Clear every tile except the Base and the Base Wall."""
    keep = {(t.x, t.y) for t in battle.map.get_tiles_by_type([TileType.BASE])}
    keep |= {(t.x, t.y) for t in battle.map.get_base_surrounding_tiles()}
    clear_tiles(
        battle.map,
        [
            (x, y)
            for y in range(battle.map.height)
            for x in range(battle.map.width)
            if (x, y) not in keep
        ],
    )


class TestCpuPartnerSetup:
    def test_cpu_partner_spawns_at_p2_spawn_point(self, cpu_battle):
        battle = cpu_battle
        p2 = battle.scene().players[1]
        assert battle.map.player_spawn_2 is not None
        assert (p2.x, p2.y) == battle.map.grid_to_pixels(*battle.map.player_spawn_2)

    def test_keyboard_drives_p1_only(self, cpu_battle, key_down_event):
        battle = cpu_battle
        clear_enemies(battle)
        # No spawn points to Ambush at: the CPU Partner has nothing to do.
        battle.map.spawn_points = []
        p1, p2 = battle.scene().players
        p2_start = (p2.x, p2.y)

        battle.handle_event(key_down_event(pygame.K_LEFT))
        tick(battle, 10)

        assert p1.direction == Direction.LEFT
        assert (p2.x, p2.y) == p2_start


class TestWorldView:
    def test_reflects_the_battlefield(self, cpu_battle):
        battle = cpu_battle
        enemy = spawn_enemy_at(battle, 4, 6, direction=Direction.LEFT)
        bullet = fire_bullet_from(battle, enemy)

        view = battle.world_view().for_player(2)

        assert view.own_player is not None
        assert view.own_player.player_id == 2
        assert [(e.x, e.y, e.direction) for e in view.enemies] == [
            (4 * SUB_TILE_SIZE, 6 * SUB_TILE_SIZE, Direction.LEFT)
        ]
        assert [(b.x, b.y) for b in view.bullets] == [(bullet.x, bullet.y)]
        assert view.enemy_spawn_points == tuple(battle.map.spawn_points)
        base = battle.map.get_base()
        assert (base.x, base.y) in view.base_cells
        wall = battle.map.get_base_surrounding_tiles()[0]
        assert (wall.x, wall.y) in view.base_wall_cells
        assert view.tiles[wall.y][wall.x] is wall.type

    def test_carries_each_tiles_rules(self, cpu_battle):
        battle = cpu_battle
        placed = [t for row in battle.map.tiles for t in row if t is not None]

        view = battle.world_view()

        assert view.tank_blocking_cells == {
            (t.x, t.y) for t in placed if t.blocks_tanks
        }
        assert view.bullet_blocking_cells == {
            (t.x, t.y) for t in placed if t.blocks_bullets
        }
        assert view.destructible_cells == {
            (t.x, t.y) for t in placed if t.is_destructible
        }
        steel = battle.map.get_tiles_by_type([TileType.STEEL])[0]
        assert (steel.x, steel.y) in view.bullet_blocking_cells
        assert (steel.x, steel.y) not in view.destructible_cells

    def test_reports_tank_and_bullet_speeds(self, cpu_battle):
        battle = cpu_battle
        enemy = spawn_enemy_at(battle, 4, 6)
        p2 = battle.scene().players[1]

        view = battle.world_view().for_player(2)

        assert view.enemies[0].speed == enemy.speed
        assert view.own_player.speed == p2.speed
        assert view.own_player.bullet_speed == p2.bullet_speed

    def test_reports_each_bullets_speed_and_identity(self, cpu_battle):
        battle = cpu_battle
        enemy = spawn_enemy_at(battle, 4, 6)
        bullet = fire_bullet_from(battle, enemy)

        first = battle.world_view().bullets
        bullet.update(1.0 / FPS)
        later = battle.world_view().bullets

        assert [b.speed for b in first] == [enemy.bullet_speed]
        assert [b.bullet_id for b in later] == [b.bullet_id for b in first]
        other = fire_bullet_from(battle, battle.scene().players[0])
        ids = {b.bullet_id for b in battle.world_view().bullets}
        assert len(ids) == 2 and other.active

    def test_reports_whether_a_player_is_shielded(self, cpu_battle):
        battle = cpu_battle
        p1, p2 = battle.scene().players
        p1.is_invincible = False
        p2.activate_invincibility(5.0)

        view = battle.world_view()

        assert [p.shielded for p in view.players] == [False, True]

    def test_reports_whether_a_player_is_at_its_bullet_cap(self, cpu_battle):
        battle = cpu_battle
        p1, p2 = battle.scene().players
        fire_bullet_from(battle, p2)

        view = battle.world_view()

        assert [p.can_fire for p in view.players] == [True, False]

    def test_reports_half_bricks(self, cpu_battle):
        battle = cpu_battle
        brick = battle.map.get_tiles_by_type([TileType.BRICK])[0]
        battle.map.damage_brick(brick, Direction.UP, brick.rect)

        view = battle.world_view()

        assert (brick.x, brick.y) in view.half_brick_cells
        assert view.tiles[brick.y][brick.x] is TileType.BRICK

    def test_is_a_snapshot_not_live_objects(self, cpu_battle):
        battle = cpu_battle
        enemy = spawn_enemy_at(battle, 4, 6)
        view = battle.world_view()

        enemy.set_position(100, 100)
        p2 = battle.scene().players[1]
        p2.set_position(0, 0)

        assert (view.enemies[0].x, view.enemies[0].y) == (
            4 * SUB_TILE_SIZE,
            6 * SUB_TILE_SIZE,
        )
        assert (view.players[1].x, view.players[1].y) != (0, 0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            view.enemies[0].x = 0  # type: ignore[misc]


class TestCpuPartnerHunt:
    def test_kills_lone_stationary_enemy_in_open_space(self, cpu_battle):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        p1, p2 = battle.scene().players
        place_player_at(battle, 0, 0, player=p1)
        place_player_at(battle, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(battle, 4, 6, fires=False)
        enemy.speed = 0

        for _ in range(10 * FPS):
            tick(battle)
            if enemy not in battle.scene().enemies:
                break

        assert enemy not in battle.scene().enemies
        assert score_of(battle, 2) > 0
        assert score_of(battle, 1) == 0

    def test_still_hunts_after_stage_change(self, cpu_game):
        gm = cpu_game
        reach_next_stage(gm)
        assert gm.flow.stage == 2
        battle = gm.battle
        open_field(battle)
        clear_enemies(battle)
        p1, p2 = battle.scene().players
        place_player_at(battle, 0, 0, player=p1)
        place_player_at(battle, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(battle, 16, 4, fires=False)
        enemy.speed = 0

        tick(battle, 3 * FPS)

        assert enemy not in battle.scene().enemies


def set_tiles(game_map, positions, tile_type) -> None:
    """Turn the tiles at the given sub-tile grid positions into ``tile_type``."""
    for gx, gy in positions:
        game_map.set_tile_type(game_map.get_tile_at(gx, gy), tile_type)


class TestCpuPartnerPathfinding:
    def test_kills_enemy_walled_in_by_steel_and_brick(self, cpu_battle):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        # The Enemy sits in the top-left corner, walled in by steel below
        # and by brick on its right. Lining up from below leads nowhere.
        set_tiles(
            battle.map, [(x, y) for x in range(10) for y in (8, 9)], TileType.STEEL
        )
        set_tiles(
            battle.map, [(x, y) for x in (8, 9) for y in range(8)], TileType.BRICK
        )
        p1, p2 = battle.scene().players
        place_player_at(battle, 24 * SUB_TILE_SIZE, 0, player=p1)
        place_player_at(battle, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(battle, 4, 4, fires=False)
        enemy.speed = 0

        for _ in range(15 * FPS):
            tick(battle)
            if enemy not in battle.scene().enemies:
                break

        assert enemy not in battle.scene().enemies
        assert score_of(battle, 2) > 0


class TestCpuPartnerGivesWay:
    def test_routes_around_human_sitting_in_a_corridor(self, cpu_battle):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        # A steel wall across rows 12-13 with a near gap at columns 4-5 and
        # a far one at columns 20-21. The Human Player sits in the near gap.
        gaps = (4, 5, 20, 21)
        set_tiles(
            battle.map,
            [
                (x, y)
                for x in range(battle.map.width)
                for y in (12, 13)
                if x not in gaps
            ],
            TileType.STEEL,
        )
        p1, p2 = battle.scene().players
        place_player_at(battle, 4 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE, player=p1)
        place_player_at(battle, 4 * SUB_TILE_SIZE, 20 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(battle, 12, 2, fires=False)
        enemy.speed = 0

        for _ in range(15 * FPS):
            tick(battle)
            if enemy not in battle.scene().enemies:
                break

        assert enemy not in battle.scene().enemies
        assert score_of(battle, 2) > 0
        assert (p1.x, p1.y) == (4 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE)


class TestCpuPartnerFiringPosition:
    def test_kills_enemy_it_can_only_shoot_across_water(self, cpu_battle):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        # A moat of water two sub-tiles wide rings the Enemy: no tank can
        # reach it, but a bullet flies straight across.
        moat = [
            (x, y)
            for x in range(2, 8)
            for y in range(2, 8)
            if not (4 <= x <= 5 and 4 <= y <= 5)
        ]
        set_tiles(battle.map, moat, TileType.WATER)
        p1, p2 = battle.scene().players
        place_player_at(battle, 24 * SUB_TILE_SIZE, 0, player=p1)
        place_player_at(battle, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(battle, 4, 4, fires=False)
        enemy.speed = 0

        for _ in range(10 * FPS):
            tick(battle)
            if enemy not in battle.scene().enemies:
                break

        assert enemy not in battle.scene().enemies
        assert score_of(battle, 2) > 0


class TestCpuPartnerDefend:
    def test_intercepts_a_base_threat_before_hunting(self, cpu_battle):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        p1, p2 = battle.scene().players
        place_player_at(battle, 0, 0, player=p1)
        place_player_at(battle, 20 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        # One Enemy lined up straight above the CPU Partner, far from the
        # Base; the other a few sub-tiles from the Base, off to its left.
        far = spawn_enemy_at(battle, 20, 6, fires=False)
        threat = spawn_enemy_at(battle, 6, 20, replace=False, fires=False)
        for enemy in (far, threat):
            enemy.speed = 0

        for _ in range(10 * FPS):
            tick(battle)
            if threat not in battle.scene().enemies:
                break

        assert threat not in battle.scene().enemies
        assert far in battle.scene().enemies
        assert score_of(battle, 2) > 0


# The first roll under this seed is above the Dodge miss chance, and noticing
# the shot is the only thing that rolls during the test: it doesn't miss it.
NOTICES_THE_SHOT_SEED = 0


@pytest.fixture
def seeded_rng():
    """Lets a test seed the RNG; restores its state after."""
    state = random.getstate()
    yield random.seed
    random.setstate(state)


class TestCpuPartnerDodge:
    def test_steps_out_of_the_way_of_an_enemy_shot(self, cpu_battle, seeded_rng):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        # No Enemy Spawn Point to Ambush at: it stands still until the shot.
        battle.map.spawn_points = []
        p1, p2 = battle.scene().players
        place_player_at(battle, 0, 0, player=p1)
        place_player_at(battle, 16 * SUB_TILE_SIZE, 10 * SUB_TILE_SIZE, player=p2)
        p2.is_invincible = False
        # An Enemy far off to its left fires along its row, then is gone.
        enemy = spawn_enemy_at(battle, 2, 10, direction=Direction.RIGHT, fires=False)
        bullet = fire_bullet_from(battle, enemy)
        clear_enemies(battle)
        lives = p2.lives
        seeded_rng(NOTICES_THE_SHOT_SEED)

        for _ in range(3 * FPS):
            tick(battle)
            if not bullet.active:
                break

        assert not bullet.active
        assert p2.lives == lives
        assert (p2.x, p2.y) != (16 * SUB_TILE_SIZE, 10 * SUB_TILE_SIZE)

    def test_survives_a_shot_from_an_enemy_it_is_not_lined_up_with(
        self, cpu_battle, seeded_rng
    ):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        battle.map.spawn_points = []
        p1, p2 = battle.scene().players
        place_player_at(battle, 0, 0, player=p1)
        place_player_at(battle, 16 * SUB_TILE_SIZE, 10 * SUB_TILE_SIZE, player=p2)
        p2.direction = Direction.LEFT
        p2.is_invincible = False
        # A still Enemy a few px below its row fires at it: the shot's lane
        # misses its own bullet's, so it sidesteps, then must not line up
        # with the Enemy again while the shot flies past.
        enemy = spawn_enemy_at(battle, 8, 10, direction=Direction.RIGHT, fires=False)
        enemy.speed = 0
        place_player_at(battle, enemy.x, enemy.y + 6, player=enemy)
        bullet = fire_bullet_from(battle, enemy)
        lives = p2.lives
        seeded_rng(NOTICES_THE_SHOT_SEED)

        for _ in range(3 * FPS):
            tick(battle)
            if not bullet.active:
                break

        assert not bullet.active
        assert p2.lives == lives


class TestCpuPartnerGrabPowerUp:
    def test_collects_a_nearby_power_up_before_hunting(self, cpu_battle):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        p1, p2 = battle.scene().players
        place_player_at(battle, 0, 0, player=p1)
        place_player_at(battle, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        # An Enemy lined up straight above the CPU Partner, far from the
        # Base, and a Power-Up a few sub-tiles off to its right.
        enemy = spawn_enemy_at(battle, 16, 4, fires=False)
        enemy.speed = 0
        battle.drop_power_up(
            PowerUpType.STAR, position=battle.map.grid_to_pixels(22, 16)
        )

        for _ in range(5 * FPS):
            tick(battle)
            if not battle.scene().power_ups:
                break

        assert not battle.scene().power_ups
        assert p2.star_level == 1
        assert p1.star_level == 0
        assert enemy in battle.scene().enemies


def fire_enemy_bullet_at(battle, player) -> None:
    """Fire an Enemy bullet straight down onto an unprotected `player`."""
    player.is_invincible = False
    gx, gy = int(player.x // SUB_TILE_SIZE), int(player.y // SUB_TILE_SIZE)
    enemy = spawn_enemy_at(battle, gx, gy - 4, direction=Direction.DOWN, fires=False)
    enemy.speed = 0
    fire_bullet_from(battle, enemy)


class TestCpuPartnerGameOver:
    @pytest.fixture
    def arena(self, cpu_battle):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        p1, p2 = battle.scene().players
        place_player_at(battle, 4 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE, player=p1)
        place_player_at(battle, 20 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE, player=p2)
        return battle

    def test_game_over_when_human_eliminated_and_cpu_partner_not(self, arena):
        battle = arena
        p1, p2 = battle.scene().players
        p1.restore_lives(1)
        p2.restore_lives(3)
        fire_enemy_bullet_at(battle, p1)

        tick(battle, FPS)

        assert p1.lives == 0
        assert p2.lives == 3
        assert battle.result is BattleResult.GAME_OVER


class TestCpuPartnerHud:
    @staticmethod
    def hud_labels(gm) -> set[str]:
        gm.renderer._text_cache.clear()
        gm.render()
        return {text for _, text, _ in gm.renderer._text_cache}

    def test_shows_cpu_out_once_eliminated(self, cpu_game):
        p2 = cpu_game.battle.scene().players[1]
        p2.eliminate()
        labels = self.hud_labels(cpu_game)
        assert "CPU: OUT" in labels
        assert not any(label.startswith("P2") for label in labels)


def player_bullets_on(battle, cells) -> list[tuple[int, int]]:
    """The ``cells`` a Player bullet on the battlefield overlaps, as ``(x, y)``.

    Bullets stopped this frame are still on the battlefield until the next.
    """
    tiles = [battle.map.get_tile_at(x, y) for x, y in cells]
    return [
        (tile.x, tile.y)
        for bullet in battle.scene().bullets
        if bullet.owner_type is OwnerType.PLAYER
        for tile in tiles
        if tile is not None and bullet.rect.colliderect(tile.rect)
    ]


class TestCpuPartnerHoldFireSoak:
    SOAK_SECONDS = 90

    def test_player_bullets_never_hit_base_or_base_wall(self, seeded_cpu_battle):
        battle = seeded_cpu_battle
        game_map = battle.map
        p1 = battle.scene().players[0]
        protected = {(t.x, t.y) for t in game_map.get_tiles_by_type([TileType.BASE])}
        protected |= {
            (t.x, t.y) for t in game_map.get_base_surrounding_tiles(include_empty=True)
        }

        hits: list[tuple[int, int]] = []
        for _ in range(self.SOAK_SECONDS * FPS):
            # Keep the idle Human Player in the game so the soak runs its full
            # length; only the CPU Partner acts.
            if p1.lives < 2:
                p1.gain_life()
            # Only a tile that blocked bullets going into the frame can stop one.
            blocking = [
                (x, y)
                for x, y in protected
                if game_map.get_tile_at(x, y).blocks_bullets
            ]
            tick(battle)
            hits += player_bullets_on(battle, blocking)
            if battle.result is not None:
                break

        assert hits == []
        assert score_of(battle, 2) > 0


class TestCpuPartnerAmbush:
    def test_waits_covering_a_spawn_point_without_blocking_spawns(self, cpu_battle):
        battle = cpu_battle
        open_field(battle)
        clear_enemies(battle)
        p1, p2 = battle.scene().players
        place_player_at(battle, 0, 24 * SUB_TILE_SIZE, player=p1)
        place_player_at(battle, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)

        tick(battle, 5 * FPS)
        settled = (p2.x, p2.y)
        tick(battle, FPS)

        assert (p2.x, p2.y) == settled
        cx, cy = round(p2.x / SUB_TILE_SIZE), round(p2.y / SUB_TILE_SIZE)
        covered = [
            (sx, sy)
            for sx, sy in battle.map.spawn_points
            if (sx == cx or sy == cy)
            and abs(sx - cx) + abs(sy - cy) >= CPU_PARTNER_AMBUSH_DISTANCE
        ]
        assert covered
        sx, sy = covered[0]
        facing = (
            (Direction.DOWN if sy > cy else Direction.UP)
            if sx == cx
            else (Direction.RIGHT if sx > cx else Direction.LEFT)
        )
        assert p2.direction == facing
        for spawn_point in battle.map.spawn_points:
            for player in battle.scene().players:
                footprint = Footprint(player.rect.x, player.rect.y, player.rect.width)
                assert not blocks_spawn_point(
                    footprint, spawn_point, battle.map.tile_size
                )
