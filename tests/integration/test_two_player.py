"""Integration tests for 2-player co-op mode.

Tests the full pipeline: GameManager -> Map -> PlayerManager -> PlayerTank.
Unit-level behavior (freeze, scoring, life steal, game over) is covered
in the respective unit test files.
"""

import pytest
import pygame
from src.managers.game_manager import GameManager


@pytest.fixture
def two_player_game():
    """GameManager in 2P mode with game running."""
    pygame.init()
    gm = GameManager()
    gm._two_player_mode = True
    gm._reset_game()
    return gm


class TestTwoPlayerSetup:
    def test_two_players_created(self, two_player_game):
        """2P mode creates two active player tanks."""
        players = two_player_game.player_manager.get_active_players()
        assert len(players) == 2

    def test_players_have_different_ids(self, two_player_game):
        """P1 and P2 have player_id 1 and 2."""
        players = two_player_game.player_manager._players
        assert players[0].player_id == 1
        assert players[1].player_id == 2

    def test_players_at_different_positions(self, two_player_game):
        """P1 and P2 spawn at different positions."""
        players = two_player_game.player_manager._players
        assert (players[0].x, players[0].y) != (players[1].x, players[1].y)

    def test_player_spawn_positions_match_map(self, two_player_game):
        """Players spawn at positions defined in the map."""
        gm = two_player_game
        p1 = gm.player_manager._players[0]
        p2 = gm.player_manager._players[1]
        ts = gm.map.tile_size
        expected_p1 = (
            gm.map.player_spawn[0] * ts,
            gm.map.player_spawn[1] * ts,
        )
        assert (p1.x, p1.y) == expected_p1
        if gm.map.player_spawn_2 is not None:
            expected_p2 = (
                gm.map.player_spawn_2[0] * ts,
                gm.map.player_spawn_2[1] * ts,
            )
            assert (p2.x, p2.y) == expected_p2


class TestTwoPlayerStageTransition:
    def test_both_players_preserved_across_stages(self, two_player_game):
        """Both players' lives and star levels are preserved across stages."""
        gm = two_player_game
        p1 = gm.player_manager._players[0]
        p2 = gm.player_manager._players[1]

        p1.lives = 5
        p1.restore_star_level(2)
        p2.lives = 4
        p2.restore_star_level(1)

        gm.player_manager.preserve_state()
        gm.player_manager.create_players(gm.map, two_player_mode=True)
        gm.player_manager.restore_state()

        assert gm.player_manager._players[0].lives == 5
        assert gm.player_manager._players[0].star_level == 2
        assert gm.player_manager._players[1].lives == 4
        assert gm.player_manager._players[1].star_level == 1
