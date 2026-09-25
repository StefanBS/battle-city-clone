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
from src.utils.constants import (
    CPU_PARTNER_AMBUSH_DISTANCE,
    FPS,
    SUB_TILE_SIZE,
    TILE_SIZE,
    Direction,
    OwnerType,
    PowerUpType,
)
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
    keep = {(t.x, t.y) for t in game.battle.map.get_tiles_by_type([TileType.BASE])}
    keep |= {(t.x, t.y) for t in game.battle.map.get_base_surrounding_tiles()}
    clear_tiles(
        game.battle.map,
        [
            (x, y)
            for y in range(game.battle.map.height)
            for x in range(game.battle.map.width)
            if (x, y) not in keep
        ],
    )


class TestCpuPartnerSetup:
    def test_cpu_partner_spawns_at_p2_spawn_point(self, cpu_game):
        gm = cpu_game
        p2 = gm.battle.player_manager.get_active_players()[1]
        assert gm.battle.map.player_spawn_2 is not None
        assert (p2.x, p2.y) == gm.battle.map.grid_to_pixels(
            *gm.battle.map.player_spawn_2
        )

    def test_keyboard_drives_p1_only(self, cpu_game, key_down_event):
        gm = cpu_game
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        # No spawn points to Ambush at: the CPU Partner has nothing to do.
        gm.battle.map.spawn_points = []
        p1, p2 = gm.battle.player_manager.get_active_players()
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

        view = gm.battle.world_view().for_player(2)

        assert view.own_player is not None
        assert view.own_player.player_id == 2
        assert [(e.x, e.y, e.direction) for e in view.enemies] == [
            (4 * SUB_TILE_SIZE, 6 * SUB_TILE_SIZE, Direction.LEFT)
        ]
        assert [(b.x, b.y) for b in view.bullets] == [(bullet.x, bullet.y)]
        assert view.enemy_spawn_points == tuple(gm.battle.map.spawn_points)
        base = gm.battle.map.get_base()
        assert (base.x, base.y) in view.base_cells
        wall = gm.battle.map.get_base_surrounding_tiles()[0]
        assert (wall.x, wall.y) in view.base_wall_cells
        assert view.tiles[wall.y][wall.x] is wall.type

    def test_carries_each_tiles_rules(self, cpu_game):
        gm = cpu_game
        placed = [t for row in gm.battle.map.tiles for t in row if t is not None]

        view = gm.battle.world_view()

        assert view.tank_blocking_cells == {
            (t.x, t.y) for t in placed if t.blocks_tanks
        }
        assert view.bullet_blocking_cells == {
            (t.x, t.y) for t in placed if t.blocks_bullets
        }
        assert view.destructible_cells == {
            (t.x, t.y) for t in placed if t.is_destructible
        }
        steel = gm.battle.map.get_tiles_by_type([TileType.STEEL])[0]
        assert (steel.x, steel.y) in view.bullet_blocking_cells
        assert (steel.x, steel.y) not in view.destructible_cells

    def test_reports_tank_and_bullet_speeds(self, cpu_game):
        gm = cpu_game
        enemy = spawn_enemy_at(gm, 4, 6)
        p2 = gm.battle.player_manager.get_active_players()[1]

        view = gm.battle.world_view().for_player(2)

        assert view.enemies[0].speed == enemy.speed
        assert view.own_player.speed == p2.speed
        assert view.own_player.bullet_speed == p2.bullet_speed

    def test_reports_each_bullets_speed_and_identity(self, cpu_game):
        gm = cpu_game
        enemy = spawn_enemy_at(gm, 4, 6)
        bullet = fire_bullet_from(gm, enemy)

        first = gm.battle.world_view().bullets
        bullet.update(1.0 / FPS)
        later = gm.battle.world_view().bullets

        assert [b.speed for b in first] == [enemy.bullet_speed]
        assert [b.bullet_id for b in later] == [b.bullet_id for b in first]
        other = fire_bullet_from(gm, gm.battle.player_manager.get_active_players()[0])
        ids = {b.bullet_id for b in gm.battle.world_view().bullets}
        assert len(ids) == 2 and other.active

    def test_reports_whether_a_player_is_shielded(self, cpu_game):
        gm = cpu_game
        p1, p2 = gm.battle.player_manager.get_active_players()
        p1.is_invincible = False
        p2.activate_invincibility(5.0)

        view = gm.battle.world_view()

        assert [p.shielded for p in view.players] == [False, True]

    def test_reports_whether_a_player_is_at_its_bullet_cap(self, cpu_game):
        gm = cpu_game
        p1, p2 = gm.battle.player_manager.get_active_players()
        fire_bullet_from(gm, p2)

        view = gm.battle.world_view()

        assert [p.can_fire for p in view.players] == [True, False]

    def test_reports_half_bricks(self, cpu_game):
        gm = cpu_game
        brick = gm.battle.map.get_tiles_by_type([TileType.BRICK])[0]
        gm.battle.map.damage_brick(brick, Direction.UP, brick.rect)

        view = gm.battle.world_view()

        assert (brick.x, brick.y) in view.half_brick_cells
        assert view.tiles[brick.y][brick.x] is TileType.BRICK

    def test_is_a_snapshot_not_live_objects(self, cpu_game):
        gm = cpu_game
        enemy = spawn_enemy_at(gm, 4, 6)
        view = gm.battle.world_view()

        enemy.set_position(100, 100)
        p2 = gm.battle.player_manager.get_active_players()[1]
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
        gm.battle.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 0, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 4, 6, fires=False)
        enemy.speed = 0

        for _ in range(10 * FPS):
            tick(gm)
            if enemy not in gm.battle.enemy_manager.enemies:
                break

        assert enemy not in gm.battle.enemy_manager.enemies
        assert gm.battle.player_manager.get_score(2) > 0
        assert gm.battle.player_manager.get_score(1) == 0

    def test_still_hunts_after_stage_change(self, cpu_game):
        gm = cpu_game
        gm._on_victory_finished()
        gm.state = GameState.RUNNING
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 0, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 16, 4, fires=False)
        enemy.speed = 0

        tick(gm, 3 * FPS)

        assert enemy not in gm.battle.enemy_manager.enemies


