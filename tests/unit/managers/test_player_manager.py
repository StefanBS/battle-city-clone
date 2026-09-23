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
from src.managers.player_manager import (
    CarriedProgress,
    PlayerHudEntry,
    PlayerKind,
    PlayerManager,
)
from src.managers.sound_manager import SoundManager
from src.managers.tank_stepper import TankStepper
from src.managers.world_view import EnemyView, PlayerView, WorldView
from src.states.game_mode import GameMode
from src.utils.constants import (
    CPU_PARTNER_REACTION_DELAY,
    FPS,
    INITIAL_PLAYER_LIVES,
    TILE_SIZE,
    Direction,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sound_manager():
    """Mock SoundManager."""
    return MagicMock(spec=SoundManager)


@pytest.fixture
def make_player_manager(mock_texture_manager, mock_sound_manager, mock_game_map):
    """Build a PlayerManager on the mock map, after any spawn tweaks a test makes."""

    def _make(
        controller_instance_ids=(),
        mode=GameMode.ONE_PLAYER,
        carried=None,
    ):
        return PlayerManager(
            mock_texture_manager,
            mock_sound_manager,
            mock_game_map,
            controller_instance_ids=list(controller_instance_ids),
            mode=mode,
            carried=carried,
        )

    return _make


@pytest.fixture
def player_manager(make_player_manager):
    """A 1-player PlayerManager with mock dependencies."""
    return make_player_manager()


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
    def test_creates_single_player(
        self, make_player_manager, mock_game_map, mock_texture_manager
    ):
        """1P mode produces exactly one active player."""
        player_manager = make_player_manager(controller_instance_ids=[])

        players = player_manager.get_active_players()
        assert len(players) == 1
        assert isinstance(players[0], PlayerTank)

    def test_player_starts_at_spawn_point(
        self, make_player_manager, mock_game_map, mock_texture_manager
    ):
        """Player tank is placed at the map's player_spawn coordinates."""
        mock_game_map.player_spawn = (3, 22)
        mock_game_map.tile_size = TILE_SIZE

        player_manager = make_player_manager(controller_instance_ids=[])

        player = player_manager.get_active_players()[0]
        expected_x = 3 * TILE_SIZE
        expected_y = 22 * TILE_SIZE
        assert player.x == expected_x
        assert player.y == expected_y

    @pytest.mark.parametrize("controller_instance_ids", [[], [7]])
    def test_1p_is_combined_input(
        self, make_player_manager, mock_game_map, controller_instance_ids
    ) -> None:
        """1P always wraps keyboard + non-filtering controller in CombinedInput.

        Uses ControllerInput(instance_id=None) whatever controllers are
        plugged in, so hot-plugging Just Works.
        """
        player_manager = make_player_manager(
            controller_instance_ids=controller_instance_ids
        )
        pi = player_manager._slots[0].input
        assert isinstance(pi, CombinedInput)
        assert len(pi._inputs) == 2
        assert isinstance(pi._inputs[0], KeyboardInput)
        assert isinstance(pi._inputs[1], ControllerInput)
        assert pi._inputs[1].instance_id is None

    def test_get_active_players_returns_living(
        self, make_player_manager, mock_game_map
    ):
        """get_active_players() filters out dead tanks."""
        player_manager = make_player_manager(controller_instance_ids=[])

        player_manager.get_active_players()[0].health = 0
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
    def setup(self, make_player_manager, mock_game_map):
        """Create a single player and a stepper before each test in this class."""
        player_manager = make_player_manager(controller_instance_ids=[])
        self.pm = player_manager
        self.game_map = mock_game_map
        self.stepper = TankStepper(mock_game_map)
        self.player = player_manager.get_active_players()[0]

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
        self, make_player_manager, mock_game_map
    ):
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[3], mode=GameMode.TWO_PLAYERS
        )
        p1, p2 = player_manager.get_active_players()
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
        self, make_player_manager, mock_game_map
    ):
        """handle_event() forwards the event to each slot's input."""
        mock_game_map.player_spawn_2 = (16, 24)
        # No controllers: both Players fall back to the keyboard.
        player_manager = make_player_manager(
            controller_instance_ids=[], mode=GameMode.TWO_PLAYERS
        )
        p1, p2 = player_manager.get_active_players()
        p1_y, p2_y = p1.y, p2.y

        _press(player_manager, pygame.K_UP)
        player_manager.update(1.0 / 60, TankStepper(mock_game_map))

        assert p1.y < p1_y
        assert p2.y < p2_y


