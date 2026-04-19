"""End-to-end tests for 1 Player + AI mode."""

import pygame
import pytest

from src.managers.ai_player_input import AIPlayerInput
from src.states.game_mode import GameMode
from src.states.game_state import GameState


@pytest.fixture
def ai_coop_game(game_manager_fixture):
    """Start the game in ONE_PLAYER_AI mode and run past stage-curtain animations."""
    gm = game_manager_fixture
    gm._start_game(GameMode.ONE_PLAYER_AI)
    while gm.state != GameState.RUNNING:
        pygame.event.clear()
        gm.update()
        if gm.state == GameState.EXIT:
            pytest.fail("Game exited before reaching RUNNING")
    return gm


class TestAICoopRuntime:
    def test_slot_2_has_ai_input(self, ai_coop_game):
        pm = ai_coop_game.player_manager
        assert len(pm.get_active_players()) == 2
        assert isinstance(pm._player_inputs[1], AIPlayerInput)

    def test_ai_tank_moves_from_spawn(self, ai_coop_game):
        pm = ai_coop_game.player_manager
        ai_tank = pm._players[1]
        spawn_x, spawn_y = ai_tank.x, ai_tank.y
        for _ in range(120):
            pygame.event.clear()
            ai_coop_game.update()
        assert (ai_tank.x, ai_tank.y) != (spawn_x, spawn_y)

    def test_ai_fires_a_bullet(self, ai_coop_game):
        pm = ai_coop_game.player_manager
        ai_tank = pm._players[1]
        ai_fired = False
        for _ in range(180):
            pygame.event.clear()
            ai_coop_game.update()
            if any(b.owner is ai_tank for b in pm.get_all_bullets()):
                ai_fired = True
                break
        assert ai_fired, "AI did not fire within 3 seconds"