def set_tiles(game_map, positions, tile_type) -> None:
    """Turn the tiles at the given sub-tile grid positions into ``tile_type``."""
    for gx, gy in positions:
        game_map.set_tile_type(game_map.get_tile_at(gx, gy), tile_type)


class TestCpuPartnerPathfinding:
    def test_kills_enemy_walled_in_by_steel_and_brick(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        # The Enemy sits in the top-left corner, walled in by steel below
        # and by brick on its right. Lining up from below leads nowhere.
        set_tiles(
            gm.battle.map, [(x, y) for x in range(10) for y in (8, 9)], TileType.STEEL
        )
        set_tiles(
            gm.battle.map, [(x, y) for x in (8, 9) for y in range(8)], TileType.BRICK
        )
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 24 * SUB_TILE_SIZE, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 4, 4, fires=False)
        enemy.speed = 0

        for _ in range(15 * FPS):
            tick(gm)
            if enemy not in gm.battle.enemy_manager.enemies:
                break

        assert enemy not in gm.battle.enemy_manager.enemies
        assert gm.battle.player_manager.get_score(2) > 0


class TestCpuPartnerGivesWay:
    def test_routes_around_human_sitting_in_a_corridor(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        # A steel wall across rows 12-13 with a near gap at columns 4-5 and
        # a far one at columns 20-21. The Human Player sits in the near gap.
        gaps = (4, 5, 20, 21)
        set_tiles(
            gm.battle.map,
            [
                (x, y)
                for x in range(gm.battle.map.width)
                for y in (12, 13)
                if x not in gaps
            ],
            TileType.STEEL,
        )
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 4 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE, player=p1)
        place_player_at(gm, 4 * SUB_TILE_SIZE, 20 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 12, 2, fires=False)
        enemy.speed = 0

        for _ in range(15 * FPS):
            tick(gm)
            if enemy not in gm.battle.enemy_manager.enemies:
                break

        assert enemy not in gm.battle.enemy_manager.enemies
        assert gm.battle.player_manager.get_score(2) > 0
        assert (p1.x, p1.y) == (4 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE)


