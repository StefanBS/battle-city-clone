"""SoundPlayer: how the Battle plays sounds, without naming the shell."""

from typing import Protocol


class SoundPlayer(Protocol):
    """Plays the Battle's one-shot sounds and switches its loops.

    ``SoundManager`` matches it by shape; the Battle only annotates with this,
    so it never imports the shell (ADR 0008).
    """

    def play(self, name: str) -> None:
        """Play the sound called ``name``."""
        ...

    def update_engine(self, any_moving: bool) -> None:
        """Run the engine loop while any tank is moving."""
        ...

    def update_powerup_blink(self, any_active: bool) -> None:
        """Run the Power-Up loop while one is on the battlefield."""
        ...
