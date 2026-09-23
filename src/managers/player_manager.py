"""PlayerManager: owns the player slots (tank, input, score) and their progress."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame
from loguru import logger

from src.core.player_tank import PlayerTank
from src.managers.cpu_partner import CpuPartnerInput
from src.managers.player_input import (
    CombinedInput,
    ControllerInput,
    KeyboardInput,
    PlayerInput,
)
from src.states.game_mode import GameMode

if TYPE_CHECKING:
    from src.core.map import Map
    from src.managers.sound_manager import SoundManager
    from src.managers.tank_stepper import TankStepper
    from src.managers.texture_manager import TextureManager
    from src.managers.world_view import WorldView


class PlayerKind(Enum):
    """Who drives the tank in a player slot."""

    HUMAN = auto()
    CPU_PARTNER = auto()


@dataclass
class PlayerSlot:
    """One player slot (P1 or P2): its tank, the input driving it, and its score."""

    tank: PlayerTank
    input: PlayerInput
    kind: PlayerKind
    score: int = 0

    @property
    def player_id(self) -> int:
        """The slot's player id (1 for P1, 2 for P2)."""
        return self.tank.player_id


@dataclass(frozen=True)
class CarriedProgress:
    """What a Player keeps from one stage to the next, besides its score."""

    lives: int
    star_level: int