class TestCpuPartnerFiringPosition:
    def test_kills_enemy_it_can_only_shoot_across_water(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        # A moat of water two sub-tiles wide rings the Enemy: no tank can
        # reach it, but a bullet flies straight across.
        moat = [
            (x, y)
            for x in range(2, 8)
            for y in range(2, 8)
            if not (4 <= x <= 5 and 4 <= y <= 5)
        ]
        set_tiles(gm.battle.map, moat, TileType.WATER)
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 24 * SUB_TILE_SIZE, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        enemy = spawn_enemy_at(gm, 4, 4, fires=False)
        enemy.speed = 0

        for _ in range(10 * FPS):
            tick(gm)
            if enemy not in gm.battle.enemy_manager.enemies:
                break

        assert enemy not in gm.battle.enemy_manager.enemies
        assert gm.battle.player_manager.get_score(2) > 0


class TestCpuPartnerDefend:
    def test_intercepts_a_base_threat_before_hunting(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 0, 0, player=p1)
        place_player_at(gm, 20 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        # One Enemy lined up straight above the CPU Partner, far from the
        # Base; the other a few sub-tiles from the Base, off to its left.
        far = spawn_enemy_at(gm, 20, 6, fires=False)
        threat = spawn_enemy_at(gm, 6, 20, replace=False, fires=False)
        for enemy in (far, threat):
            enemy.speed = 0

        for _ in range(10 * FPS):
            tick(gm)
            if threat not in gm.battle.enemy_manager.enemies:
                break

        assert threat not in gm.battle.enemy_manager.enemies
        assert far in gm.battle.enemy_manager.enemies
        assert gm.battle.player_manager.get_score(2) > 0


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
    def test_steps_out_of_the_way_of_an_enemy_shot(self, cpu_game, seeded_rng):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        # No Enemy Spawn Point to Ambush at: it stands still until the shot.
        gm.battle.map.spawn_points = []
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 0, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 10 * SUB_TILE_SIZE, player=p2)
        p2.is_invincible = False
        # An Enemy far off to its left fires along its row, then is gone.
        enemy = spawn_enemy_at(gm, 2, 10, direction=Direction.RIGHT, fires=False)
        bullet = fire_bullet_from(gm, enemy)
        clear_enemies(gm)
        lives = p2.lives
        seeded_rng(NOTICES_THE_SHOT_SEED)

        for _ in range(3 * FPS):
            tick(gm)
            if not bullet.active:
                break

        assert not bullet.active
        assert p2.lives == lives
        assert (p2.x, p2.y) != (16 * SUB_TILE_SIZE, 10 * SUB_TILE_SIZE)

    def test_survives_a_shot_from_an_enemy_it_is_not_lined_up_with(
        self, cpu_game, seeded_rng
    ):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        gm.battle.map.spawn_points = []
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 0, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 10 * SUB_TILE_SIZE, player=p2)
        p2.direction = Direction.LEFT
        p2.is_invincible = False
        # A still Enemy a few px below its row fires at it: the shot's lane
        # misses its own bullet's, so it sidesteps, then must not line up
        # with the Enemy again while the shot flies past.
        enemy = spawn_enemy_at(gm, 8, 10, direction=Direction.RIGHT, fires=False)
        enemy.speed = 0
        place_player_at(gm, enemy.x, enemy.y + 6, player=enemy)
        bullet = fire_bullet_from(gm, enemy)
        lives = p2.lives
        seeded_rng(NOTICES_THE_SHOT_SEED)

        for _ in range(3 * FPS):
            tick(gm)
            if not bullet.active:
                break

        assert not bullet.active
        assert p2.lives == lives


