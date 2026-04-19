"""PlayerManager: owns player tanks, input, bullets, and score."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from loguru import logger

from src.core.bullet import Bullet
from src.core.player_tank import PlayerTank
from src.managers.ai_player_input import AIPlayerInput
from src.managers.player_input import (
    CombinedInput,
    ControllerInput,
    KeyboardInput,
    PlayerInput,
)
from src.states.game_mode import GameMode

if TYPE_CHECKING:
    from src.core.enemy_tank import EnemyTank
    from src.core.map import Map
    from src.managers.sound_manager import SoundManager
    from src.managers.texture_manager import TextureManager


class PlayerManager:
    """Owns the player tank(s), their input bindings, bullets, and score.

    Responsibilities:
    - Create player tanks at map spawn points.
    - Forward pygame events to PlayerInput instances.
    - Each update: call player.update(), apply ice sliding, apply movement.
    - On try_shoot: consume shoot input and spawn bullets up to max_bullets.
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
        self._bullets: list[Bullet] = []
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
        self._bullets.clear()

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

        if mode == GameMode.ONE_PLAYER:
            self._player_inputs.extend(self._one_player_inputs())
        else:
            p2_spawn = game_map.player_spawn_2
            if p2_spawn is None:
                px = game_map.player_spawn[0] + 8
                p2_spawn = (px, game_map.player_spawn[1])
            self._players.append(make_player(p2_spawn, 2))

            if mode == GameMode.ONE_PLAYER_AI:
                self._player_inputs.extend(self._one_player_inputs())
                self._player_inputs.append(AIPlayerInput(tank=self._players[1]))
            else:  # GameMode.TWO_PLAYER
                self._player_inputs.extend(
                    self._two_player_inputs(controller_instance_ids)
                )

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

    def clear_pending_shoot(self) -> None:
        # Called when leaving a menu so the confirm-button press (e.g.
        # controller A) doesn't leak into gameplay as a fired bullet.
        for pi in self._player_inputs:
            pi.clear_pending_shoot()

    def update(self, dt: float, game_map: Map, enemies: list[EnemyTank]) -> None:
        """Process input, move players, and handle ice sliding.

        For each live player:
        1. If the input is an AIPlayerInput, advance its AI state with the
           current enemy list and surviving teammate (if any).
        2. Call player.update(dt) to advance timers.
        3. Read movement direction from the paired PlayerInput.
        4. Detect whether the player is on an ice tile and start sliding if needed.
        5. Apply player.move() when there is valid (non-diagonal) input and the
           player is not currently sliding.

        Also advances all active bullets and prunes inactive ones.

        Args:
            dt: Time step in seconds.
            game_map: Current map (used for ice tile detection).
            enemies: Live enemy tanks; forwarded to AI inputs for targeting.
        """
        for player, player_input in zip(self._players, self._player_inputs):
            if player.health <= 0:
                continue

            if isinstance(player_input, AIPlayerInput):
                teammate = next(
                    (p for p in self._players if p is not player and p.health > 0),
                    None,
                )
                player_input.update(dt, enemies, teammate)

            player.update(dt)

            dx, dy = player_input.get_movement_direction()
            has_valid_input = (dx != 0 or dy != 0) and not (dx != 0 and dy != 0)

            # Ice slide: trigger BEFORE move() so start_slide() captures old direction
            player.on_ice = game_map.is_tile_slidable(
                player.x, player.y, player.width, player.height
            )
            if player.on_ice and not player.is_sliding:
                if not has_valid_input or (dx, dy) != player.direction.delta:
                    if player.start_slide():
                        self._sound_manager.play("ice_slide")

            if has_valid_input and not player.is_sliding:
                player.move(dx, dy, dt)

        for bullet in self._bullets:
            bullet.update(dt)
        self._bullets = [b for b in self._bullets if b.active]

    def try_shoot(self) -> None:
        """Check shoot input for each player and fire a bullet if possible.

        Respects each tank's max_bullets cap — no new bullet is created when
        the player already has that many active bullets in flight.
        """
        for player, player_input in zip(self._players, self._player_inputs):
            if player.health <= 0:
                continue
            if player_input.consume_shoot():
                active_count = sum(
                    1 for b in self._bullets if b.owner is player and b.active
                )
                if active_count < player.max_bullets:
                    bullet: Bullet | None = player.shoot()
                    if bullet is not None:
                        self._bullets.append(bullet)
                        self._sound_manager.play("shoot")

    def get_all_bullets(self) -> list[Bullet]:
        """Return all player bullets (pruned to active-only by update()).

        Read-only: callers must not mutate the returned list.
        """
        return self._bullets

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

    def handle_player_death(self, player: PlayerTank) -> bool:
        """Handle a player's destruction. Returns True if game should end.

        Args:
            player: The PlayerTank that was just destroyed.

        Returns:
            True if the game should end (all players eliminated), False otherwise.
        """
        if player.lives > 0:
            player.respawn()
            return False

        return self.is_game_over()

    def is_game_over(self) -> bool:
        """Check if all players are eliminated (0 lives and dead).

        Returns:
            True when every player has no lives remaining and health <= 0.
        """
        return all(p.lives <= 0 and p.health <= 0 for p in self._players)

    def reset(self) -> None:
        """Full reset for starting a new game."""
        self._players.clear()
        self._player_inputs.clear()
        self._bullets.clear()
        self._scores = {}
        self._preserved_state = {}
