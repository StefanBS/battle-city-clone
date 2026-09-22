"""What the CPU Partner remembers about an Enemy until the Enemy moves."""

from collections.abc import Mapping

from src.managers.pathfinding import Cell


class EnemyMemory[T]:
    """A value per Enemy, kept while the Enemy stays on the cell it stood on.

    Each entry expires once its Enemy is gone or stands on another cell.
    """

    def __init__(self) -> None:
        self._entries: dict[int, tuple[Cell, T]] = {}

    def remember(self, enemy_id: int, cell: Cell, value: T) -> None:
        """Keep ``value`` for the Enemy while it stands on ``cell``."""
        self._entries[enemy_id] = (cell, value)

    def get(self, enemy_id: int) -> T | None:
        """The value kept for the Enemy, or ``None``."""
        entry = self._entries.get(enemy_id)
        return None if entry is None else entry[1]

    def __contains__(self, enemy_id: object) -> bool:
        return enemy_id in self._entries

    def expire(self, current_cells: Mapping[int, Cell]) -> None:
        """Forget Enemies that are gone or have moved off their cell.

        ``current_cells`` maps each live Enemy's id to the cell it stands on.
        """
        self._entries = {
            enemy_id: (cell, value)
            for enemy_id, (cell, value) in self._entries.items()
            if current_cells.get(enemy_id) == cell
        }