class TestCpuPartnerGrabPowerUp:
    def test_collects_a_nearby_power_up_before_hunting(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 0, 0, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)
        # An Enemy lined up straight above the CPU Partner, far from the
        # Base, and a Power-Up a few sub-tiles off to its right.
        enemy = spawn_enemy_at(gm, 16, 4, fires=False)
        enemy.speed = 0
        gm.battle.power_up_manager.spawn_power_up(
            power_up_type=PowerUpType.STAR,
            position=gm.battle.map.grid_to_pixels(22, 16),
        )

        for _ in range(5 * FPS):
            tick(gm)
            if not gm.battle.power_up_manager.active_power_ups:
                break

        assert not gm.battle.power_up_manager.active_power_ups
        assert p2.star_level == 1
        assert p1.star_level == 0
        assert enemy in gm.battle.enemy_manager.enemies


def fire_enemy_bullet_at(gm, player) -> None:
    """Fire an Enemy bullet straight down onto an unprotected `player`."""
    player.is_invincible = False
    gx, gy = int(player.x // SUB_TILE_SIZE), int(player.y // SUB_TILE_SIZE)
    enemy = spawn_enemy_at(gm, gx, gy - 4, direction=Direction.DOWN, fires=False)
    enemy.speed = 0
    fire_bullet_from(gm, enemy)


class TestCpuPartnerGameOver:
    @pytest.fixture
    def arena(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 4 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE, player=p1)
        place_player_at(gm, 20 * SUB_TILE_SIZE, 12 * SUB_TILE_SIZE, player=p2)
        return gm

    def test_game_over_when_human_eliminated_and_cpu_partner_not(self, arena):
        gm = arena
        p1, p2 = gm.battle.player_manager.get_active_players()
        p1.restore_lives(1)
        p2.restore_lives(3)
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
        p2 = cpu_game.battle.player_manager.get_active_players()[1]
        p2.eliminate()
        labels = self.hud_labels(cpu_game)
        assert "CPU: OUT" in labels
        assert not any(label.startswith("P2") for label in labels)


class TestCpuPartnerHoldFireSoak:
    SOAK_SECONDS = 90

    def test_player_bullets_never_hit_base_or_base_wall(self, seeded_cpu_game):
        gm = seeded_cpu_game
        p1 = gm.battle.player_manager.get_active_players()[0]
        protected = {
            (t.x, t.y) for t in gm.battle.map.get_tiles_by_type([TileType.BASE])
        }
        protected |= {
            (t.x, t.y)
            for t in gm.battle.map.get_base_surrounding_tiles(include_empty=True)
        }

        # Record every Player bullet that hits a protected tile, then let the
        # real handler respond as usual.
        forbidden_hits: list[tuple[int, int]] = []
        handlers = gm.battle.collision_response_handler._handlers
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
            if p1.lives < 2:
                p1.gain_life()
            tick(gm)
            if gm.state is not GameState.RUNNING:
                break

        assert forbidden_hits == []
        assert gm.battle.player_manager.get_score(2) > 0


class TestCpuPartnerAmbush:
    def test_waits_covering_a_spawn_point_without_blocking_spawns(self, cpu_game):
        gm = cpu_game
        open_field(gm)
        clear_enemies(gm)
        gm.battle.spawn_manager.spawn_interval = float("inf")
        p1, p2 = gm.battle.player_manager.get_active_players()
        place_player_at(gm, 0, 24 * SUB_TILE_SIZE, player=p1)
        place_player_at(gm, 16 * SUB_TILE_SIZE, 16 * SUB_TILE_SIZE, player=p2)

        tick(gm, 5 * FPS)
        settled = (p2.x, p2.y)
        tick(gm, FPS)

        assert (p2.x, p2.y) == settled
        cx, cy = round(p2.x / SUB_TILE_SIZE), round(p2.y / SUB_TILE_SIZE)
        covered = [
            (sx, sy)
            for sx, sy in gm.battle.map.spawn_points
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
        for sx, sy in gm.battle.map.spawn_points:
            rect = pygame.Rect(
                *gm.battle.map.grid_to_pixels(sx, sy), TILE_SIZE, TILE_SIZE
            )
            assert not gm.battle.spawn_manager._is_spawn_blocked(
                rect,
                [
                    *gm.battle.player_manager.get_active_players(),
                    *gm.battle.enemy_manager.enemies,
                ],
                gm.battle.map,
            )
