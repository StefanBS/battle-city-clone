"""PlayerManager: owns player tanks, input, and score."""

from __future__ import annotations

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


class PlayerManager:
    """Owns the player tank(s), their input bindings, and score.

    Responsibilities:
    - Create player tanks at map spawn points.
    - Forward pygame events to PlayerInput instances.
    - Each update: step every live player through TankStepper with its input.
    - Track player score.
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
        self._players: list[PlayerTank] = []
        self._player_inputs: list[PlayerInput] = []
        self._scores: dict[int, int] = {}
        self._preserved_state: dict[int, dict] = {}

    def create_players(
        self,
        game_map: Map,
        controller_instance_ids: list[int],
        mode: GameMode = GameMode.ONE_PLAYER,
    ) -> None:
        # controller_instance_ids must come from InputHandler — it's the single
        # source of truth for which SDL game controllers are currently open.
        self._players.clear()
        self._player_inputs.clear()

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

        self._players.append(make_player(game_map.player_spawn, 1))
        if mode is not GameMode.ONE_PLAYER:
            p2_spawn = game_map.player_spawn_2
            if p2_spawn is None:
                px = game_map.player_spawn[0] + 8
                p2_spawn = (px, game_map.player_spawn[1])
            self._players.append(make_player(p2_spawn, 2))

        match mode:
            case GameMode.ONE_PLAYER:
                self._player_inputs.extend(self._one_player_inputs())
            case GameMode.TWO_PLAYERS:
                self._player_inputs.extend(
                    self._two_player_inputs(controller_instance_ids)
                )
            case GameMode.ONE_PLAYER_CPU:
                self._player_inputs.extend(self._one_player_inputs())
                self._player_inputs.append(CpuPartnerInput())

        for player in self._players:
            if player.player_id not in self._scores:
                self._scores[player.player_id] = 0

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
        for pi in self._player_inputs:
            pi.handle_event(event)

    def observe(self, world: WorldView) -> None:
        """Hand this frame's World View to every input, marking its own tank."""
        for player, player_input in zip(self._players, self._player_inputs):
            player_input.observe(world.for_player(player.player_id))

    def clear_pending_shoot(self) -> None:
        # Called when leaving a menu so the confirm-button press (e.g.
        # controller A) doesn't leak into gameplay as a fired bullet.
        for pi in self._player_inputs:
            pi.clear_pending_shoot()

    def update(self, dt: float, stepper: TankStepper) -> None:
        """Step every live player with its input and play its sounds.

        Args:
            dt: Time step in seconds.
            stepper: Steps each tank and owns the bullets it fires.
        """
        for player, player_input in zip(self._players, self._player_inputs):
            if player.health <= 0:
                continue
            result = stepper.step(player, player_input, dt)
            if result.slide_started:
                self._sound_manager.play("ice_slide")
            if result.fired:
                self._sound_manager.play("shoot")

    @property
    def players(self) -> list[PlayerTank]:
        """All player tanks, alive or not. Read-only view."""
        return self._players

    def get_active_players(self) -> list[PlayerTank]:
        """Return players that are still alive (health > 0).

        Returns:
            List of living PlayerTank instances.
        """
        return [p for p in self._players if p.health > 0]

    @property
    def score(self) -> int:
        """Total score across all players."""
        return sum(self._scores.values())

    def add_score(self, points: int, player_id: int = 1) -> None:
        """Add points to a specific player's score.

        Args:
            points: Number of points to add.
            player_id: The player whose score to update (defaults to 1 for
                backward compatibility with 1-player mode).
        """
        if player_id not in self._scores:
            self._scores[player_id] = 0
        self._scores[player_id] += points

    @property
    def scores(self) -> dict[int, int]:
        """Per-player scores dict {player_id: score}. Read-only view."""
        return self._scores

    def get_score(self, player_id: int) -> int:
        """Get a specific player's score.

        Args:
            player_id: The player whose score to retrieve.

        Returns:
            The player's current score, or 0 if not found.
        """
        return self._scores.get(player_id, 0)

    def preserve_state(self) -> None:
        """Save player state before stage transition."""
        self._preserved_state = {}
        for player in self._players:
            self._preserved_state[player.player_id] = {
                "lives": player.lives,
                "star_level": player.star_level,
            }

    def restore_state(self) -> None:
        """Restore player state after new tank creation."""
        for player in self._players:
            state = self._preserved_state.get(player.player_id)
            if state is not None:
                player.lives = state["lives"]
                if state["star_level"] > 0:
                    player.restore_star_level(state["star_level"])

    def handle_player_death(self, player: PlayerTank) -> None:
        """Respawn a destroyed Player and reset its input, if it has lives left.

        Args:
            player: The PlayerTank that was just destroyed.
        """
        if player.lives <= 0:
            return
        player.respawn()
        for owner, player_input in zip(self._players, self._player_inputs):
            if owner is player:
                player_input.reset()

    @property
    def cpu_partner_ids(self) -> frozenset[int]:
        """Player ids whose tank is driven by a CPU Partner."""
        return frozenset(
            player.player_id
            for player, player_input in zip(self._players, self._player_inputs)
            if isinstance(player_input, CpuPartnerInput)
        )

    def is_game_over(self) -> bool:
        """Check if every Human Player is eliminated (0 lives and dead).

        A CPU Partner's remaining lives do not keep the game going.

        Returns:
            True when every Human Player has no lives remaining and health <= 0.
        """
        cpu_ids = self.cpu_partner_ids
        return all(
            p.lives <= 0 and p.health <= 0
            for p in self._players
            if p.player_id not in cpu_ids
        )

    def reset(self) -> None:
        """Full reset for starting a new game."""
        self._players.clear()
        self._player_inputs.clear()
        self._scores = {}
        self._preserved_state = {}
