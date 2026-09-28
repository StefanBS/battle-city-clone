"""Integration tests for 2-player co-op mode.

Tests the full pipeline: GameManager -> Map -> PlayerManager -> PlayerTank.
Unit-level behavior (freeze, scoring, life steal, game over) is covered
in the respective unit test files.
"""

import pytest
import pygame
from src.battle.outcomes import EnemyDestroyed
from src.states.game_mode import GameMode
from src.utils.constants import ENEMY_POINTS, FPS, TankType
from tests.integration.conftest import (
    score_of,
    spawn_enemy_at,
    start_game,
    reach_next_stage,
)


@pytest.fixture
def two_player_game():
    """GameManager in 2P mode with game running."""
    pygame.init()
    return start_game(GameMode.TWO_PLAYERS)


class TestTwoPlayerSetup:
    def test_two_players_created(self, two_player_game):
        """2P mode creates two active player tanks."""
        players = two_player_game.battle.scene().players
        assert len(players) == 2

    def test_players_have_different_ids(self, two_player_game):
        """P1 and P2 have player_id 1 and 2."""
        players = two_player_game.battle.scene().players
        assert players[0].player_id == 1
        assert players[1].player_id == 2

    def test_players_at_different_positions(self, two_player_game):
        """P1 and P2 spawn at different positions."""
        players = two_player_game.battle.scene().players
        assert (players[0].x, players[0].y) != (players[1].x, players[1].y)

    def test_player_spawn_positions_match_map(self, two_player_game):
        """Players spawn at positions defined in the map."""
        gm = two_player_game
        p1 = gm.battle.scene().players[0]
        p2 = gm.battle.scene().players[1]
        ts = gm.battle.map.tile_size
        expected_p1 = (
            gm.battle.map.player_spawn[0] * ts,
            gm.battle.map.player_spawn[1] * ts,
        )
        assert (p1.x, p1.y) == expected_p1
        if gm.battle.map.player_spawn_2 is not None:
            expected_p2 = (
                gm.battle.map.player_spawn_2[0] * ts,
                gm.battle.map.player_spawn_2[1] * ts,
            )
            assert (p2.x, p2.y) == expected_p2


class TestTwoPlayerStageTransition:
    def test_both_players_preserved_across_stages(self, two_player_game):
        """Both players' lives and star levels are preserved across stages."""
        gm = two_player_game
        p1 = gm.battle.scene().players[0]
        p2 = gm.battle.scene().players[1]

        p1.restore_lives(5)
        p1.restore_star_level(2)
        p2.restore_lives(4)
        p2.restore_star_level(1)

        reach_next_stage(gm)

        p1, p2 = gm.battle.scene().players
        assert (p1.lives, p1.star_level) == (5, 2)
        assert (p2.lives, p2.star_level) == (4, 1)

    def test_player_out_of_lives_stays_out_in_the_next_stage(self, two_player_game):
        """A Player Eliminated at a Victory does not come back next Stage."""
        gm = two_player_game
        p2 = gm.battle.scene().players[1]
        enemy = spawn_enemy_at(gm, 0, 0)
        gm.battle.apply_outcomes([EnemyDestroyed(enemy, by=p2)])
        p2.eliminate()

        reach_next_stage(gm)

        assert [p.player_id for p in gm.battle.scene().players] == [1]
        assert score_of(gm, 2) == ENEMY_POINTS[TankType.BASIC]
        # P1 fights on, so the Battle goes on.
        assert gm.battle.step(1.0 / FPS) is None
