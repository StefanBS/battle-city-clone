"""PlayerManager: owns player tanks, input, bullets, and score."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

from src.core.bullet import Bullet
from src.core.player_tank import PlayerTank
from src.managers.player_input import InputSource, PlayerInput

if TYPE_CHECKING:
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
        self, texture_manager: "TextureManager", sound_manager: "SoundManager"
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
        self._score: int = 0
        self._preserved_state: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def create_players(self, game_map: "Map", two_player_mode: bool = False) -> None:
        """Create player tank(s) at map spawn points and assign input sources.

        For 1P mode: creates one PlayerTank at game_map.player_spawn.
        Assigns a joystick input if a joystick is detected, otherwise keyboard.
        Clears any previously stored players, inputs, and bullets.

        Args:
            game_map: The loaded Map object providing spawn position and dimensions.
            two_player_mode: Reserved for future 2-player support (unused).
        """
        self._players.clear()
        self._player_inputs.clear()
        self._bullets.clear()

        map_width_px = game_map.width * game_map.tile_size
        map_height_px = game_map.height * game_map.tile_size
        start_x = game_map.player_spawn[0] * game_map.tile_size
        start_y = game_map.player_spawn[1] * game_map.tile_size

        player = PlayerTank(
            start_x,
            start_y,
            game_map.tile_size,
            self._texture_manager,
            map_width_px=map_width_px,
            map_height_px=map_height_px,
        )
        self._players.append(player)

        if pygame.joystick.get_count() > 0:
            self._player_inputs.append(
                PlayerInput(InputSource.JOYSTICK, joystick_index=0)
            )
        else:
            self._player_inputs.append(PlayerInput(InputSource.KEYBOARD))

    # ------------------------------------------------------------------
    # Event forwarding
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        """Forward a pygame event to all PlayerInput instances.

        Args:
            event: The pygame event to process.
        """
        for pi in self._player_inputs:
            pi.handle_event(event)

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(self, dt: float, game_map: "Map") -> None:
        """Process input, move players, and handle ice sliding.

        For each live player:
        1. Call player.update(dt) to advance timers.
        2. Read movement direction from the paired PlayerInput.
        3. Detect whether the player is on an ice tile and start sliding if needed.
        4. Apply player.move() when there is valid (non-diagonal) input and the
           player is not currently sliding.

        Also advances all active bullets and prunes inactive ones.

        Args:
            dt: Time step in seconds.
            game_map: Current map (used for ice tile detection).
        """
        for player, player_input in zip(self._players, self._player_inputs):
            if player.health <= 0:
                continue

            player.update(dt)

            dx, dy = player_input.get_movement_direction()
            has_valid_input = (dx != 0 or dy != 0) and not (dx != 0 and dy != 0)

            # Ice slide: trigger BEFORE move() so start_slide() captures old direction
            player.on_ice = self._is_on_ice(player, game_map)
            if player.on_ice and not player.is_sliding:
                if not has_valid_input or (dx, dy) != player.direction.delta:
                    if player.start_slide():
                        self._sound_manager.play_ice_slide()

            if has_valid_input and not player.is_sliding:
                player.move(dx, dy, dt)

        for bullet in self._bullets:
            if bullet.active:
                bullet.update(dt)

        self._bullets = [b for b in self._bullets if b.active]

    # ------------------------------------------------------------------
    # Shooting
    # ------------------------------------------------------------------

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
                    bullet: Optional[Bullet] = player.shoot()
                    if bullet is not None:
                        self._bullets.append(bullet)
                        self._sound_manager.play_shoot()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_all_bullets(self) -> list[Bullet]:
        """Return all active player bullets.

        Returns:
            List of active Bullet instances.
        """
        return [b for b in self._bullets if b.active]

    def get_active_players(self) -> list[PlayerTank]:
        """Return players that are still alive (health > 0).

        Returns:
            List of living PlayerTank instances.
        """
        return [p for p in self._players if p.health > 0]

    @property
    def score(self) -> int:
        """Current player score."""
        return self._score

    def add_score(self, points: int) -> None:
        """Increment the player score.

        Args:
            points: Number of points to add.
        """
        self._score += points

    # ------------------------------------------------------------------
    # State preservation
    # ------------------------------------------------------------------

    def preserve_state(self) -> None:
        """Save player state before stage transition."""
        self._preserved_state = {}
        for i, player in enumerate(self._players):
            self._preserved_state[i] = {
                "lives": player.lives,
                "star_level": player.star_level,
            }

    def restore_state(self) -> None:
        """Restore player state after new tank creation."""
        for i, player in enumerate(self._players):
            if i in self._preserved_state:
                state = self._preserved_state[i]
                player.lives = state["lives"]
                if state["star_level"] > 0:
                    player.restore_star_level(state["star_level"])

    # ------------------------------------------------------------------
    # Death handling and game-over
    # ------------------------------------------------------------------

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
        # No lives left — player eliminated
        return self.is_game_over()

    def is_game_over(self) -> bool:
        """Check if all players are eliminated (0 lives and dead).

        Returns:
            True when every player has no lives remaining and health <= 0.
        """
        return all(p.lives <= 0 and p.health <= 0 for p in self._players)

    # ------------------------------------------------------------------
    # Full reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Full reset for starting a new game."""
        self._players.clear()
        self._player_inputs.clear()
        self._bullets.clear()
        self._score = 0
        self._preserved_state = {}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_on_ice(self, tank: PlayerTank, game_map: "Map") -> bool:
        """Return True if the tank's centre is over a slidable (ice) tile.

        Args:
            tank: The tank to check.
            game_map: The map providing tile information.

        Returns:
            True when the tile under the tank centre has is_slidable set.
        """
        center_x = int(tank.x + tank.width / 2)
        center_y = int(tank.y + tank.height / 2)
        grid_x = center_x // game_map.tile_size
        grid_y = center_y // game_map.tile_size
        tile = game_map.get_tile_at(grid_x, grid_y)
        return tile is not None and tile.is_slidable
