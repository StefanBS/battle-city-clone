"""Smoke tests for GameManager, the pygame adapter around the Screen Flow."""

import pygame
import pytest

from src.managers.game_manager import GameManager, stage_map_path
from src.managers.outcomes import EnemyDestroyed
from src.states.game_mode import GameMode
from src.managers.player_input import AXIS_MAX
from src.states.screen import Screen
from src.utils.constants import ENEMY_POINTS, VICTORY_PAUSE_DURATION, TankType
from tests.integration.conftest import (
    first_player,
    run_until_screen,
    score_of,
    spawn_enemy_at,
    start_game,
    tick,
    tick_for,
    use_up_roster,
)


def post(*events):
    for event in events:
        pygame.event.post(event)


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def button(b):
    return pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=b, instance_id=0)


class TestStartingAGame:
    def test_starts_on_the_title_screen_without_a_battle(self):
        game = GameManager()

        assert game.flow.screen is Screen.TITLE_SCREEN
        assert game.battle is None

    @pytest.mark.parametrize(
        "mode, players", [(GameMode.ONE_PLAYER, 1), (GameMode.TWO_PLAYERS, 2)]
    )
    def test_choosing_a_mode_starts_its_battle_on_stage_1(self, mode, players):
        game = start_game(mode)

        assert game.flow.stage == 1
        assert game.battle is not None
        assert len(game.battle.scene().players) == players
        game.render()


class TestRender:
    def test_every_screen_draws(self, tmp_path, monkeypatch):
        # Leaving Options saves settings.json in the working directory.
        monkeypatch.chdir(tmp_path)
        game = start_game()
        game.render()
        post(key(pygame.K_ESCAPE))
        game.handle_events()
        game.render()
        post(key(pygame.K_DOWN), key(pygame.K_RETURN))
        game.handle_events()
        assert game.flow.screen is Screen.OPTIONS_MENU
        game.render()
        post(key(pygame.K_ESCAPE), key(pygame.K_DOWN), key(pygame.K_RETURN))
        game.handle_events()
        assert game.flow.screen is Screen.TITLE_SCREEN
        game.render()


class TestPause:
    def test_the_button_that_resumes_does_not_fire(self):
        game = start_game()
        post(key(pygame.K_ESCAPE))
        game.handle_events()
        assert game.flow.screen is Screen.PAUSED

        post(button(pygame.CONTROLLER_BUTTON_A))
        game.handle_events()
        assert game.flow.screen is Screen.RUNNING
        tick(game)

        assert not game.battle.scene().bullets

    def test_a_stick_held_while_pausing_moves_the_pause_cursor(self):
        game = start_game()
        stick_down = pygame.event.Event(
            pygame.CONTROLLERAXISMOTION,
            axis=pygame.CONTROLLER_AXIS_LEFTY,
            value=int(0.8 * AXIS_MAX),
            instance_id=0,
        )
        post(stick_down, key(pygame.K_ESCAPE))
        game.handle_events()
        assert game.flow.menu.selection == 0

        post(stick_down)
        game.handle_events()

        assert game.flow.menu.selection == 1

    def test_the_same_button_fires_while_running(self):
        game = start_game()

        post(button(pygame.CONTROLLER_BUTTON_A))
        game.handle_events()
        tick(game)

        assert len(game.battle.scene().bullets) == 1


class TestNextStage:
    def test_victory_starts_the_next_stage_with_progress_carried(self):
        game = start_game()
        player = first_player(game)
        player.restore_lives(5)
        player.apply_star()
        enemy = spawn_enemy_at(game, 0, 0)
        game.battle.apply_outcomes([EnemyDestroyed(enemy, by=player)])
        first_battle = game.battle

        use_up_roster(game)
        tick(game)
        assert game.flow.screen is Screen.VICTORY
        tick_for(game, VICTORY_PAUSE_DURATION + 0.1)
        run_until_screen(game, Screen.RUNNING)

        assert game.flow.stage == 2
        assert game.battle is not first_battle
        assert first_player(game).lives == 5
        assert first_player(game).star_level == 1
        assert score_of(game) == ENEMY_POINTS[TankType.BASIC]


class TestStageMapPath:
    def test_each_stage_has_its_own_map(self):
        assert stage_map_path(5).endswith("level_05.tmx")

    def test_a_stage_without_a_map_falls_back_to_level_01(self):
        assert stage_map_path(99).endswith("level_01.tmx")


class TestQuit:
    def test_closing_the_window_exits(self):
        game = start_game()

        post(pygame.event.Event(pygame.QUIT))
        game.handle_events()

        assert game.flow.screen is Screen.EXIT
