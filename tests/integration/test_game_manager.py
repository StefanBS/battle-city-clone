"""Smoke tests for GameManager, the pygame adapter around the Screen Flow."""

import pygame

from src.shell.game_manager import stage_map_path
from src.battle.player_input import AXIS_MAX
from src.states.screen import Screen
from tests.integration.conftest import (
    first_player,
    run_frames,
    start_game,
    use_up_roster,
)


def post(*events):
    for event in events:
        pygame.event.post(event)


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def button(b):
    return pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=b, instance_id=0)


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
        run_frames(game)

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


class TestBattleEnd:
    def test_a_battle_won_shows_victory(self):
        game = start_game()
        use_up_roster(game.battle)

        run_frames(game)

        assert game.flow.screen is Screen.VICTORY

    def test_a_battle_lost_shows_the_game_over_animation(self):
        game = start_game()
        first_player(game.battle).eliminate()

        run_frames(game)

        assert game.flow.screen is Screen.GAME_OVER_ANIMATION


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
