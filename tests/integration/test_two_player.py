"""Integration tests for 2-player co-op mode."""

import pytest
import pygame
from src.managers.game_manager import GameManager
from src.utils.constants import FPS


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
        expected_p1 = (gm.map.player_spawn[0] * ts, gm.map.player_spawn[1] * ts)
        assert (p1.x, p1.y) == expected_p1
        if gm.map.player_spawn_2 is not None:
            expected_p2 = (gm.map.player_spawn_2[0] * ts, gm.map.player_spawn_2[1] * ts)
            assert (p2.x, p2.y) == expected_p2


class TestTwoPlayerGameOver:
    def test_game_continues_when_one_player_dies(self, two_player_game):
        """Game doesn't end when only one player is eliminated."""
        gm = two_player_game
        p1 = gm.player_manager._players[0]

        p1.lives = 0
        p1.health = 0

        assert gm.player_manager.is_game_over() is False

    def test_game_over_when_both_eliminated(self, two_player_game):
        """Game ends when both players are eliminated."""
        gm = two_player_game
        p1 = gm.player_manager._players[0]
        p2 = gm.player_manager._players[1]

        p1.lives = 0
        p1.health = 0
        p2.lives = 0
        p2.health = 0

        assert gm.player_manager.is_game_over() is True


class TestTwoPlayerLifeSteal:
    def test_life_stolen_on_death(self, two_player_game):
        """When P1 dies with 0 lives and P2 has 2+, P2 gives a life."""
        gm = two_player_game
        p1 = gm.player_manager._players[0]
        p2 = gm.player_manager._players[1]

        p1.lives = 0
        p1.health = 0
        p2.lives = 3

        result = gm.player_manager.handle_player_death(p1)

        assert result is False
        assert p2.lives == 2
        assert p1.lives == 1


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


class TestTwoPlayerScoring:
    def test_per_player_scores_independent(self, two_player_game):
        """Scores are tracked independently per player."""
        gm = two_player_game
        gm.player_manager.add_score(100, player_id=1)
        gm.player_manager.add_score(200, player_id=2)

        assert gm.player_manager.get_score(1) == 100
        assert gm.player_manager.get_score(2) == 200
        assert gm.player_manager.score == 300


class TestTwoPlayerFreeze:
    def test_frozen_player_cannot_move(self, two_player_game):
        """A frozen player cannot move."""
        gm = two_player_game
        p1 = gm.player_manager._players[0]
        p1.is_invincible = False

        p1.freeze(2.0)
        old_x, old_y = p1.x, p1.y
        p1.move(1, 0, 0.016)
        assert p1.x == old_x
        assert p1.y == old_y

    def test_freeze_expires_after_updates(self, two_player_game):
        """Freeze expires after enough update ticks."""
        gm = two_player_game
        p1 = gm.player_manager._players[0]
        p1.freeze(1.0)
        assert p1.is_frozen is True

        # Advance enough time
        for _ in range(70):  # ~1.17s at 60fps
            p1.update(1.0 / FPS)

        assert p1.is_frozen is False
