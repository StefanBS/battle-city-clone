import pytest
import pygame
from src.managers.game_manager import GameManager


class TestNewGameAndLoadStage:
    @pytest.fixture
    def game(self):
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.NOFRAME)
        gm = GameManager()
        gm._new_game()
        return gm

    def test_new_game_resets_stage_and_score(self, game):
        assert game.current_stage == 1
        assert game.score == 0

    def test_load_stage_preserves_score(self, game):
        game.score = 500
        game._load_stage()
        assert game.score == 500

    def test_load_stage_preserves_lives(self, game):
        game.player_tank.lives = 5
        game._load_stage()
        assert game.player_tank.lives == 5

    def test_load_stage_preserves_star_level(self, game):
        game.player_tank.apply_star()
        game.player_tank.apply_star()
        game._load_stage()
        assert game.player_tank.star_level == 2