class PlayerManager:
    """Owns the player slots: each Player's tank, input, kind, and score.

    Responsibilities:
    - Create one slot per Player, with its tank at the map's spawn point.
    - Forward pygame events to every slot's input.
    - Each update: step every live player through TankStepper with its input.
    - Track each Player's score and carry lives and Stars between stages.
    """

    def __init__(
        self, texture_manager: TextureManager, sound_manager: SoundManager
    ) -> None:
        """Initialize PlayerManager.

        Args:
            texture_manager: Texture atlas used when creating player tanks.
            sound_manager: Sound manager used to play audio cues.
        """
        self._texture_manager = texture_manager
        self._sound_manager = sound_manager
        self._slots: list[PlayerSlot] = []
        self._carried: dict[int, CarriedProgress] = {}

    def create_players(
        self,
        game_map: Map,
        controller_instance_ids: list[int],
        mode: GameMode = GameMode.ONE_PLAYER,
    ) -> None:
        # controller_instance_ids must come from InputHandler — it's the single
        # source of truth for which SDL game controllers are currently open.
        previous_scores = {slot.player_id: slot.score for slot in self._slots}

        map_width_px = game_map.width * game_map.tile_size
        map_height_px = game_map.height * game_map.tile_size

        def make_player(spawn: tuple[int, int], pid: int) -> PlayerTank:
            x, y = game_map.grid_to_pixels(spawn[0], spawn[1])
            return PlayerTank(
                x,
                y,
                game_map.tile_size,
                self._texture_manager,
                map_width_px=map_width_px,
                map_height_px=map_height_px,
                player_id=pid,
            )

        tanks = [make_player(game_map.player_spawn, 1)]
        if mode is not GameMode.ONE_PLAYER:
            p2_spawn = game_map.player_spawn_2
            if p2_spawn is None:
                px = game_map.player_spawn[0] + 8
                p2_spawn = (px, game_map.player_spawn[1])
            tanks.append(make_player(p2_spawn, 2))

        match mode:
            case GameMode.ONE_PLAYER:
                drivers = [(inp, PlayerKind.HUMAN) for inp in self._one_player_inputs()]
            case GameMode.TWO_PLAYERS:
                drivers = [
                    (inp, PlayerKind.HUMAN)
                    for inp in self._two_player_inputs(controller_instance_ids)
                ]
            case GameMode.ONE_PLAYER_CPU:
                drivers = [
                    (self._one_player_inputs()[0], PlayerKind.HUMAN),
                    (CpuPartnerInput(), PlayerKind.CPU_PARTNER),
                ]

        self._slots = [
            PlayerSlot(
                tank=tank,
                input=player_input,
                kind=kind,
                score=previous_scores.get(tank.player_id, 0),
            )
            for tank, (player_input, kind) in zip(tanks, drivers, strict=True)
        ]

    @staticmethod
    def _one_player_inputs() -> list[PlayerInput]:
        return [CombinedInput([KeyboardInput(), ControllerInput(instance_id=None)])]

    @staticmethod
    def _two_player_inputs(instance_ids: list[int]) -> list[PlayerInput]:
        if len(instance_ids) >= 2:
            return [
                ControllerInput(instance_ids[0]),
                ControllerInput(instance_ids[1]),
            ]
        if len(instance_ids) == 1:
            return [KeyboardInput(), ControllerInput(instance_ids[0])]
        logger.warning(
            "2-player mode started without any controllers; P1 and P2 will "
            "both use the keyboard and compete for the same keys."
        )
        return [KeyboardInput(), KeyboardInput()]

    def handle_event(self, event: pygame.event.Event) -> None:
        for slot in self._slots:
            slot.input.handle_event(event)

    def observe(self, world: WorldView) -> None:
        """Hand this frame's World View to every input, marking its own tank."""
        for slot in self._slots:
            slot.input.observe(world.for_player(slot.player_id))

    def clear_pending_shoot(self) -> None:
        # Called when leaving a menu so the confirm-button press (e.g.
        # controller A) doesn't leak into gameplay as a fired bullet.
        for slot in self._slots:
            slot.input.clear_pending_shoot()

    def update(self, dt: float, stepper: TankStepper) -> None:
        """Step every live player with its input and play its sounds.

        Args:
            dt: Time step in seconds.
            stepper: Steps each tank and owns the bullets it fires.
        """
        for slot in self._slots:
            if slot.tank.health <= 0:
                continue
            result = stepper.step(slot.tank, slot.input, dt)
            if result.slide_started:
                self._sound_manager.play("ice_slide")
            if result.fired:
                self._sound_manager.play("shoot")

    @property
    def slots(self) -> tuple[PlayerSlot, ...]:
        """Every player slot, P1 first."""
        return tuple(self._slots)

    @property
    def players(self) -> list[PlayerTank]:
        """All player tanks, alive or not."""
        return [slot.tank for slot in self._slots]

    def get_active_players(self) -> list[PlayerTank]:
        """Return players that are still alive (health > 0).

        Returns:
            List of living PlayerTank instances.
        """
        return [slot.tank for slot in self._slots if slot.tank.health > 0]

    @property
    def score(self) -> int:
        """Total score across all players."""
        return sum(slot.score for slot in self._slots)

    def add_score(self, points: int, player_id: int = 1) -> None:
        """Add points to a specific player's score.

        Args:
            points: Number of points to add.
            player_id: The player whose score to update (defaults to P1).

        Raises:
            KeyError: If no slot has that player id.
        """
        slot = self._find_slot(player_id)
        if slot is None:
            raise KeyError(f"No player slot with id {player_id}")
        slot.score += points

    @property
    def scores(self) -> dict[int, int]:
        """Per-player scores {player_id: score}."""
        return {slot.player_id: slot.score for slot in self._slots}

    def get_score(self, player_id: int) -> int:
        """Get a specific player's score.

        Args:
            player_id: The player whose score to retrieve.

        Returns:
            The player's current score, or 0 if not found.
        """
        slot = self._find_slot(player_id)
        return slot.score if slot is not None else 0

    def _find_slot(self, player_id: int) -> PlayerSlot | None:
        return next((s for s in self._slots if s.player_id == player_id), None)

    def preserve_state(self) -> None:
        """Save each Player's lives and Stars before a stage transition."""
        self._carried = {
            slot.player_id: CarriedProgress(
                lives=slot.tank.lives, star_level=slot.tank.star_level
            )
            for slot in self._slots
        }

    def restore_state(self) -> None:
        """Put the saved lives and Stars back onto the newly created tanks."""
        for slot in self._slots:
            progress = self._carried.get(slot.player_id)
            if progress is not None:
                slot.tank.lives = progress.lives
                if progress.star_level > 0:
                    slot.tank.restore_star_level(progress.star_level)

    def handle_player_death(self, player: PlayerTank) -> None:
        """Respawn a destroyed Player and reset its input, if it has lives left.

        Args:
            player: The PlayerTank that was just destroyed.
        """
        if player.lives <= 0:
            return
        player.respawn()
        for slot in self._slots:
            if slot.tank is player:
                slot.input.reset()

    @property
    def cpu_partner_ids(self) -> frozenset[int]:
        """Player ids whose tank is driven by a CPU Partner."""
        return frozenset(
            slot.player_id
            for slot in self._slots
            if slot.kind is PlayerKind.CPU_PARTNER
        )

    def is_game_over(self) -> bool:
        """Check if every Human Player is eliminated (0 lives and dead).

        A CPU Partner's remaining lives do not keep the game going.

        Returns:
            True when every Human Player has no lives remaining and health <= 0.
        """
        return all(
            slot.tank.lives <= 0 and slot.tank.health <= 0
            for slot in self._slots
            if slot.kind is PlayerKind.HUMAN
        )

    def reset(self) -> None:
        """Full reset for starting a new game."""
        self._slots = []
        self._carried = {}
