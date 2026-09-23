"""Unit tests for PlayerManager."""

from __future__ import annotations

import pytest
import pygame
from unittest.mock import MagicMock

from src.core.map import Map
from src.core.player_tank import PlayerTank
from src.core.tile import TileType
from src.managers.player_input import (
    CombinedInput,
    ControllerInput,
    KeyboardInput,
)
from src.managers.cpu_partner import CpuPartnerInput
from src.managers.player_manager import PlayerKind, PlayerManager
from src.managers.sound_manager import SoundManager
from src.managers.tank_stepper import TankStepper
from src.managers.world_view import EnemyView, PlayerView, WorldView
from src.states.game_mode import GameMode
from src.utils.constants import CPU_PARTNER_REACTION_DELAY, FPS, TILE_SIZE, Direction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sound_manager():
    """Mock SoundManager."""
    return MagicMock(spec=SoundManager)


@pytest.fixture
def player_manager(mock_texture_manager, mock_sound_manager):
    """PlayerManager with mock dependencies."""
    return PlayerManager(mock_texture_manager, mock_sound_manager)


@pytest.fixture
def mock_game_map():
    """Mock Map with typical spawn / dimension attributes."""
    game_map = MagicMock(spec=Map)
    game_map.player_spawn = (4, 24)
    game_map.width = 26
    game_map.height = 26
    game_map.tile_size = TILE_SIZE
    game_map.grid_to_pixels.side_effect = lambda gx, gy: (
        gx * TILE_SIZE,
        gy * TILE_SIZE,
    )
    # Default: no ice tile under any tank
    game_map.get_tile_at.return_value = None
    game_map.is_tile_slidable.return_value = False
    return game_map


# ---------------------------------------------------------------------------
# TestPlayerManagerCreation
# ---------------------------------------------------------------------------


