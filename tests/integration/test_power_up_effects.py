"""Integration tests for power-up effects.

Uses real objects (no mocks) with SDL_VIDEODRIVER=dummy for headless execution.
"""

import pytest
from src.utils.constants import (
    FPS,
    HELMET_INVINCIBILITY_DURATION,
    POWERUP_CARRIER_INDICES,
    PowerUpType,
)


def _flush_pending_spawns(game, max_ticks=120):
    """Tick effect updates until all pending spawn animations finish.

    NOTE: Accesses SpawnManager private internals (_pending_spawns,
    _materialize_enemy) because the public API (update) also advances the
    spawn timer and may trigger additional spawns.
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


def _spawn_carrier(game):
    """Spawn enemies until a carrier appears."""
    first_carrier_index = POWERUP_CARRIER_INDICES[0]
    max_attempts = (first_carrier_index + 1) * 5
    for _ in range(max_attempts):
        if game.spawn_manager.total_enemy_spawns > first_carrier_index:
            break
        game.spawn_manager.enemy_tanks = []
        game.spawn_manager._pending_spawns = []
        game.spawn_manager.spawn_enemy(game.player_tank, game.map)
        _flush_pending_spawns(game)
    carriers = [e for e in game.spawn_manager.enemy_tanks if e.is_carrier]
    assert carriers, "No carrier found"
    return carriers[0]


class TestPowerUpEffectsIntegration:
    @pytest.fixture
    def game(self, game_manager_fixture):
        return game_manager_fixture

    def _collect_power_up(self, game, power_up_type):
        """Spawn a carrier, destroy it, spawn a specific power-up, collect it."""
        carrier = _spawn_carrier(game)
        carrier.health = 0
        game.spawn_manager.remove_enemy(carrier)
        game.power_up_manager.spawn_power_up(
            game.player_tank,
            game.spawn_manager.enemy_tanks,
            power_up_type=power_up_type,
        )
        assert game.power_up_manager.active_power_up is not None
        # Move player to power-up location to trigger collision
        pu = game.power_up_manager.active_power_up
        game.player_tank.set_position(pu.x, pu.y)
        game.player_tank.rect.topleft = (round(pu.x), round(pu.y))

    def test_helmet_effect(self, game):
        self._collect_power_up(game, PowerUpType.HELMET)
        game.update()
        assert game.player_tank.is_invincible is True
        assert game.player_tank.invincibility_duration == HELMET_INVINCIBILITY_DURATION

    def test_extra_life_effect(self, game):
        lives_before = game.player_tank.lives
        self._collect_power_up(game, PowerUpType.EXTRA_LIFE)
        game.update()
        assert game.player_tank.lives == lives_before + 1

    def test_bomb_effect(self, game):
        _flush_pending_spawns(game)
        enemies_before = len(game.spawn_manager.enemy_tanks)
        assert enemies_before > 0
        self._collect_power_up(game, PowerUpType.BOMB)
        game.update()
        assert len(game.spawn_manager.enemy_tanks) == 0
