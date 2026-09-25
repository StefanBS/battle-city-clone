"""How long the CPU Partner has held a shot it may not safely take."""


class RefusedShots:
    """Counts the frames it stays lined up on its target without a safe shot.

    Only an unbroken run of frames refusing to shoot the same target counts:
    any frame it doesn't refuse, or a new target, starts the count afresh.
    """

    def __init__(self, frames: int) -> None:
        self._frames = frames
        self._count: int = 0
        self._target: int | None = None

    def should_give_up(self, refusing_enemy_id: int | None) -> bool:
        """Count one frame: whether to give up on the Enemy it refused to shoot.

        ``refusing_enemy_id`` is the Enemy it refused to shoot this frame, or
        None if it refused no shot. Once it has refused the same Enemy for
        ``frames`` in a row it gives up, and counts afresh.
        """
        if refusing_enemy_id != self._target:
            self._count = 0
        self._target = refusing_enemy_id
        if refusing_enemy_id is None:
            return False
        self._count += 1
        if self._count >= self._frames:
            self._count = 0
            return True
        return False
