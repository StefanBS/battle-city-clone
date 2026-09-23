"""How long the CPU Partner has held a shot it may not safely take."""


class RefusedShots:
    """Counts the frames it stays lined up on its target without a safe shot.

    Only an unbroken run of frames refusing to shoot the same target counts:
    any frame it doesn't refuse, or a new target, starts the count afresh.
    """

    def __init__(self, frames: int) -> None:
        self._frames = frames
        self._count: int = 0
        # The count up to the last frame, kept only if it refuses this frame.
        self._carried: int = 0
        self._target: int | None = None

    def start_frame(self) -> None:
        """Start a frame: the count carries on only if it refuses in it."""
        self._carried, self._count = self._count, 0

    def refuse(self, enemy_id: int) -> bool:
        """Count a frame refusing to shoot the Enemy; whether to give up now.

        Once it has refused for ``frames`` it gives up, and counts afresh.
        """
        carried = self._carried if enemy_id == self._target else 0
        self._target = enemy_id
        self._count = carried + 1
        if self._count >= self._frames:
            self._count = 0
            return True
        return False