# ---------------------------------------------------------------------------
# TestPlayerManagerScore
# ---------------------------------------------------------------------------


class TestPlayerManagerScore:
    def test_add_score_accumulates(self, make_player_manager, mock_game_map):
        """Multiple add_score() calls accumulate correctly."""
        player_manager = make_player_manager(controller_instance_ids=[])
        player_manager.add_score(200)
        player_manager.add_score(300)
        assert player_manager.score == 500

    def test_add_score_for_a_missing_slot_raises(self, player_manager):
        with pytest.raises(KeyError):
            player_manager.add_score(100, player_id=2)

    def test_score_comes_from_carried_progress(
        self, make_player_manager, mock_game_map
    ):
        """Each slot starts with the score it carried from the previous Battle."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0],
            mode=GameMode.TWO_PLAYERS,
            carried={
                1: CarriedProgress(lives=3, star_level=0, score=100),
                2: CarriedProgress(lives=3, star_level=0, score=200),
            },
        )

        assert player_manager.get_score(1) == 100
        assert player_manager.get_score(2) == 200


# ---------------------------------------------------------------------------
# TestPlayerManagerCarriedProgress
# ---------------------------------------------------------------------------


class TestPlayerManagerCarriedProgress:
    def test_carried_lives_and_stars_go_onto_the_new_tanks(self, make_player_manager):
        player_manager = make_player_manager(
            carried={1: CarriedProgress(lives=5, star_level=2, score=0)}
        )

        assert player_manager.get_active_players()[0].lives == 5
        assert player_manager.get_active_players()[0].star_level == 2

    def test_players_without_carried_progress_start_fresh(self, make_player_manager):
        player_manager = make_player_manager(carried={})

        player = player_manager.get_active_players()[0]
        assert player.lives == INITIAL_PLAYER_LIVES
        assert player.star_level == 0
        assert player_manager.score == 0

    def test_carried_progress_reports_each_slot(
        self, make_player_manager, mock_game_map
    ):
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        p1, p2 = player_manager.get_active_players()
        p1.lives = 5
        p1.restore_star_level(2)
        p2.lives = 1
        player_manager.add_score(300, player_id=2)

        assert player_manager.carried_progress == {
            1: CarriedProgress(lives=5, star_level=2, score=0),
            2: CarriedProgress(lives=1, star_level=0, score=300),
        }

    def test_carried_progress_marks_a_player_out_of_lives_as_eliminated(
        self, make_player_manager, mock_game_map
    ):
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        p1, p2 = player_manager.get_active_players()
        p1.lives = 0  # on its last life, still in play
        p2.lives = 0
        p2.health = 0

        carried = player_manager.carried_progress

        assert carried[1].eliminated is False
        assert carried[2].eliminated is True

    def test_an_eliminated_player_stays_out_but_keeps_its_score(
        self, make_player_manager, mock_game_map
    ):
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0],
            mode=GameMode.TWO_PLAYERS,
            carried={
                1: CarriedProgress(lives=2, star_level=0, score=100),
                2: CarriedProgress(lives=0, star_level=0, score=700, eliminated=True),
            },
        )

        assert [p.player_id for p in player_manager.get_active_players()] == [1]
        assert player_manager.hud_entries[1].eliminated is True
        assert player_manager.get_score(2) == 700
        assert player_manager.carried_progress[2].eliminated is True


# ---------------------------------------------------------------------------
# TestPlayerManagerHud
# ---------------------------------------------------------------------------


class TestPlayerManagerHud:
    def test_one_entry_per_player_with_lives_and_score(
        self, make_player_manager, mock_game_map
    ):
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0],
            mode=GameMode.TWO_PLAYERS,
            carried={
                1: CarriedProgress(lives=3, star_level=0, score=100),
                2: CarriedProgress(lives=2, star_level=0, score=250),
            },
        )

        assert player_manager.hud_entries == (
            PlayerHudEntry(label="P1", lives=3, score=100),
            PlayerHudEntry(label="P2", lives=2, score=250),
        )

    def test_cpu_partner_is_labelled_cpu(self, make_player_manager, mock_game_map):
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(mode=GameMode.ONE_PLAYER_CPU)

        labels = [entry.label for entry in player_manager.hud_entries]

        assert labels == ["P1", "CPU"]


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

    def test_no_game_over_with_no_lives_but_health_positive(
        self, make_player_manager, mock_game_map, mock_texture_manager
    ):
        """Edge case: lives = 0 but health > 0 — is_game_over returns False."""
        player_manager = make_player_manager(controller_instance_ids=[])

        player = player_manager.get_active_players()[0]
        player.lives = 0
        player.health = 1  # unusual state: out of lives but not fully dead

        assert player_manager.is_game_over() is False


# ---------------------------------------------------------------------------
# TestPlayerManagerGameOver
# ---------------------------------------------------------------------------


class TestPlayerManagerGameOver:
    def test_not_game_over_when_alive(
        self, make_player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns False when the player is still alive."""
        player_manager = make_player_manager(controller_instance_ids=[])

        player = player_manager.get_active_players()[0]
        player.health = 1
        player.lives = 2

        assert player_manager.is_game_over() is False

    def test_game_over_when_dead_no_lives(
        self, make_player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns True when the player is dead with no lives."""
        player_manager = make_player_manager(controller_instance_ids=[])

        player = player_manager.get_active_players()[0]
        player.health = 0
        player.lives = 0

        assert player_manager.is_game_over() is True

    def test_not_game_over_when_has_lives(
        self, make_player_manager, mock_game_map, mock_texture_manager
    ):
        """is_game_over() returns False when the player is dead but has lives left."""
        player_manager = make_player_manager(controller_instance_ids=[])

        player = player_manager.get_active_players()[0]
        player.health = 0
        player.lives = 1  # dead this frame but can still respawn

        assert player_manager.is_game_over() is False


# ---------------------------------------------------------------------------
# TestPlayerManagerTwoPlayerCreation
# ---------------------------------------------------------------------------


class TestPlayerManagerTwoPlayerCreation:
    def test_create_two_players(self, make_player_manager, mock_game_map):
        """2P mode produces two active players, with player_ids 1 and 2."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        players = player_manager.get_active_players()
        assert [p.player_id for p in players] == [1, 2]

    def test_player2_at_spawn_2_position(self, make_player_manager, mock_game_map):
        """Player 2 spawns at player_spawn_2 coordinates."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        p2 = player_manager.get_active_players()[1]
        assert p2.x == 16 * TILE_SIZE
        assert p2.y == 24 * TILE_SIZE

    def test_2p_one_controller_input(self, make_player_manager, mock_game_map):
        """2P + 1 controller: P1=keyboard, P2=controller bound by instance_id."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[4], mode=GameMode.TWO_PLAYERS
        )
        assert isinstance(player_manager._slots[0].input, KeyboardInput)
        assert isinstance(player_manager._slots[1].input, ControllerInput)
        assert player_manager._slots[1].input.instance_id == 4

    def test_2p_two_controllers_both_controller(
        self, make_player_manager, mock_game_map
    ):
        """2P + 2 controllers: each player bound to its own instance_id.

        Regression: the ids are non-sequential on purpose. Previously
        PlayerInput stored a device index that assumed 0-based sequential
        IDs, so plugging a second controller later whose SDL instance_id
        wasn't 1 broke per-player routing.
        """
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[8, 12], mode=GameMode.TWO_PLAYERS
        )
        assert isinstance(player_manager._slots[0].input, ControllerInput)
        assert player_manager._slots[0].input.instance_id == 8
        assert isinstance(player_manager._slots[1].input, ControllerInput)
        assert player_manager._slots[1].input.instance_id == 12

    def test_2p_fallback_spawn_when_no_spawn_2(
        self, make_player_manager, mock_game_map
    ):
        """When player_spawn_2 is absent, derive P2 position from P1."""
        mock_game_map.player_spawn_2 = None
        mock_game_map.player_spawn = (8, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        p2 = player_manager.get_active_players()[1]
        assert p2.x == (8 + 8) * TILE_SIZE
        assert p2.y == 24 * TILE_SIZE

    def test_2p_per_player_scores(self, make_player_manager, mock_game_map):
        """Per-player scores start at 0 and accumulate independently."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        player_manager.add_score(100, player_id=1)
        player_manager.add_score(200, player_id=2)
        assert player_manager.get_score(1) == 100
        assert player_manager.get_score(2) == 200
        assert player_manager.score == 300

    def test_2p_no_controllers_both_keyboard(self, make_player_manager, mock_game_map):
        """2P + 0 controllers: both players fall back to keyboard (degenerate).

        This mode is not playable (P1 and P2 both fight for arrow keys) but
        must not crash; the UI guards against entering it.
        """
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[], mode=GameMode.TWO_PLAYERS
        )

        assert isinstance(player_manager._slots[0].input, KeyboardInput)
        assert isinstance(player_manager._slots[1].input, KeyboardInput)


# ---------------------------------------------------------------------------
# TestPlayerManagerCpuPartner
# ---------------------------------------------------------------------------


class TestPlayerManagerCpuPartner:
    DT = 1.0 / 60

    @pytest.fixture
    def cpu_pm(self, make_player_manager, mock_game_map):
        """PlayerManager in 1 Player + CPU mode."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[3], mode=GameMode.ONE_PLAYER_CPU
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
                for p in pm.get_active_players()
            ),
            enemies=tuple(
                EnemyView(enemy_id=i, x=x, y=y, direction=Direction.DOWN)
                for i, (x, y) in enumerate(enemies)
            ),
        )

    def test_p1_is_human_and_p2_is_cpu_partner(self, cpu_pm):
        assert [p.player_id for p in cpu_pm.get_active_players()] == [1, 2]
        assert isinstance(cpu_pm._slots[0].input, CombinedInput)
        assert isinstance(cpu_pm._slots[1].input, CpuPartnerInput)
        assert [slot.kind for slot in cpu_pm._slots] == [
            PlayerKind.HUMAN,
            PlayerKind.CPU_PARTNER,
        ]

    def test_respawn_makes_cpu_partner_choose_a_new_target(self, cpu_pm, mock_game_map):
        p2 = cpu_pm.get_active_players()[1]
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
        p1, p2 = cpu_pm.get_active_players()
        p1.lives = 0
        p1.health = 0
        p2.lives = 3

        assert cpu_pm.is_game_over() is True

    def test_cpu_partner_out_does_not_end_game_while_human_alive(self, cpu_pm):
        p1, p2 = cpu_pm.get_active_players()
        p2.lives = 0
        p2.health = 0

        assert cpu_pm.is_game_over() is False