class TestPlayerManagerCreation:
    def test_initial_players_empty(self, player_manager):
        """No players exist before create_players() is called."""
        assert player_manager.get_active_players() == []

    def test_create_players_single_player(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """create_players() produces exactly one active player."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        players = player_manager.get_active_players()
        assert len(players) == 1
        assert isinstance(players[0], PlayerTank)

    def test_create_players_sets_correct_position(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Player tank is placed at the map's player_spawn coordinates."""
        mock_game_map.player_spawn = (3, 22)
        mock_game_map.tile_size = TILE_SIZE

        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager.get_active_players()[0]
        expected_x = 3 * TILE_SIZE
        expected_y = 22 * TILE_SIZE
        assert player.x == expected_x
        assert player.y == expected_y

    def test_create_players_1p_is_combined_input(
        self, player_manager, mock_game_map
    ) -> None:
        """1P always wraps keyboard + non-filtering controller in CombinedInput.

        Uses ControllerInput(instance_id=None) regardless of whether a
        controller is currently plugged in, so hot-plugging Just Works.
        """
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        pi = player_manager.slots[0].input
        assert isinstance(pi, CombinedInput)
        assert len(pi._inputs) == 2
        assert isinstance(pi._inputs[0], KeyboardInput)
        assert isinstance(pi._inputs[1], ControllerInput)
        assert pi._inputs[1].instance_id is None

    def test_create_players_1p_combined_ignores_instance_ids(
        self, player_manager, mock_game_map
    ) -> None:
        player_manager.create_players(mock_game_map, controller_instance_ids=[7])
        pi = player_manager.slots[0].input
        assert isinstance(pi, CombinedInput)
        assert pi._inputs[1].instance_id is None

    def test_1p_slot_is_a_human_player(self, player_manager, mock_game_map):
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        assert [slot.kind for slot in player_manager.slots] == [PlayerKind.HUMAN]

    def test_slot_holds_its_tank(self, player_manager, mock_game_map):
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        slot = player_manager.slots[0]
        assert slot.tank is player_manager.players[0]
        assert slot.player_id == 1

    def test_create_players_clears_previous_state(self, player_manager, mock_game_map):
        """Calling create_players() twice replaces the players and inputs."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        first = player_manager.players[0]
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        assert len(player_manager.players) == 1
        assert player_manager.players[0] is not first

    def test_get_active_players_returns_living(self, player_manager, mock_game_map):
        """get_active_players() filters out dead tanks."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.players[0].health = 0
        assert player_manager.get_active_players() == []


# ---------------------------------------------------------------------------
# TestPlayerManagerUpdate
# ---------------------------------------------------------------------------


def _press(pm: PlayerManager, key: int) -> None:
    pm.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


def _release(pm: PlayerManager, key: int) -> None:
    pm.handle_event(pygame.event.Event(pygame.KEYUP, key=key))


class TestPlayerManagerUpdate:
    DT = 1.0 / 60

    @pytest.fixture(autouse=True)
    def setup(self, player_manager, mock_game_map):
        """Create a single player and a stepper before each test in this class."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        self.pm = player_manager
        self.game_map = mock_game_map
        self.stepper = TankStepper(mock_game_map)
        self.player = player_manager.players[0]

    def test_steps_player_with_its_input(self):
        y_before = self.player.y
        _press(self.pm, pygame.K_UP)

        self.pm.update(self.DT, self.stepper)

        assert self.player.y < y_before

    def test_skips_dead_player(self):
        self.player.health = 0
        y_before = self.player.y
        _press(self.pm, pygame.K_UP)
        _press(self.pm, pygame.K_SPACE)

        self.pm.update(self.DT, self.stepper)

        assert self.player.y == y_before
        assert self.stepper.bullets == []

    def test_fired_bullet_goes_to_the_stepper_and_plays_shoot(self):
        _press(self.pm, pygame.K_SPACE)

        self.pm.update(self.DT, self.stepper)

        assert [b.owner for b in self.stepper.bullets] == [self.player]
        self.pm._sound_manager.play.assert_called_once_with("shoot")

    def test_slide_plays_ice_sound(self):
        self.game_map.is_tile_slidable.return_value = True
        _press(self.pm, pygame.K_UP)
        self.pm.update(self.DT, self.stepper)
        _release(self.pm, pygame.K_UP)

        self.pm.update(self.DT, self.stepper)

        assert self.player.is_sliding is True
        self.pm._sound_manager.play.assert_called_once_with("ice_slide")

    def test_two_players_each_follow_their_own_input(
        self, player_manager, mock_game_map
    ):
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[3], mode=GameMode.TWO_PLAYERS
        )
        p1, p2 = player_manager.players
        p1_y, p2_y = p1.y, p2.y
        _press(player_manager, pygame.K_UP)

        player_manager.update(self.DT, self.stepper)

        assert p1.y < p1_y
        assert p2.y == p2_y


# ---------------------------------------------------------------------------
# TestPlayerManagerHandleEvent
# ---------------------------------------------------------------------------


class TestPlayerManagerHandleEvent:
    def test_handle_event_reaches_every_players_input(
        self, player_manager, mock_game_map
    ):
        """handle_event() forwards the event to each slot's input."""
        mock_game_map.player_spawn_2 = (16, 24)
        # No controllers: both Players fall back to the keyboard.
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[], mode=GameMode.TWO_PLAYERS
        )
        p1, p2 = player_manager.players
        p1_y, p2_y = p1.y, p2.y

        _press(player_manager, pygame.K_UP)
        player_manager.update(1.0 / 60, TankStepper(mock_game_map))

        assert p1.y < p1_y
        assert p2.y < p2_y


# ---------------------------------------------------------------------------
# TestPlayerManagerScore
# ---------------------------------------------------------------------------


