"""End-to-end tests for 1 Player + AI mode."""

import random

import pygame
import pytest

from src.core.enemy_tank import EnemyTank
from src.managers.ai_player_input import AIPlayerInput, AIRole
from src.states.game_mode import GameMode
from src.states.game_state import GameState
from src.utils.constants import SUB_TILE_SIZE

from tests.integration.conftest import clear_enemies, spawn_enemy_at


@pytest.fixture(autouse=True)
def seed_random():
    """Seed the global `random` module so stochastic AI picks are deterministic."""
    state = random.getstate()
    random.seed(42)
    yield
    random.setstate(state)


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
        human = pm._players[0]
        ai_tank = pm._players[1]
        # Move the human well off any axis shared with the AI so friendly-fire
        # suppression never stalls the shoot timer during the observation window.
        human.x = 4 * 32
        human.y = 0.0
        human.prev_x, human.prev_y = human.x, human.y
        human.rect.topleft = (int(human.x), int(human.y))

        ai_fired = False
        for _ in range(300):
            pygame.event.clear()
            ai_coop_game.update()
            if any(b.owner is ai_tank for b in pm.get_all_bullets()):
                ai_fired = True
                break
        assert ai_fired, "AI did not fire within 5 seconds"


class TestAICoopDefenderMode:
    def test_defender_role_triggers_when_enemy_near_base(
        self, ai_coop_game, monkeypatch
    ):
        """With an enemy parked 2 tiles from the base, the AI should pick
        DEFENDER on its next replan."""
        pm = ai_coop_game.player_manager
        ai_input = pm._player_inputs[1]

        # Park a single enemy 2 tiles (64px) from the base along x.
        assert EnemyTank.base_position is not None, (
            "Base position must be set by SpawnManager"
        )
        bx, by = EnemyTank.base_position
        clear_enemies(ai_coop_game)
        # Use sub-tile grid (8px units) — 2 TILE_SIZE = 8 sub-tiles.
        enemy_grid_x = int(bx / SUB_TILE_SIZE) + 8
        enemy_grid_y = int(by / SUB_TILE_SIZE)
        spawn_enemy_at(ai_coop_game, enemy_grid_x, enemy_grid_y)

        captured_roles: list[AIRole] = []
        original_select_role = ai_input._select_role

        def spy(enemies, base_position):
            role = original_select_role(enemies, base_position)
            captured_roles.append(role)
            return role

        monkeypatch.setattr(ai_input, "_select_role", spy)

        # Force a replan next frame.
        ai_input._direction_timer = ai_input._direction_change_interval

        for _ in range(5):
            pygame.event.clear()
            ai_coop_game.update()

        assert AIRole.DEFENDER in captured_roles, (
            f"Expected DEFENDER role when enemy is near base; captured={captured_roles}"
        )


class TestAICoopFriendlyFireSafety:
    def test_player_bullet_hitting_ai_does_not_crash(self, ai_coop_game):
        """Friendly fire on the AI tank must freeze it, not crash the AI."""
        pm = ai_coop_game.player_manager
        human = pm._players[0]
        ai_tank = pm._players[1]

        # Clear spawn invincibility so friendly-fire actually resolves.
        ai_tank.is_invincible = False
        ai_tank.invincibility_timer = 0.0
        ai_tank.invincibility_duration = 0.0

        # Fire a real player-owned bullet and reposition it on top of the AI
        # tank so the next collision tick resolves friendly-fire immediately.
        bullet = human.shoot()
        assert bullet is not None
        bullet.x = ai_tank.x
        bullet.y = ai_tank.y
        bullet.rect.topleft = (int(bullet.x), int(bullet.y))
        pm._bullets.append(bullet)

        # Step a few frames — must not raise, and the AI tank should freeze.
        for _ in range(10):
            pygame.event.clear()
            ai_coop_game.update()

        assert ai_tank.health > 0
        assert ai_tank.is_frozen