class TestPlayerManagerTwoPlayerDeath:
    @pytest.fixture
    def two_player_pm(self, make_player_manager, mock_game_map):
        """Create a 2P PlayerManager."""
        mock_game_map.player_spawn_2 = (16, 24)
        player_manager = make_player_manager(
            controller_instance_ids=[0], mode=GameMode.TWO_PLAYERS
        )
        return player_manager

    def test_dead_player_does_not_borrow_from_partner(self, two_player_pm):
        """Each player has their own life pool — no transfers between players."""
        p1 = two_player_pm.get_active_players()[0]
        p2 = two_player_pm.get_active_players()[1]
        p1.lives = 0
        p1.health = 0
        p2.lives = 3

        two_player_pm.handle_player_death(p1)

        assert two_player_pm.is_game_over() is False  # p2 is still alive
        assert p2.lives == 3  # untouched
        assert p1.lives == 0  # stays dead

    def test_game_over_only_when_both_eliminated(self, two_player_pm):
        """is_game_over() is True only when both players are dead with 0 lives."""
        p1 = two_player_pm.get_active_players()[0]
        p2 = two_player_pm.get_active_players()[1]

        p1.lives = 0
        p1.health = 0
        p2.lives = 2
        p2.health = 1
        assert two_player_pm.is_game_over() is False

        p2.lives = 0
        p2.health = 0
        assert two_player_pm.is_game_over() is True