class TestPlayerManagerScore:
    def test_initial_score_zero(self, player_manager):
        """Score is 0 immediately after construction."""
        assert player_manager.score == 0

    def test_add_score_increments(self, player_manager, mock_game_map):
        """add_score(100) raises the score to 100."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        player_manager.add_score(100)
        assert player_manager.score == 100

    def test_add_score_accumulates(self, player_manager, mock_game_map):
        """Multiple add_score() calls accumulate correctly."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        player_manager.add_score(200)
        player_manager.add_score(300)
        assert player_manager.score == 500

    def test_score_is_kept_in_the_players_slot(self, player_manager, mock_game_map):
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        player_manager.add_score(300)
        assert player_manager.slots[0].score == 300

    def test_score_carries_over_to_the_next_stage(self, player_manager, mock_game_map):
        """create_players() for a new stage keeps each slot's score."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        player_manager.add_score(100, player_id=1)
        player_manager.add_score(200, player_id=2)

        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )

        assert player_manager.scores == {1: 100, 2: 200}


# ---------------------------------------------------------------------------
# TestPlayerManagerStatePreservation
# ---------------------------------------------------------------------------


class TestPlayerManagerStatePreservation:
    def test_preserve_and_restore_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Preserved lives are restored onto a new player tank."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.players[0].lives = 5
        player_manager.preserve_state()

        # Simulate stage transition: create fresh tanks
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.restore_state()

        assert player_manager.players[0].lives == 5

    def test_preserve_and_restore_star_level(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Preserved star_level is restored onto a new player tank."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.players[0].restore_star_level(2)
        player_manager.preserve_state()

        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.restore_state()

        assert player_manager.players[0].star_level == 2

    def test_restore_with_no_preserved_state(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """restore_state() with empty preserved state does not crash."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        # Nothing preserved yet — should not raise
        player_manager.restore_state()

        # Player remains in default state
        assert player_manager.players[0].lives >= 0


# ---------------------------------------------------------------------------
# TestPlayerManagerDeathHandling
# ---------------------------------------------------------------------------


