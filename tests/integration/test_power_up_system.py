"""Integration tests for the power-up spawn system.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.utils.constants import (
    FPS,
    POWERUP_CARRIER_INDICES,
    POWERUP_COLLECT_POINTS,
    POWERUP_TIMEOUT,
)


def _flush_pending_spawns(game, max_ticks=120):
    """Tick effect updates until all pending spawn animations finish.

    This is needed because SpawnManager uses spawn animations (EffectManager),
    so tanks only appear in enemy_tanks once the animation completes.
    """
    dt = 1.0 / FPS
    sm = game.spawn_manager
    em = game.effect_manager
    for _ in range(max_ticks):
        if not sm._pending_spawns:
            break
        em.update(dt)
        still_pending = []
        for pending in sm._pending_spawns:
            if not pending.effect.active:
                sm._materialize_enemy(
                    pending.x, pending.y, pending.tank_type, pending.is_carrier
                )
            else:
                still_pending.append(pending)
        sm._pending_spawns = still_pending


class TestPowerUpIntegration:
    """Full-cycle integration tests for the power-up system."""

    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    def _spawn_enemies_until_carrier(self, game):
        """Spawn enemies until the first carrier appears, return the carrier.

        Clears existing enemy_tanks between each spawn attempt to ensure spawn
        points are not blocked on the small test map.
        """
        first_carrier_index = POWERUP_CARRIER_INDICES[0]
        max_attempts = (first_carrier_index + 1) * 5
        for _ in range(max_attempts):
            if game.spawn_manager.total_enemy_spawns > first_carrier_index:
                break
            # Clear active enemies so spawn points stay free
            game.spawn_manager.enemy_tanks = []
            game.spawn_manager._pending_spawns = []
            game.spawn_manager.spawn_enemy(game.player_tank, game.map)
            _flush_pending_spawns(game)

        carriers = [e for e in game.spawn_manager.enemy_tanks if e.is_carrier]
        return carriers[0] if carriers else None

    def test_carrier_enemy_exists(self, game):
        """The 4th spawned enemy should be a carrier."""
        carrier = self._spawn_enemies_until_carrier(game)
        assert carrier is not None
        assert carrier.is_carrier is True

    def test_destroying_carrier_spawns_power_up(self, game):
        """Killing a carrier enemy should spawn a power-up on the map."""
        carrier = self._spawn_enemies_until_carrier(game)
        assert carrier is not None

        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            game.player_tank, game.spawn_manager.enemy_tanks
        )

        assert game.power_up_manager.active_power_up is not None

    def test_power_up_timeout(self, game):
        """Power-up should disappear after timeout."""
        carrier = self._spawn_enemies_until_carrier(game)
        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            game.player_tank, game.spawn_manager.enemy_tanks
        )

        game.power_up_manager.update(POWERUP_TIMEOUT + 0.1)
        assert game.power_up_manager.active_power_up is None

    def test_only_one_power_up_at_a_time(self, game):
        """Second spawn attempt should not create a second power-up."""
        carrier = self._spawn_enemies_until_carrier(game)
        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            game.player_tank, game.spawn_manager.enemy_tanks
        )
        first_pu = game.power_up_manager.active_power_up

        game.power_up_manager.spawn_power_up(
            game.player_tank, game.spawn_manager.enemy_tanks
        )
        assert game.power_up_manager.active_power_up is first_pu