class TestPlayerManagerDeathHandling:
    def test_handle_death_with_lives_respawns(self, player_manager, mock_game_map):
        """handle_player_death calls respawn() when lives remain."""
        player = MagicMock(spec=PlayerTank)
        player.lives = 2
        player.health = 0

        player_manager.handle_player_death(player)

        player.respawn.assert_called_once()

    def test_handle_death_no_lives_does_not_respawn(self, player_manager):
        player = MagicMock(spec=PlayerTank)
        player.lives = 0
        player.health = 0

        player_manager.handle_player_death(player)

        player.respawn.assert_not_called()

    def test_game_over_when_last_player_eliminated(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager.players[0]
        player.lives = 0
        player.health = 0

        assert player_manager.is_game_over() is True

    def test_no_game_over_with_no_lives_but_health_positive(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """Edge case: lives = 0 but health > 0 — is_game_over returns False."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager.players[0]
        player.lives = 0
        player.health = 1  # unusual state: out of lives but not fully dead

        assert player_manager.is_game_over() is False


# ---------------------------------------------------------------------------
# TestPlayerManagerGameOver
# ---------------------------------------------------------------------------


class TestPlayerManagerGameOver:
    def test_not_game_over_when_alive(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns False when the player is still alive."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager.players[0]
        player.health = 1
        player.lives = 2

        assert player_manager.is_game_over() is False

    def test_game_over_when_dead_no_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns True when the player is dead with no lives."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager.players[0]
        player.health = 0
        player.lives = 0

        assert player_manager.is_game_over() is True

    def test_not_game_over_when_has_lives(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns False when the player is dead but has lives left."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player = player_manager.players[0]
        player.health = 0
        player.lives = 1  # dead this frame but can still respawn

        assert player_manager.is_game_over() is False


# ---------------------------------------------------------------------------
# TestPlayerManagerReset
# ---------------------------------------------------------------------------


class TestPlayerManagerReset:
    def test_reset_clears_all_state(
        self, player_manager, mock_game_map, mock_texture_manager
    ):
        """reset() clears players, inputs, score, and preserved state."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])

        player_manager.add_score(500)
        player_manager.players[0].lives = 5
        player_manager.preserve_state()

        player_manager.reset()

        assert player_manager.slots == ()
        assert player_manager.score == 0
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        player_manager.restore_state()
        assert player_manager.score == 0
        assert player_manager.players[0].lives != 5


# ---------------------------------------------------------------------------
# TestPlayerManagerTwoPlayerCreation
# ---------------------------------------------------------------------------


class TestPlayerManagerTwoPlayerCreation:
    def test_create_two_players(self, player_manager, mock_game_map):
        """create_players(mode=GameMode.TWO_PLAYERS) produces two active players."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        players = player_manager.get_active_players()
        assert len(players) == 2

    def test_player2_has_player_id_2(self, player_manager, mock_game_map):
        """Second player has player_id=2."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        assert player_manager.players[0].player_id == 1
        assert player_manager.players[1].player_id == 2

    def test_player2_at_spawn_2_position(self, player_manager, mock_game_map):
        """Player 2 spawns at player_spawn_2 coordinates."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        p2 = player_manager.players[1]
        assert p2.x == 16 * TILE_SIZE
        assert p2.y == 24 * TILE_SIZE

    def test_2p_one_controller_input(self, player_manager, mock_game_map):
        """2P + 1 controller: P1=keyboard, P2=controller bound by instance_id."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[4], mode=GameMode.TWO_PLAYERS
        )
        assert isinstance(player_manager.slots[0].input, KeyboardInput)
        assert isinstance(player_manager.slots[1].input, ControllerInput)
        assert player_manager.slots[1].input.instance_id == 4

    def test_2p_two_controllers_both_controller(self, player_manager, mock_game_map):
        """2P + 2 controllers: each player bound to its own instance_id."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[8, 12], mode=GameMode.TWO_PLAYERS
        )
        assert isinstance(player_manager.slots[0].input, ControllerInput)
        assert player_manager.slots[0].input.instance_id == 8
        assert isinstance(player_manager.slots[1].input, ControllerInput)
        assert player_manager.slots[1].input.instance_id == 12

    def test_2p_two_controllers_non_sequential_instance_ids(
        self, player_manager, mock_game_map
    ):
        """Regression: non-sequential instance_ids (e.g. 0 and 5) route correctly.

        Previously PlayerInput stored a device index that assumed 0-based
        sequential IDs, so plugging a second controller later whose SDL
        instance_id wasn't 1 broke per-player routing.
        """
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0, 5], mode=GameMode.TWO_PLAYERS
        )
        assert player_manager.slots[0].input.instance_id == 0
        assert player_manager.slots[1].input.instance_id == 5

    def test_2p_both_slots_are_human_players(self, player_manager, mock_game_map):
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        assert [slot.kind for slot in player_manager.slots] == [
            PlayerKind.HUMAN,
            PlayerKind.HUMAN,
        ]
        assert player_manager.cpu_partner_ids == frozenset()

    def test_2p_fallback_spawn_when_no_spawn_2(self, player_manager, mock_game_map):
        """When player_spawn_2 is absent, derive P2 position from P1."""
        mock_game_map.player_spawn_2 = None
        mock_game_map.player_spawn = (8, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        p2 = player_manager.players[1]
        assert p2.x == (8 + 8) * TILE_SIZE
        assert p2.y == 24 * TILE_SIZE

    def test_2p_per_player_scores(self, player_manager, mock_game_map):
        """Per-player scores start at 0 and accumulate independently."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        player_manager.add_score(100, player_id=1)
        player_manager.add_score(200, player_id=2)
        assert player_manager.get_score(1) == 100
        assert player_manager.get_score(2) == 200
        assert player_manager.score == 300

    def test_1p_add_score_backward_compatible(self, player_manager, mock_game_map):
        """add_score() without player_id works for 1P."""
        player_manager.create_players(mock_game_map, controller_instance_ids=[])
        player_manager.add_score(100)
        assert player_manager.score == 100

    def test_2p_no_controllers_both_keyboard(self, player_manager, mock_game_map):
        """2P + 0 controllers: both players fall back to keyboard (degenerate).

        This mode is not playable (P1 and P2 both fight for arrow keys) but
        must not crash; the UI guards against entering it.
        """
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[], mode=GameMode.TWO_PLAYERS
        )

        assert isinstance(player_manager.slots[0].input, KeyboardInput)
        assert isinstance(player_manager.slots[1].input, KeyboardInput)


# ---------------------------------------------------------------------------
# TestPlayerManagerCpuPartner
# ---------------------------------------------------------------------------


class TestPlayerManagerCpuPartner:
    DT = 1.0 / 60

    @pytest.fixture
    def cpu_pm(self, player_manager, mock_game_map):
        """PlayerManager in 1 Player + CPU mode."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[3], mode=GameMode.ONE_PLAYER_CPU
        )
        return player_manager

    @staticmethod
    def view(pm: PlayerManager, enemies: list[tuple[float, float]]) -> WorldView:
        """Hand-built open-field World View of the tanks plus Enemies at pixels."""
        return WorldView(
            tile_size=TILE_SIZE,
            tiles=((TileType.EMPTY,) * 26,) * 26,
            players=tuple(
                PlayerView(player_id=p.player_id, x=p.x, y=p.y, direction=p.direction)
                for p in pm.players
            ),
            enemies=tuple(
                EnemyView(enemy_id=i, x=x, y=y, direction=Direction.DOWN)
                for i, (x, y) in enumerate(enemies)
            ),
        )

    def test_p1_is_human_and_p2_is_cpu_partner(self, cpu_pm):
        assert [p.player_id for p in cpu_pm.get_active_players()] == [1, 2]
        assert isinstance(cpu_pm.slots[0].input, CombinedInput)
        assert isinstance(cpu_pm.slots[1].input, CpuPartnerInput)
        assert [slot.kind for slot in cpu_pm.slots] == [
            PlayerKind.HUMAN,
            PlayerKind.CPU_PARTNER,
        ]

    def test_cpu_partner_ids_names_the_p2_slot(self, cpu_pm):
        assert cpu_pm.cpu_partner_ids == frozenset({2})

    def test_respawn_makes_cpu_partner_choose_a_new_target(self, cpu_pm, mock_game_map):
        p2 = cpu_pm.players[1]
        far_left = (p2.x - 6 * TILE_SIZE, p2.y - 10 * TILE_SIZE)
        stepper = TankStepper(mock_game_map)
        cpu_pm.observe(self.view(cpu_pm, enemies=[far_left]))
        cpu_pm.update(self.DT, stepper)

        p2.lives = 2
        cpu_pm.handle_player_death(p2)
        x_after_respawn = p2.x
        # Its Firing Positions are 3 tiles right, against 6 left for far_left.
        close_right = (p2.x + 3 * TILE_SIZE, p2.y - 10 * TILE_SIZE)
        # Past the CPU Partner's reaction delay to its new target.
        for _ in range(round(CPU_PARTNER_REACTION_DELAY * FPS) + 1):
            cpu_pm.observe(self.view(cpu_pm, enemies=[far_left, close_right]))
            cpu_pm.update(self.DT, stepper)

        assert p2.x > x_after_respawn

    def test_game_over_when_human_out_even_if_cpu_partner_has_lives(self, cpu_pm):
        p1, p2 = cpu_pm.players
        p1.lives = 0
        p1.health = 0
        p2.lives = 3

        assert cpu_pm.is_game_over() is True

    def test_cpu_partner_out_does_not_end_game_while_human_alive(self, cpu_pm):
        p1, p2 = cpu_pm.players
        p2.lives = 0
        p2.health = 0

        assert cpu_pm.is_game_over() is False


class TestPlayerManagerTwoPlayerDeath:
    @pytest.fixture
    def two_player_pm(self, player_manager, mock_game_map):
        """Create a 2P PlayerManager."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager.create_players(
            mock_game_map, controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        return player_manager

    def test_dead_player_does_not_borrow_from_partner(self, two_player_pm):
        """Each player has their own life pool — no transfers between players."""
        p1 = two_player_pm.players[0]
        p2 = two_player_pm.players[1]
        p1.lives = 0
        p1.health = 0
        p2.lives = 3

        two_player_pm.handle_player_death(p1)

        assert two_player_pm.is_game_over() is False  # p2 is still alive
        assert p2.lives == 3  # untouched
        assert p1.lives == 0  # stays dead

    def test_game_over_when_last_player_dies(self, two_player_pm):
        """Game ends when the surviving player loses their last life."""
        p1 = two_player_pm.players[0]
        p2 = two_player_pm.players[1]
        p1.lives = 0
        p1.health = 0
        p2.lives = 0
        p2.health = 0

        two_player_pm.handle_player_death(p2)

        assert two_player_pm.is_game_over() is True

    def test_game_over_only_when_both_eliminated(self, two_player_pm):
        """is_game_over() is True only when both players are dead with 0 lives."""
        p1 = two_player_pm.players[0]
        p2 = two_player_pm.players[1]

        p1.lives = 0
        p1.health = 0
        p2.lives = 2
        p2.health = 1
        assert two_player_pm.is_game_over() is False

        p2.lives = 0
        p2.health = 0
        assert two_player_pm.is_game_over() is True
